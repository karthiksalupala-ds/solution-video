"""Content-driven no-voice pipeline for the Phase-2 scene catalog."""

from __future__ import annotations

import json
import hashlib
import math
import os
import re
import sys
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from PIL import Image
from pydantic import ValidationError

from .engine.audio import AudioMixer, mix_voice_tracks, write_wav
from .engine.encode import encode_frames
from .engine.output import OutputValidationError, validate_output
from .engine.theme import Theme, load_theme
from .engine.timeline import Cue, SceneTiming
from .schema import Meta, SolutionSpec, VoiceClipMeta
from .schema import QuestionInput
from .llm import JsonProvider, LLMError, RateLimitError, prompt_for_question
from .llm.base import (
    JsonModeValidationError,
    JsonParseError,
    SpeechLanguageMode,
    resolve_speech_language_mode,
)
from .llm.base import rate_limit_delay
from .verify import verify
from .scenes import AnswerScene, OutroScene, QuestionScene, StepScene, TipScene, TitleScene
from .scenes.hello import HelloScene, HelloSpec
from .scenes.common import draw_layout, fit
from .engine.assets import FontBook
from .engine.canvas import Canvas
from .engine.text import reveal_words
from .voice.runtime import VoiceInput, VoiceRender, VoiceRuntimeError, speed_up_audio, synthesize_voice
from .voice.normalization import normalize_speech, number_to_words


@dataclass(frozen=True)
class PlannedScene:
    name: str
    scene: object
    duration_s: float
    scene_duration_override: float | None = None
    reveal_cues: tuple[Cue, ...] = ()
    event_positions: tuple[Cue, ...] = ()
    base_duration_s: float | None = None
    caption_text: str | None = None
    narration_duration_s: float = 0.0

    def __post_init__(self) -> None:
        if self.base_duration_s is None:
            object.__setattr__(self, "base_duration_s", self.duration_s)
        if self.duration_s <= 0:
            raise ValueError("Planned scene duration must be positive")
        if self.scene_duration_override is not None and self.scene_duration_override <= 0:
            raise ValueError("scene_duration_override must be positive")

    def cue_time(self, name: str) -> float:
        return SceneTiming(
            float(self.base_duration_s),
            self.scene_duration_override or self.duration_s,
            self.reveal_cues,
            self.event_positions if self.scene_duration_override is not None else (),
        ).cue_time(name)

    def render_frame(self, time_s: float, theme: Theme):
        duration = self.scene_duration_override or self.duration_s
        mapped = SceneTiming(
            float(self.base_duration_s),
            duration,
            self.reveal_cues,
            self.event_positions if self.scene_duration_override is not None else (),
        ).to_base_time(time_s)
        frame = self.scene.render_frame(mapped)
        if theme.voice.get("captions") and self.caption_text and time_s < self.narration_duration_s:
            frame = _caption_frame(frame, self.caption_text, time_s, self.narration_duration_s, theme)
        return frame


def _reading_duration(text: str, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, 1.25 + len(text.split()) / 2.5))


def _cue(name: str, progress: float) -> Cue:
    return Cue(name, max(0.0, min(1.0, progress)))


def _relative_cues(name: str, scene: object, speech: str = "") -> tuple[Cue, ...]:
    if name == "step":
        lines = scene.step.lines
        total_words = max(1, sum(len(line.split()) for line in lines))
        speech_words = max(1, len(speech.split()))
        label_words = len(scene.step.label.split())
        elapsed = 0
        cues = [_cue("label", 0.10 + 0.10 * label_words / speech_words)]
        for line_index, line in enumerate(lines, 1):
            elapsed += len(line.split())
            speech_progress = (label_words + (speech_words - label_words) * elapsed / total_words) / speech_words
            cues.append(_cue(f"line_{line_index}", 0.10 + 0.78 * speech_progress))
        return tuple(cues)
    if name == "question":
        question_words = len(scene.question.question.split())
        total_words = max(1, len(speech.split()))
        elapsed = question_words
        cues = [_cue("question", 0.08 + 0.82 * elapsed / total_words)]
        for letter, option in zip("ABCD", scene.question.options):
            elapsed += len(option.split())
            cues.append(_cue(f"option_{letter}", 0.08 + 0.82 * elapsed / total_words))
        return tuple(cues)
    if name == "title":
        return (_cue("title", 0.15),)
    if name == "answer":
        return (_cue("answer", 0.35), _cue("option", 0.70))
    if name == "tip":
        return (_cue("tip", 0.25),)
    if name == "outro":
        return (_cue("outro", 0.25),)
    return (_cue("reveal", 0.5),)


