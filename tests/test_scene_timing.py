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

    assert [cue.name for cue in question.reveal_cues] == [
        "question", "option_A", "option_B", "option_C", "option_D",
    ]
    assert [cue.progress for cue in question.reveal_cues] == sorted(
        cue.progress for cue in question.reveal_cues
    )
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
    assert question_events["option_A"] == pytest.approx(0.60)
    assert question_events["option_B"] == pytest.approx(0.72)
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


def test_edge_word_boundaries_align_equations_and_question_options():
    import json

    root = Path(__file__).resolve().parents[1]
    spec = SolutionSpec.from_payload(json.loads((root / "examples" / "speed_train.json").read_text(encoding="utf-8")))
    plan = plan_scenes(spec, load_theme())
    step_index = next(index for index, item in enumerate(plan) if item.name == "step")
    question_index = next(index for index, item in enumerate(plan) if item.name == "question")
    step_boundaries = (("one", 0.8), ("hundred", 0.85), ("fifty", 0.9))
    question_boundaries = (
        ("Option", 4.0), ("A", 4.05), ("seventy", 4.1), ("two", 4.15),
        ("Option", 5.0), ("B", 5.05), ("ninety", 5.1),
        ("Option", 6.0), ("C", 6.05), ("one", 6.1), ("hundred", 6.15), ("eight", 6.2),
        ("Option", 7.0), ("D", 7.05), ("one", 7.1), ("hundred", 7.15), ("twenty", 7.2),
    )
    clips = [
        VoiceClip(Path(f"{index}.wav"), 10.0, "edge_tts", "voice", 10, 0, "speech")
        for index in range(len(plan))
    ]
    clips[step_index] = VoiceClip(
        Path("step.wav"), 10.0, "edge_tts", "voice", 10, 0, "speech", step_boundaries
    )
    clips[question_index] = VoiceClip(
        Path("question.wav"), 10.0, "edge_tts", "voice", 10, 0, "speech", question_boundaries
    )
    voice = VoiceRender(tuple(clips), (), "edge_tts", "voice", 20, 0)
    synchronized = _apply_voice_durations(plan, voice, 0.45)
    step = synchronized[step_index]
    question = synchronized[question_index]

    equation_time = step.cue_time("line_1")
    assert equation_time == pytest.approx(0.75)
    assert 0 <= 0.8 - equation_time <= 0.15
    for letter, expected in zip("ABCD", (4.0, 5.0, 6.0, 7.0)):
        actual = question.cue_time(f"option_{letter}")
        assert actual == pytest.approx(expected - 0.05)
        assert 0 <= expected - actual <= 0.15

    report = format_sync_report(synchronized, voice)
    assert "step/line_1 |" in report
    assert "question/option_A |" in report


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


def test_voice_duration_removes_padding_before_speeding_up():
    plan = (PlannedScene("title", FixedScene(), 3.0), PlannedScene("answer", FixedScene(), 4.0))
    clips = (
        VoiceClip(Path("a.wav"), 37.4, "edge_tts", "voice", 10, 0, "speech"),
        VoiceClip(Path("b.wav"), 37.4, "edge_tts", "voice", 10, 0, "speech"),
    )
    voice = VoiceRender(clips, (), "edge_tts", "voice", 20, 0)
    padded = _apply_voice_durations(plan, voice, 0.25)

    result, adjusted = _fit_voice_duration(voice, padded, sum(item.duration_s for item in padded))

    assert result is voice
    assert sum(item.duration_s for item in adjusted) == 75.0
    assert all(item.duration_s == 37.5 for item in adjusted)


def test_voice_duration_speeds_up_slightly_then_rejects_excess(monkeypatch):
    import solution_video.pipeline as pipeline

    plan = (PlannedScene("title", FixedScene(), 3.0), PlannedScene("answer", FixedScene(), 4.0))
    clips = (
        VoiceClip(Path("a.wav"), 37.6, "edge_tts", "voice", 10, 0, "speech"),
        VoiceClip(Path("b.wav"), 37.6, "edge_tts", "voice", 10, 0, "speech"),
    )
    voice = VoiceRender(clips, (), "edge_tts", "voice", 20, 0)
    padded = _apply_voice_durations(plan, voice, 0.0)
    calls = []

    def fake_speed(path, factor):
        calls.append(factor)
        return path, 37.6 / factor

    monkeypatch.setattr(pipeline, "speed_up_audio", fake_speed)
    shortened, adjusted = pipeline._fit_voice_duration(voice, padded, 75.2)
    assert len(calls) == 2
    assert all(1 < factor <= 1.12 for factor in calls)
    assert sum(item.duration_s for item in adjusted) <= 75.05
    assert shortened.credits == 0

    too_long = VoiceRender(
        tuple(VoiceClip(Path(f"{index}.wav"), 45.0, "edge_tts", "voice", 10, 0, "speech") for index in range(2)),
        (),
        "edge_tts",
        "voice",
        20,
        0,
    )
    too_long_plan = _apply_voice_durations(plan, too_long, 0.0)
    with pytest.raises(VoiceRuntimeError, match="even with padding removed"):
        pipeline._fit_voice_duration(too_long, too_long_plan, 90.0)
