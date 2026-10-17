from __future__ import annotations

import json
import warnings
from pathlib import Path

from PIL import Image, ImageChops
import pytest

from solution_video.engine.canvas import Canvas
from solution_video.engine.theme import load_theme
from solution_video.engine.timeline import Cue
from solution_video.pipeline import PlannedScene, plan_scenes
from solution_video.schema import SolutionSpec, VisualSpec
from solution_video.scenes.step import StepScene


ROOT = Path(__file__).resolve().parents[1]
BOUNDS = (40, 500, 680, 1050)


def _example_spec(name: str) -> SolutionSpec:
    payload = json.loads((ROOT / "examples" / name).read_text(encoding="utf-8"))
    return SolutionSpec.from_payload(payload)


def test_bar_chart_uses_question_values_and_animates_count_up():
    from solution_video.plugins import draw_visual
    from solution_video.plugins.bar_chart import _bar_progress, _format_animated_value

    theme = load_theme()
    visual = VisualSpec.model_validate({
        "name": "bar_chart",
        "data": {
            "title": "Quarterly sales",
            "values": [120, 150, 180, 210],
            "labels": ["Q1", "Q2", "Q3", "Q4"],
            "highlight_indices": [0, 1, 2, 3],
        },
    })
    early = Canvas(720, 1280, background=theme.colors["bg_top"])
    late = Canvas(720, 1280, background=theme.colors["bg_top"])

    assert draw_visual(early, visual, BOUNDS, 0.0, theme)
    assert draw_visual(late, visual, BOUNDS, 2.0, theme)
    assert ImageChops.difference(early.final_rgb(), late.final_rgb()).getbbox() is not None
    assert _bar_progress(0.5, 0, 1.4, 0.18) > _bar_progress(0.5, 3, 1.4, 0.18)
    assert _bar_progress(2.0, 3, 1.4, 0.18) == 1
    assert _format_animated_value(120.0, 0.5) == "60"


def test_train_crossing_uses_supplied_lengths_and_time():
    from solution_video.plugins import draw_visual

    theme = load_theme()
    visual = VisualSpec.model_validate({
        "name": "train_crossing",
        "data": {
            "train_length_m": 150,
            "platform_length_m": 250,
            "crossing_time_s": 20,
            "distance_unit": "m",
            "time_unit": "s",
            "train_label": "Train",
            "platform_label": "Platform",
            "front_marker_label": "Front enters",
            "rear_marker_label": "Rear leaves",
            "elapsed_label": "Elapsed",
            "distance_label": "Distance covered",
        },
    })
    start = Canvas(720, 1280, background=theme.colors["bg_top"])
    middle = Canvas(720, 1280, background=theme.colors["bg_top"])
    end = Canvas(720, 1280, background=theme.colors["bg_top"])

    assert draw_visual(start, visual, BOUNDS, 0.0, theme)
    assert draw_visual(middle, visual, BOUNDS, 1.5, theme)
    assert draw_visual(end, visual, BOUNDS, 3.1, theme)
    assert ImageChops.difference(start.final_rgb(), middle.final_rgb()).getbbox() is not None
    assert ImageChops.difference(start.final_rgb(), end.final_rgb()).getbbox() is not None
    assert ImageChops.difference(middle.final_rgb(), end.final_rgb()).getbbox() is not None


def test_train_crossing_animation_starts_and_ends_at_platform_markers():
    from solution_video.plugins.train_crossing import _crossing_geometry, _crossing_progress

    assert _crossing_progress(0.0, 3.0) == 0
    assert _crossing_progress(1.5, 3.0) == 0.5
    assert _crossing_progress(3.0, 3.0) == 1
    train_length, platform_length, track_left, track_width = 150, 250, 20, 560
    start = _crossing_geometry(track_left, track_width, train_length, platform_length, 0)
    end = _crossing_geometry(track_left, track_width, train_length, platform_length, 1)
    _, start_train_width, start_platform_left, _ = start
    end_train_left, end_train_width, _, end_platform_right = end

    assert track_left + start_train_width == start_platform_left
    assert end_train_left == end_platform_right
    assert end_train_left + end_train_width == track_left + track_width


def test_plugin_motion_uses_scene_time_without_changing_cue_mapped_content():
    theme = load_theme()
    step = _example_spec("speed_train.json").steps[0]
    scene = StepScene(step, 1, 3, theme)
    planned = PlannedScene(
        name="step",
        scene=scene,
        duration_s=4.0,
        scene_duration_override=4.0,
        reveal_cues=(Cue("label", 0.2), Cue("line_1", 0.8)),
        event_positions=(Cue("label", 0.16), Cue("line_1", 0.55)),
        base_duration_s=3.2,
    )

    assert planned.plugin_time(0.8, theme) == 0
    assert 0 < planned.plugin_time(2.0, theme) < theme.motion["plugin_train_duration_s"]
    assert planned.plugin_time(3.9, theme) == theme.motion["plugin_train_duration_s"]
    assert planned.cue_time("line_1") == 3.2


@pytest.mark.parametrize(
    ("example", "expected_visual"),
    (("speed_train.json", "train_crossing"), ("di_average.json", "bar_chart")),
)
def test_examples_attach_visuals_to_the_expected_steps(example: str, expected_visual: str):
    theme = load_theme()
    plan = plan_scenes(_example_spec(example), theme)
    steps = [item for item in plan if item.name == "step"]

    assert steps[0].scene.step.visual is not None
    assert steps[0].scene.step.visual.name == expected_visual
    assert all(item.render_frame(item.duration_s * 0.8, theme).size == (720, 1280) for item in steps)


def test_unknown_visual_warns_and_keeps_generic_step_rendering():
    theme = load_theme()
    example_step = _example_spec("speed_train.json").steps[0].model_copy(
        update={"visual": VisualSpec(name="future_plugin")}
    )
    scene = StepScene(example_step, 1, 1, theme)

    with pytest.warns(RuntimeWarning, match="Unknown visual plugin"):
        frame = scene.render_frame(2.0)

    with warnings.catch_warnings(record=True) as logged:
        warnings.simplefilter("always")
        scene.render_frame(2.0)

    assert frame.size == (720, 1280)
    assert not logged


def test_invalid_visual_data_warns_and_keeps_generic_step_rendering():
    theme = load_theme()
    example_step = _example_spec("di_average.json").steps[0].model_copy(
        update={"visual": VisualSpec(name="bar_chart", data={"values": [1], "labels": ["Q1"]})}
    )
    scene = StepScene(example_step, 1, 2, theme)

    with pytest.warns(RuntimeWarning, match="Invalid 'bar_chart' visual data"):
        frame = scene.render_frame(2.0)

    assert frame.size == (720, 1280)


def test_visual_falls_back_when_multi_line_steps_need_the_space():
    theme = load_theme()
    example_step = _example_spec("time_work.json").steps[0].model_copy(
        update={
            "lines": ["1 / 12 = 1/12 work/day"] * 4,
            "visual": VisualSpec(name="bar_chart"),
        }
    )
    scene = StepScene(example_step, 1, 3, theme)

    with pytest.warns(RuntimeWarning, match="Not enough room"):
        frame = scene.render_frame(2.0)

    assert frame.size == (720, 1280)
