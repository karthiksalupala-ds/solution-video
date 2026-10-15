"""Content-driven no-voice pipeline for the Phase-2 scene catalog."""

from __future__ import annotations

import json
import hashlib
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .engine.audio import AudioMixer, write_wav
from .engine.encode import encode_frames
from .engine.theme import Theme, load_theme
from .schema import Meta, SolutionSpec
from .schema import QuestionInput
from .llm import JsonProvider, LLMError, RateLimitError, prompt_for_question
from .llm.base import rate_limit_delay
from .verify import verify
from .scenes import AnswerScene, OutroScene, QuestionScene, StepScene, TipScene, TitleScene
from .scenes.hello import HelloScene, HelloSpec


@dataclass(frozen=True)
class PlannedScene:
    name: str
    scene: object
    duration_s: float


def _reading_duration(text: str, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, 1.25 + len(text.split()) / 2.5))


def plan_scenes(spec: SolutionSpec, theme: Theme) -> tuple[PlannedScene, ...]:
    question = spec.question_input
    plan: list[PlannedScene] = [
        PlannedScene("title", TitleScene(question, theme), 3.0),
        PlannedScene("question", QuestionScene(question, theme), _reading_duration(question.question, 5.0, 9.0)),
    ]
    for index, step in enumerate(spec.steps, 1):
        plan.append(PlannedScene("step", StepScene(step, index, len(spec.steps), theme), _reading_duration(" ".join([step.label, *step.lines]), 3.2, 8.5)))
    if spec.tip:
        plan.append(PlannedScene("tip", TipScene(spec.tip, theme), _reading_duration(spec.tip.display, 2.5, 4.5)))
    plan.append(PlannedScene("answer", AnswerScene(spec.answer, question, theme), 4.0))
    if spec.cta:
        plan.append(PlannedScene("outro", OutroScene(spec.cta, theme), _reading_duration(spec.cta.display, 2.0, 3.5)))
    cap = question.time_sec or 75
    total = sum(item.duration_s for item in plan)
    if total > cap:
        scale = max(0.65, cap / total)
        plan = [PlannedScene(item.name, item.scene, item.duration_s * scale) for item in plan]
    return tuple(plan)


def render(spec: SolutionSpec, theme: Theme, output_path: Path, voice: object | None = None) -> Meta:
    """Render a validated spec; voice is reserved for the Phase-5 contract."""
    del voice
    gate = verify(spec.question_input, spec)
    if not gate.passed:
        meta = Meta(path=str(output_path), duration_s=0, size_bytes=0, answer_verified=False, status="blocked", reasons=list(gate.reasons))
        output_path.with_suffix(".meta.json").write_text(json.dumps(meta.model_dump(), indent=2), encoding="utf-8")
        raise ValueError("Accuracy gate blocked render: " + "; ".join(gate.reasons))
    plan = plan_scenes(spec, theme)
    duration_s = sum(item.duration_s for item in plan)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    wav_path = output_path.with_suffix(".phase2.wav")
    mixer = AudioMixer(44_100, duration_s, spec.seed)
    cursor = 0.0
    for item in plan:
        mixer.add_tick(cursor + 0.25)
        cursor += item.duration_s
    mixer.add_ding(max(0.2, duration_s - 1.0))
    write_wav(wav_path, mixer.mix())
    try:
        frames = (item.scene.render_frame(frame / theme.canvas.fps) for item in plan for frame in range(max(1, round(item.duration_s * theme.canvas.fps))))
        encode_frames(frames, theme.canvas.width, theme.canvas.height, theme.canvas.fps, wav_path, output_path, duration_s)
    finally:
        wav_path.unlink(missing_ok=True)
    meta = Meta(path=str(output_path), duration_s=duration_s, size_bytes=output_path.stat().st_size, answer_verified=True)
    output_path.with_suffix(".meta.json").write_text(json.dumps(meta.model_dump(), indent=2), encoding="utf-8")
    return meta


def render_from_file(input_path: Path, output_path: Path, *, theme_path: str | Path | None = None) -> Meta:
    try:
        payload = json.loads(input_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"Unable to read input JSON: {input_path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid input JSON: {exc.msg}") from exc
    return render(SolutionSpec.from_payload(payload), load_theme(Path(theme_path) if theme_path else None), output_path)


