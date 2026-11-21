from pathlib import Path

from PIL import Image
import pytest

from solution_video.engine.theme import load_theme
from solution_video.engine.timeline import Cue, SceneTiming
from solution_video.pipeline import (
    PlannedScene,
    _apply_voice_durations,
    _fit_voice_duration,
    format_sync_report,
    plan_scenes,
)
from solution_video.schema import SolutionSpec
from solution_video.voice.runtime import VoiceClip, VoiceRender, VoiceRuntimeError
from solution_video.engine.output import OutputValidationError


class FixedScene:
    def render_frame(self, time_s):
        return Image.new("RGB", (4, 4), (round(time_s), 0, 0))


def test_scene_duration_override_and_named_cues_are_relative():
    timing = SceneTiming(8.0, 4.0, (Cue("line_1", 0.25), Cue("line_2", 0.75)))
    assert timing.to_base_time(2.0) == 4.0
    assert timing.cue_time("line_1") == 1.0
    assert timing.cue_time("line_2") == 3.0


def test_scene_timing_remaps_named_animation_events_to_speech_cues():
    timing = SceneTiming(
        10.0,
        5.0,
        (Cue("line_1", 0.25), Cue("line_2", 0.75)),
        (Cue("line_1", 0.50), Cue("line_2", 0.80)),
    )
    assert timing.to_base_time(1.25) == 5.0
    assert timing.to_base_time(3.75) == 8.0


def test_planned_scene_override_maps_render_time_and_exposes_cue():
    scene = PlannedScene(
        "step",
        FixedScene(),
        duration_s=8.0,
        scene_duration_override=4.0,
        base_duration_s=8.0,
        reveal_cues=(Cue("line_1", 0.5),),
    )
    frame = scene.render_frame(2.0, load_theme())
    assert frame.getpixel((0, 0))[0] == 4
    assert scene.cue_time("line_1") == 2.0


def test_planned_reveal_cues_are_relative_and_ordered_by_narration_words():
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    spec = SolutionSpec.from_payload(json.loads((root / "examples" / "speed_train.json").read_text(encoding="utf-8")))
    plan = plan_scenes(spec, load_theme())
    question = next(item for item in plan if item.name == "question")
    step = next(item for item in plan if item.name == "step")

    assert [cue.name for cue in question.reveal_cues] == ["question"]
    line_cues = [cue for cue in step.reveal_cues if cue.name.startswith("line_")]
    assert line_cues
    assert [cue.progress for cue in line_cues] == sorted(cue.progress for cue in line_cues)


def test_animation_events_begin_at_their_narration_cues():
    import json

    root = Path(__file__).resolve().parents[1]
    spec = SolutionSpec.from_payload(json.loads((root / "examples" / "speed_train.json").read_text(encoding="utf-8")))
    plan = plan_scenes(spec, load_theme())
    question = next(item for item in plan if item.name == "question")
    step = next(item for item in plan if item.name == "step")
    question_events = {event.name: event.progress * question.base_duration_s for event in question.event_positions}
    step_events = {event.name: event.progress * step.base_duration_s for event in step.event_positions}

    assert question_events["question"] == pytest.approx(0.60)
    assert question_events["question"] == pytest.approx(0.60)
    assert step_events["line_1"] == pytest.approx(0.55)


def test_voice_reveal_cues_land_inside_the_spoken_clip_before_padding():
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    spec = SolutionSpec.from_payload(json.loads((root / "examples" / "speed_train.json").read_text(encoding="utf-8")))
    plan = plan_scenes(spec, load_theme())
    clips = tuple(
        VoiceClip(Path(f"{index}.wav"), 0.35, "edge_tts", "en-IN-NeerjaNeural", 10, 0, "spoken words")
        for index, _ in enumerate(plan)
    )
    voice = VoiceRender(clips, (), "edge_tts", "en-IN-NeerjaNeural", 70, 0)
    synchronized = _apply_voice_durations(plan, voice, 0.25)

    for scene in synchronized:
        assert max(scene.cue_time(cue.name) for cue in scene.reveal_cues) <= 0.35


