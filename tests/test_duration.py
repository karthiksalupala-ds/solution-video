import json
from pathlib import Path

from solution_video.engine.theme import load_theme
from solution_video.pipeline import plan_scenes
from solution_video.schema import SolutionSpec


ROOT = Path(__file__).resolve().parents[1]


def test_duration_is_capped_and_catalog_is_complete():
    spec = SolutionSpec.from_payload(json.loads((ROOT / "examples" / "speed_train.json").read_text(encoding="utf-8")))
    plan = plan_scenes(spec, load_theme())
    assert [item.name for item in plan] == ["title", "question", "step", "step", "step", "tip", "answer"]
    assert sum(item.duration_s for item in plan) <= 75
