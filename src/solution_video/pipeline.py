"""Content-driven no-voice pipeline for the Phase-2 scene catalog."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

from .engine.audio import AudioMixer, write_wav
from .engine.encode import encode_frames
from .engine.theme import Theme, load_theme
from .schema import Meta, SolutionSpec
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
    meta = Meta(path=str(output_path), duration_s=duration_s, size_bytes=output_path.stat().st_size, answer_verified=False)
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