def test_edge_word_boundaries_align_equations_and_short_question_cue():
    import json

    root = Path(__file__).resolve().parents[1]
    spec = SolutionSpec.from_payload(json.loads((root / "examples" / "speed_train.json").read_text(encoding="utf-8")))
    plan = plan_scenes(spec, load_theme())
    step_index = next(index for index, item in enumerate(plan) if item.name == "step")
    question_index = next(index for index, item in enumerate(plan) if item.name == "question")
    step_boundaries = (("one", 0.8), ("hundred", 0.85), ("fifty", 0.9))
    clips = []
    for index, item in enumerate(plan):
        if item.name == "question":
            clips.append(VoiceClip(Path("question.wav"), 5.0, "edge_tts", "voice", 8, 0, "speech"))
        elif item.name == "title":
            clips.append(VoiceClip(Path("title.wav"), 3.0, "edge_tts", "voice", 10, 0, "speech"))
        else:
            clips.append(VoiceClip(Path(f"{index}.wav"), 10.0, "edge_tts", "voice", 10, 0, "speech"))
    clips[step_index] = VoiceClip(
        Path("step.wav"), 10.0, "edge_tts", "voice", 10, 0, "speech", step_boundaries
    )
    voice = VoiceRender(tuple(clips), (), "edge_tts", "voice", 20, 0)
    synchronized = _apply_voice_durations(plan, voice, 0.45)
    step = synchronized[step_index]

    equation_time = step.cue_time("line_1")
    assert equation_time == pytest.approx(0.75)
    assert 0 <= 0.8 - equation_time <= 0.15

    report = format_sync_report(synchronized, voice)
    assert "step/line_1 |" in report
    assert "question/question |" in report


def test_other_providers_keep_proportional_cue_timing():
    clip = VoiceClip(Path("step.wav"), 1.0, "hf_space", "model", 10, 0, "speech")
    scene = PlannedScene(
        "step",
        FixedScene(),
        2.0,
        reveal_cues=(Cue("line_1", 0.5),),
    )
    synchronized = _apply_voice_durations(
        (scene,),
        VoiceRender((clip,), (), "hf_space", "model", 10, 0),
        0.45,
    )
    assert synchronized[0].cue_time("line_1") == pytest.approx(0.5)


def test_retiming_again_does_not_accumulate_cue_scaling():
    base = PlannedScene(
        "step",
        FixedScene(),
        duration_s=4.0,
        reveal_cues=(Cue("line_1", 0.8),),
    )
    clip = VoiceClip(Path("step.wav"), 1.0, "edge_tts", "voice", 5, 0, "speech")
    voice = VoiceRender((clip,), (), "edge_tts", "voice", 5, 0)

    padded = _apply_voice_durations((base,), voice, 0.5)
    shortened = _apply_voice_durations(padded, voice, 0.0)

    assert padded[0].cue_time("line_1") == 0.8
    assert shortened[0].cue_time("line_1") == 0.8


def test_voice_duration_rejects_over_cap_without_speeding():
    plan = (PlannedScene("title", FixedScene(), 3.0), PlannedScene("answer", FixedScene(), 4.0))
    clips = (
        VoiceClip(Path("a.wav"), 3.0, "edge_tts", "voice", 10, 0, "speech"),
        VoiceClip(Path("b.wav"), 72.5, "edge_tts", "voice", 10, 0, "speech"),
    )
    voice = VoiceRender(clips, (), "edge_tts", "voice", 20, 0)
    padded = _apply_voice_durations(plan, voice, 0.25)
    with pytest.raises(OutputValidationError, match="exceeds the 75-second limit"):
        _fit_voice_duration(voice, padded, sum(item.duration_s for item in padded))


def test_voice_duration_never_speeds_up(monkeypatch):
    import solution_video.pipeline as pipeline
    from solution_video.engine.output import OutputValidationError

    plan = (PlannedScene("title", FixedScene(), 3.0), PlannedScene("answer", FixedScene(), 4.0))
    clips = (
        VoiceClip(Path("a.wav"), 3.0, "edge_tts", "voice", 10, 0, "speech"),
        VoiceClip(Path("b.wav"), 72.5, "edge_tts", "voice", 10, 0, "speech"),
    )
    voice = VoiceRender(clips, (), "edge_tts", "voice", 20, 0)
    padded = _apply_voice_durations(plan, voice, 0.0)
    calls = []

    monkeypatch.setattr(pipeline, "speed_up_audio", lambda *_args: pytest.fail("speech speed-up is forbidden"))
    with pytest.raises(OutputValidationError, match="no speech speed-up"):
        pipeline._fit_voice_duration(voice, padded, 75.2)