def _event_positions(name: str, scene: object, base_duration_s: float) -> tuple[Cue, ...]:
    if name == "title":
        return (_cue("title", 0.45 / base_duration_s),)
    if name == "question":
        question_event = _cue("question", 0.60 / base_duration_s)
        option_events = tuple(
            _cue(
                f"option_{letter}",
                (0.60 + option_index * float(scene.theme.motion["stagger_s"])) / base_duration_s,
            )
            for option_index, letter in enumerate("ABCD")
        )
        return (question_event, *option_events)
    if name == "step":
        label_event = _cue("label", 0.50 / base_duration_s)
        line_events = tuple(
            _cue(f"line_{line_index}", (0.55 + (line_index - 1) * 0.55) / base_duration_s)
            for line_index in range(1, len(scene.step.lines) + 1)
        )
        return (label_event, *line_events)
    if name == "answer":
        return (_cue("answer", 0.85 / base_duration_s),)
    if name == "tip":
        return (_cue("tip", 0.55 / base_duration_s),)
    if name == "outro":
        return (_cue("outro", 0.70 / base_duration_s),)
    return ()


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
    speech = _speech_inputs(spec)
    with_cues: list[PlannedScene] = []
    for index, item in enumerate(plan):
        text = speech[index].text if index < len(speech) else ""
        with_cues.append(replace(
            item,
            reveal_cues=_relative_cues(item.name, item.scene, text),
            event_positions=_event_positions(item.name, item.scene, float(item.base_duration_s)),
        ))
    return tuple(with_cues)


def render(
    spec: SolutionSpec,
    theme: Theme,
    output_path: Path,
    voice: object | None = None,
    *,
    no_voice: bool = False,
    voice_provider: str | None = None,
    sync_report: bool = False,
) -> Meta:
    """Render a verified solution with optional cached, synchronized narration."""
    del voice
    gate = verify(spec.question_input, spec)
    if not gate.passed:
        meta = Meta(path=str(output_path), duration_s=0, size_bytes=0, answer_verified=False, status="blocked", reasons=list(gate.reasons))
        output_path.with_suffix(".meta.json").write_text(json.dumps(meta.model_dump(), indent=2), encoding="utf-8")
        raise ValueError("Accuracy gate blocked render: " + "; ".join(gate.reasons))
    voice_inputs = _speech_inputs(spec)
    if no_voice:
        voice_result = VoiceRender(tuple(None for _ in voice_inputs), (), "none", None, 0, 0)
    else:
        voice_result = synthesize_voice(voice_inputs, provider_override=voice_provider)
    theme = _voice_theme(theme, voice_result)
    plan = plan_scenes(spec, theme)
    padding = _voice_padding(theme)
    plan = _apply_voice_durations(plan, voice_result, padding)
    duration_s = sum(item.duration_s for item in plan)
    voice_result, plan = _fit_voice_duration(
        voice_result,
        plan,
        duration_s,
        min(float(spec.question_input.time_sec or 75), 75.0),
    )
    duration_s = sum(item.duration_s for item in plan)
    if sync_report:
        print(format_sync_report(plan, voice_result))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    wav_path = output_path.with_suffix(".phase2.wav")
    mixed_wav_path = output_path.with_suffix(".phase5.wav")
    mixer = AudioMixer(44_100, duration_s, spec.seed)
    cursor = 0.0
    for item in plan:
        mixer.add_tick(cursor + 0.25)
        cursor += item.duration_s
    mixer.add_ding(max(0.2, duration_s - 1.0))
    write_wav(wav_path, mixer.mix())
    try:
        offsets: list[tuple[Path, float]] = []
        cursor = 0.0
        for item, clip in zip(plan, voice_result.clips):
            if clip is not None:
                offsets.append((clip.path, cursor))
            cursor += item.duration_s
        if offsets:
            mix_voice_tracks(wav_path, offsets, mixed_wav_path, duration_s)
            final_audio = mixed_wav_path
        else:
            final_audio = wav_path
        frames = (
            item.render_frame(frame / theme.canvas.fps, theme)
            for item in plan
            for frame in range(max(1, round(item.duration_s * theme.canvas.fps)))
        )
        encode_frames(frames, theme.canvas.width, theme.canvas.height, theme.canvas.fps, final_audio, output_path, duration_s)
    finally:
        wav_path.unlink(missing_ok=True)
        mixed_wav_path.unlink(missing_ok=True)
    try:
        validate_output(output_path, expect_audio=True)
    except OutputValidationError:
        output_path.unlink(missing_ok=True)
        raise
    warnings = list(voice_result.warnings)
    if no_voice:
        warnings = []
    clip_meta = []
    step_number = 0
    for item, clip in zip(plan, voice_result.clips):
        if item.name == "step":
            step_number += 1
        if clip is not None:
            clip_meta.append(VoiceClipMeta(
                scene=f"step-{step_number}" if item.name == "step" else item.name,
                provider=clip.provider,
                model=clip.model,
                characters=clip.characters,
                credits=clip.credits,
            ))
    meta = Meta(
        path=str(output_path),
        duration_s=duration_s,
        size_bytes=output_path.stat().st_size,
        answer_verified=True,
        voice_provider=voice_result.provider,
        voice_model=voice_result.model,
        voice_language_mode=os.environ.get("SPEECH_LANGUAGE_MODE", "english") if voice_result.provider != "none" else None,
        voice_characters=voice_result.characters,
        voice_credits=voice_result.credits,
        voice_clips=clip_meta,
        warnings=warnings,
    )
    output_path.with_suffix(".meta.json").write_text(json.dumps(meta.model_dump(), indent=2), encoding="utf-8")
    return meta


