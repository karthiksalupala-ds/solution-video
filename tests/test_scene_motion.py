from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from PIL import Image, ImageChops
import pytest

from solution_video.engine.canvas import Canvas
from solution_video.engine.theme import load_theme
from solution_video.pipeline import PlannedScene, _render_scene_frames, plan_scenes
from solution_video.schema import SolutionSpec
from solution_video.scenes.common import draw_confetti


ROOT = Path(__file__).resolve().parents[1]


class SolidScene:
    def __init__(self, color: tuple[int, int, int]) -> None:
        self.color = color

    def render_frame(self, time_s: float) -> Image.Image:
        return Image.new("RGB", (4, 200), self.color)


def test_scene_transition_crossfades_without_changing_frame_budget():
    theme = load_theme()
    theme = replace(
        theme,
        canvas=replace(theme.canvas, width=4, height=200, fps=10, supersample=1),
        motion={**theme.motion, "scene_transition_s": 0.2},
    )
    plan = (
        PlannedScene("outgoing", SolidScene((255, 0, 0)), 0.5),
        PlannedScene("incoming", SolidScene((0, 0, 255)), 0.5),
    )

    frames = list(_render_scene_frames(plan, theme))

    assert len(frames) == 10
    assert frames[3].getpixel((0, 0)) != (127, 0, 127)
    assert frames[3].getpixel((0, 199)) == (255, 0, 0)
    assert frames[4].getpixel((0, 199)) == (255, 0, 0)
    assert frames[5].getpixel((0, 0)) == (0, 0, 255)


def test_answer_confetti_stays_clear_of_option_rows():
    theme = load_theme()
    canvas = Canvas(theme.canvas.width, theme.canvas.height, background=theme.colors["bg_top"])
    before = canvas.final_rgb()

    draw_confetti(canvas, theme, 0.8, seed=13)

    after = canvas.final_rgb()
    assert ImageChops.difference(
        before.crop((0, round(theme.canvas.height * 0.4), theme.canvas.width, theme.canvas.height)),
        after.crop((0, round(theme.canvas.height * 0.4), theme.canvas.width, theme.canvas.height)),
    ).getbbox() is None


@pytest.mark.parametrize(
    "example",
    ("speed_train.json", "time_work.json", "di_average.json", "percent_increase.json"),
)
def test_core_scenes_render_at_video_dimensions_for_each_example(example: str):
    spec = SolutionSpec.from_payload(
        json.loads((ROOT / "examples" / example).read_text(encoding="utf-8"))
    )
    theme = load_theme()

    for item in plan_scenes(spec, theme):
        frame = item.render_frame(min(item.duration_s * 0.75, 2.0), theme)
        assert frame.size == (720, 1280), f"{example}: {item.name}"
