import json
from pathlib import Path

from solution_video import __version__
from solution_video.cli import main

ROOT = Path(__file__).resolve().parents[1]


def test_version():
    assert __version__


def test_cli_help_ok():
    assert main([]) == 0


def test_examples_are_valid_json_with_required_fields():
    for f in (ROOT / "examples").glob("*.json"):
        d = json.loads(f.read_text(encoding="utf-8"))
        assert len(d["options"]) == 4 and d["correct_option"] in "ABCD" and d["final_answer"]


def test_fonts_present():
    for name in ("Bold", "Medium", "Regular"):
        assert (ROOT / "fonts" / f"Poppins-{name}.ttf").exists()