def _speech_inputs(spec: SolutionSpec) -> tuple[VoiceInput, ...]:
    question = spec.question_input
    spoken_question = " ".join((
        question.question,
        *(f"Option {letter}: {option}." for letter, option in zip("ABCD", question.options)),
    ))
    inputs = [
        VoiceInput("title", f"Day {question.day}. {question.topic}."),
        VoiceInput("question", spoken_question),
        *(VoiceInput(f"step-{index}", step.speech) for index, step in enumerate(spec.steps, 1)),
    ]
    if spec.tip:
        inputs.append(VoiceInput("tip", spec.tip.speech or spec.tip.display))
    inputs.append(VoiceInput("answer", spec.answer.speech))
    if spec.cta:
        inputs.append(VoiceInput("outro", spec.cta.speech or spec.cta.display))
    return tuple(inputs)


def _voice_theme(theme: Theme, voice: VoiceRender) -> Theme:
    if "elevenlabs" not in {clip.provider for clip in voice.clips if clip}:
        return theme
    if not theme.voice.get("public_facing", False):
        return theme
    text = str(theme.voice.get("elevenlabs_attribution_text", "")).strip()
    if not text:
        return theme
    return replace(theme, branding={**theme.branding, "voice_attribution_text": text})


def _voice_padding(theme: Theme) -> float:
    value = theme.voice.get("scene_padding_s", 0.25)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError("Theme voice.scene_padding_s must be a non-negative number")
    return float(value)


def _apply_voice_durations(
    plan: tuple[PlannedScene, ...],
    voice: VoiceRender,
    padding_s: float,
) -> tuple[PlannedScene, ...]:
    if len(plan) != len(voice.clips):
        raise ValueError("Voice clips do not match the planned scene count")
    adjusted = []
    for item, clip in zip(plan, voice.clips):
        if clip is None:
            adjusted.append(item)
            continue
        duration = clip.duration_s + padding_s
        base_cues = item.reveal_cues
        if item.scene_duration_override is not None and item.narration_duration_s > 0:
            previous_clip_progress = item.narration_duration_s / item.scene_duration_override
            base_cues = tuple(
                Cue(cue.name, cue.progress / previous_clip_progress)
                for cue in item.reveal_cues
            )
        clip_progress = clip.duration_s / duration
        cues = []
        for cue in base_cues:
            word_offset = _cue_word_offset(item, cue.name, clip.word_boundaries)
            progress = cue.progress * clip_progress
            if word_offset is not None:
                progress = min(1.0, max(0.0, word_offset - 0.05) / duration)
            cues.append(Cue(cue.name, progress))
        adjusted.append(replace(
            item,
            duration_s=duration,
            scene_duration_override=duration,
            reveal_cues=tuple(cues),
            caption_text=clip.text,
            narration_duration_s=clip.duration_s,
        ))
    return tuple(adjusted)


