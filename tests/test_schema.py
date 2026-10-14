import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from solution_video.schema import QuestionInput, SolutionSpec


ROOT = Path(__file__).resolve().parents[1]


def test_checked_in_examples_normalise_to_solution_specs():
    for path in ROOT.joinpath("examples").glob("*.json"):
        if path.name != "hello.json":
            assert SolutionSpec.from_payload(json.loads(path.read_text(encoding="utf-8"))).steps


def test_wrong_correct_option_is_rejected():
    with pytest.raises(ValidationError, match="correct_option"):
        QuestionInput(day=1, topic="T", question="Q", options=["1", "2", "3", "4"], correct_option="A", final_answer="2")