def generate_steps(
    question: QuestionInput,
    provider: JsonProvider,
    *,
    cache_dir: Path | None = None,
) -> SolutionSpec:
    """Ask a provider for steps and bind them to the authoritative question."""
    question_payload = question.model_dump(mode="json")
    prompt = prompt_for_question(question_payload)
    schema = SolutionSpec.model_json_schema()
    cache_path = _steps_cache_path(question_payload, cache_dir) if cache_dir else None
    if cache_path and cache_path.exists():
        try:
            cached = SolutionSpec.model_validate_json(cache_path.read_text(encoding="utf-8"))
        except (OSError, ValidationError) as exc:
            raise ValueError(f"Cached generated steps are invalid: {cache_path}") from exc
        gate = verify(question, cached)
        if not gate.passed:
            raise ValueError(f"Cached generated steps failed verification: {'; '.join(gate.reasons)}")
        return cached

    api_attempts = 0
    repairs = 0
    rate_limit_retries = 0
    while api_attempts < 3:
        api_attempts += 1
        try:
            payload = provider.generate_json(prompt, schema)
        except RateLimitError as exc:
            if api_attempts == 3:
                raise LLMError(
                    f"Rate limit persisted after {api_attempts} attempts: {exc}"
                ) from exc
            time.sleep(rate_limit_delay(rate_limit_retries, exc.retry_after_s))
            rate_limit_retries += 1
            continue
        raw_payload = payload.copy()
        payload["question_input"] = question_payload
        try:
            spec = SolutionSpec.model_validate(payload)
        except ValidationError as exc:
            _report_schema_failure(exc, raw_payload)
            if repairs == 2:
                raise ValueError(f"Generated steps failed schema validation after 2 repairs: {exc}") from exc
            if api_attempts == 3:
                raise ValueError(f"Generated steps exhausted {api_attempts} API attempts on schema validation: {exc}") from exc
            repairs += 1
            prompt = (
                f"{prompt}\n\nYour previous JSON failed schema validation. "
                f"Return a corrected JSON object only. Exact validation error:\n{exc}"
            )
            time.sleep(1.0)
            continue
        gate = verify(question, spec)
        if gate.passed:
            if cache_path:
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_text(spec.model_dump_json(indent=2), encoding="utf-8")
            return spec
        if repairs == 2 or api_attempts == 3:
            raise ValueError("Accuracy gate blocked generated steps after 2 repairs: " + "; ".join(gate.reasons))
        repairs += 1
        prompt = f"{prompt}\n\nYour previous JSON failed the accuracy gate: {'; '.join(gate.reasons)}. Return corrected JSON only."
        time.sleep(1.0)
    raise AssertionError("unreachable")


def _steps_cache_path(question_payload: dict[str, Any], cache_dir: Path) -> Path:
    """Build the stable cache path for the normalized authoritative input."""
    encoded = json.dumps(question_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()
    return cache_dir / f"{digest}.json"


def _report_schema_failure(error: ValidationError, payload: dict[str, Any]) -> None:
    """Report only invalid model fields, redacting secret-shaped values."""
    field_values = []
    for issue in error.errors(include_url=False):
        location = issue["loc"]
        value = payload
        for part in location:
            try:
                value = value[part]
            except (KeyError, IndexError, TypeError):
                value = "<missing>"
                break
        field_values.append({
            "field": ".".join(str(part) for part in location) or "<root>",
            "value": _redact_sensitive_values(value),
        })
    details = json.dumps(field_values, ensure_ascii=False, default=str)
    diagnostic = f"Generated response schema validation failed:\n{error}\nFailed raw output fields: {details}"
    diagnostic = re.sub(
        r"(?i)\b(gsk_[A-Za-z0-9]{8,}|AIza[A-Za-z0-9_-]{20,}|hf_[A-Za-z0-9]{16,}|sk-[A-Za-z0-9_-]{16,})\b",
        "[REDACTED]",
        diagnostic,
    )
    diagnostic = re.sub(r"(?i)(Bearer\s+)[A-Za-z0-9._~+/-]+", r"\1[REDACTED]", diagnostic)
    print(diagnostic, file=sys.stderr)


def _redact_sensitive_values(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if re.search(r"(?i)(key|token|secret|password)", str(key)) else _redact_sensitive_values(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_sensitive_values(item) for item in value]
    if isinstance(value, str):
        value = re.sub(
            r"(?i)\b(gsk_[A-Za-z0-9]{8,}|AIza[A-Za-z0-9_-]{20,}|hf_[A-Za-z0-9]{16,}|sk-[A-Za-z0-9_-]{16,})\b",
            "[REDACTED]",
            value,
        )
        return re.sub(r"(?i)(Bearer\s+)[A-Za-z0-9._~+/-]+", r"\1[REDACTED]", value)
    return value


def render_hello(input_path: Path, output_path: Path, *, theme_path: str | Path | None = None) -> Meta:
    """Render the Phase-1 generic scene and an adjacent meta JSON file."""
    try:
        payload = json.loads(input_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"Unable to read input JSON: {input_path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid input JSON: {exc.msg}") from exc
    theme = load_theme(Path(theme_path) if theme_path else None)
    spec = HelloSpec.from_mapping(payload)
    scene = HelloScene(spec, theme)
    frame_count = round(spec.duration_s * theme.canvas.fps)
    if frame_count < 1:
        raise ValueError("duration_s must create at least one frame")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    wav_path = output_path.with_suffix(".phase1.wav")
    mixer = AudioMixer(44_100, spec.duration_s, spec.seed)
    mixer.add_whoosh(0.08)
    mixer.add_pop(0.50)
    mixer.add_ding(max(0.1, spec.duration_s - 1.2))
    write_wav(wav_path, mixer.mix())
    try:
        encode_frames(
            (scene.render_frame(frame / theme.canvas.fps) for frame in range(frame_count)),
            theme.canvas.width, theme.canvas.height, theme.canvas.fps, wav_path, output_path, spec.duration_s,
        )
    finally:
        wav_path.unlink(missing_ok=True)
    meta = Meta(path=str(output_path), duration_s=frame_count / theme.canvas.fps, size_bytes=output_path.stat().st_size, answer_verified=False)
    output_path.with_suffix(".meta.json").write_text(json.dumps(meta.model_dump(), indent=2), encoding="utf-8")
    return meta