def _cue_word_offset(
    item: PlannedScene,
    cue_name: str,
    word_boundaries: tuple[tuple[str, float], ...],
) -> float | None:
    """Find the spoken key token for a cue using Edge TTS word-boundary data."""
    if not word_boundaries:
        return None
    scene = item.scene
    target: str | None = None
    match_last = False
    if item.name == "step":
        if cue_name.startswith("line_"):
            try:
                line = scene.step.lines[int(cue_name.removeprefix("line_")) - 1]
            except (ValueError, IndexError):
                return None
            numeric = re.search(r"(?<!\w)-?\d+(?:,\d{3})*(?:\.\d+)?", line)
            target = number_to_words(numeric.group(0)) if numeric else line
        elif cue_name == "label":
            target = scene.step.label
    elif item.name == "question":
        if cue_name == "question":
            target = scene.question.question
            match_last = True
        elif cue_name.startswith("option_"):
            letter = cue_name.removeprefix("option_")
            try:
                option = scene.question.options[ord(letter) - ord("A")]
            except (IndexError, TypeError):
                return None
            target = f"Option {letter} {option}"
    elif item.name == "title" and cue_name == "title":
        target = " ".join((str(scene.question.day), scene.question.topic))
    elif item.name == "answer":
        if cue_name == "answer":
            target = scene.answer.display
        elif cue_name == "option":
            option = scene.answer.correct_option or scene.question.correct_option
            target = f"Option {option}" if option else None
    elif item.name == "tip" and cue_name == "tip":
        target = scene.tip.speech or scene.tip.display
    elif item.name == "outro" and cue_name == "outro":
        target = scene.cta.speech or scene.cta.display
    if not target:
        return None

    target_words = _spoken_words(target)
    flattened = [
        (word, offset)
        for text, offset in word_boundaries
        for word in re.findall(r"[a-z0-9]+", text.casefold())
    ]
    if not target_words or not flattened:
        return None
    for start in range(len(flattened) - len(target_words) + 1):
        if [word for word, _ in flattened[start:start + len(target_words)]] == target_words:
            index = start + len(target_words) - 1 if match_last else start
            return flattened[index][1]
    if item.name == "question" and cue_name.startswith("option_"):
        option_words = _spoken_words(scene.question.options[ord(cue_name[-1]) - ord("A")])
        for start, (word, offset) in enumerate(flattened):
            if word == "option" and start + 2 < len(flattened):
                if flattened[start + 1][0] == cue_name[-1].casefold():
                    option_tokens = [token for token in option_words if token not in {"the", "a", "an"}]
                    if option_tokens and flattened[start + 2][0] == option_tokens[0]:
                        return flattened[start + 2][1]
    return None


def _spoken_words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", normalize_speech(text).casefold())


def format_sync_report(
    plan: tuple[PlannedScene, ...],
    voice: VoiceRender,
) -> str:
    """Format expected word-boundary and actual reveal times for each scene cue."""
    lines = ["Sync table (video time)", "Scene / cue | expected word | actual reveal"]
    cursor = 0.0
    for item, clip in zip(plan, voice.clips):
        for cue in item.reveal_cues:
            expected = _cue_word_offset(item, cue.name, clip.word_boundaries) if clip else None
            actual = cursor + item.cue_time(cue.name)
            expected_label = f"{cursor + expected:.2f}s" if expected is not None else "proportional fallback"
            lines.append(f"{item.name}/{cue.name} | {expected_label} | {actual:.2f}s")
        cursor += item.duration_s
    return "\n".join(lines)


def _fit_voice_duration(
    voice: VoiceRender,
    plan: tuple[PlannedScene, ...],
    duration_s: float,
    maximum_s: float = 75.0,
) -> tuple[VoiceRender, tuple[PlannedScene, ...]]:
    maximum = maximum_s
    if maximum <= 0 or maximum > 75:
        raise VoiceRuntimeError("Voice render duration limit must be greater than zero and at most 75 seconds")
    if duration_s <= maximum:
        return voice, plan
    spoken_count = sum(clip is not None for clip in voice.clips)
    if spoken_count == 0:
        raise VoiceRuntimeError(
            f"Planned video duration {duration_s:.2f}s exceeds the {maximum:.0f}-second limit"
        )
    speech_duration = sum(clip.duration_s for clip in voice.clips if clip is not None)
    silent_scene_duration = sum(
        item.duration_s for item, clip in zip(plan, voice.clips) if clip is None
    )
    if speech_duration + silent_scene_duration <= maximum:
        padding = (maximum - speech_duration - silent_scene_duration) / spoken_count
        return voice, _apply_voice_durations(plan, voice, padding)
    factor = (speech_duration + silent_scene_duration) / maximum
    if factor > 1.12:
        raise VoiceRuntimeError(
            f"Narration would exceed the {maximum:.0f}-second limit even with padding removed "
            f"({speech_duration + silent_scene_duration:.2f}s); shorten the script"
        )
    clips = []
    for clip in voice.clips:
        if clip is None:
            clips.append(None)
            continue
        path, shortened_duration = speed_up_audio(clip.path, factor)
        clips.append(replace(
            clip,
            path=path,
            duration_s=shortened_duration,
            word_boundaries=tuple((word, offset / factor) for word, offset in clip.word_boundaries),
        ))
    shortened = replace(voice, clips=tuple(clips))
    adjusted_plan = _apply_voice_durations(plan, shortened, 0.0)
    if sum(item.duration_s for item in adjusted_plan) > maximum + 0.05:
        raise VoiceRuntimeError(
            f"Narration remains longer than the {maximum:.0f}-second limit after slight speed-up"
        )
    return shortened, adjusted_plan


def _caption_frame(frame: Image.Image, text: str, time_s: float, duration_s: float, theme: Theme) -> Image.Image:
    words = text.split()
    if not words:
        return frame
    shown = max(1, min(len(words), math.ceil(len(words) * time_s / duration_s)))
    caption = " ".join(words[max(0, shown - 12):shown])
    canvas = Canvas(theme.canvas.width, theme.canvas.height, background=(0, 0, 0, 0))
    canvas.composite(frame.convert("RGBA"))
    layout = fit(theme, "medium", caption, theme.canvas.width - 100, 135, 42, 3)
    top = theme.canvas.height - 230
    canvas.rounded_rect((42, top - 18, theme.canvas.width - 42, theme.canvas.height - 105), 20, (0, 0, 0, 205))
    draw_layout(
        canvas,
        FontBook(theme),
        theme,
        layout,
        theme.canvas.width / 2,
        top,
        role="medium",
        color="text",
        anchor="ma",
        line_gap=3,
    )
    return canvas.final_rgb()


def render_from_file(
    input_path: Path,
    output_path: Path,
    *,
    theme_path: str | Path | None = None,
    seed: int | None = None,
    no_voice: bool = False,
    voice_provider: str | None = None,
    sync_report: bool = False,
) -> Meta:
    try:
        payload = json.loads(input_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"Unable to read input JSON: {input_path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid input JSON: {exc.msg}") from exc
    spec = SolutionSpec.from_payload(payload)
    if seed is not None:
        if not 0 <= seed <= 2**31 - 1:
            raise ValueError("seed must be between 0 and 2147483647")
        spec = spec.model_copy(update={"seed": seed})
    return render(
        spec, load_theme(Path(theme_path) if theme_path else None), output_path,
        no_voice=no_voice,
        voice_provider=voice_provider,
        sync_report=sync_report,
    )


def generate_steps(
    question: QuestionInput,
    provider: JsonProvider,
    *,
    cache_dir: Path | None = None,
    speech_language_mode: str | None = None,
) -> SolutionSpec:
    """Ask a provider for steps and bind them to the authoritative question."""
    mode: SpeechLanguageMode = resolve_speech_language_mode(speech_language_mode)
    question_payload = question.model_dump(mode="json")
    prompt = prompt_for_question(question_payload, mode)
    schema = SolutionSpec.model_json_schema()
    cache_path = _steps_cache_path(question_payload, mode, cache_dir) if cache_dir else None
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
    gate_repair_attempted = False
    rate_limit_retries = 0
    while api_attempts < 3:
        api_attempts += 1
        try:
            payload = provider.generate_json(prompt, schema)
        except JsonModeValidationError as exc:
            if not exc.fallback_available:
                raise
            if repairs == 2 or api_attempts == 3:
                raise LLMError(
                    f"Groq JSON-mode fallback exhausted the shared {api_attempts}-request budget: {exc}"
                ) from exc
            repairs += 1
            failed_output = (
                f"\nGroq failed_generation:\n{exc.failed_generation}"
                if exc.failed_generation
                else "\nGroq did not provide a failed_generation value."
            )
            prompt = (
                f"{prompt}\n\nGroq rejected JSON mode with this exact error: {exc}\n"
                "Retry without response_format. Return one valid JSON object only; "
                "do not wrap it in prose.\n"
                f"{failed_output}"
            )
            time.sleep(1.0)
            continue
        except RateLimitError as exc:
            if api_attempts == 3:
                raise LLMError(
                    f"Rate limit persisted after {api_attempts} attempts: {exc}"
                ) from exc
            time.sleep(rate_limit_delay(rate_limit_retries, exc.retry_after_s))
            rate_limit_retries += 1
            continue
        except JsonParseError as exc:
            if repairs == 2 or api_attempts == 3:
                raise ValueError(
                    f"Provider returned invalid JSON after {api_attempts} API attempts"
                ) from exc
            repairs += 1
            prompt = (
                f"{prompt}\n\nYour previous response was not valid JSON after code-fence "
                f"stripping: {exc}\nReturn a corrected JSON object only.\n"
                f"Previous response:\n{exc.response_text}"
            )
            time.sleep(1.0)
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
        gate_reasons = "; ".join(gate.reasons)
        arithmetic_gate_failure = any(
            marker in gate_reasons
            for marker in (
                "arithmetic is false",
                "machine-evaluable arithmetic equality",
                "operands absent from the question",
                "tautology/filler",
                "Last evaluated step result",
            )
        )
        if arithmetic_gate_failure and not gate_repair_attempted and api_attempts < 3:
            gate_repair_attempted = True
            repairs += 1
            prompt = (
                f"{prompt}\n\nYour previous JSON failed the accuracy gate. "
                "Correct the arithmetic and return the complete JSON object. "
                f"Exact gate reasons: {gate_reasons}"
            )
            time.sleep(1.0)
            continue
        if arithmetic_gate_failure and gate_repair_attempted:
            raise ValueError(
                "Accuracy gate blocked generated steps after the single arithmetic repair: "
                + gate_reasons
            )
        if repairs == 2 or api_attempts == 3:
            raise ValueError(
                f"Accuracy gate blocked generated steps after {repairs} repairs: {gate_reasons}"
            )
        repairs += 1
        prompt = (
            f"{prompt}\n\nYour previous JSON failed the accuracy gate: {gate_reasons}. "
            "Return corrected JSON only."
        )
        time.sleep(1.0)
    raise AssertionError("unreachable")


def _steps_cache_path(
    question_payload: dict[str, Any],
    speech_language_mode: SpeechLanguageMode,
    cache_dir: Path,
) -> Path:
    """Build the cache path from the question and narration-language config."""
    cache_payload = {"question": question_payload, "speech_language_mode": speech_language_mode}
    encoded = json.dumps(cache_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
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
    try:
        validate_output(output_path, expect_audio=True)
    except OutputValidationError:
        output_path.unlink(missing_ok=True)
        raise
    meta = Meta(path=str(output_path), duration_s=frame_count / theme.canvas.fps, size_bytes=output_path.stat().st_size, answer_verified=False)
    output_path.with_suffix(".meta.json").write_text(json.dumps(meta.model_dump(), indent=2), encoding="utf-8")
    return meta
