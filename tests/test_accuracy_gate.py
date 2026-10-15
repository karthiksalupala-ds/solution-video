import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from solution_video.llm import JsonProvider
from solution_video.pipeline import generate_steps
from solution_video.schema import SolutionSpec
from solution_video.verify import verify


ROOT = Path(__file__).resolve().parents[1]


def _spec() -> SolutionSpec:
    return SolutionSpec.from_payload(json.loads((ROOT / "examples" / "speed_train.json").read_text(encoding="utf-8")))


def test_gate_accepts_checked_example():
    spec = _spec()
    assert verify(spec.question_input, spec).passed


def test_gate_blocks_wrong_answer_and_arithmetic():
    spec = _spec().model_copy(update={"answer": _spec().answer.model_copy(update={"display": "90 km/h"})})
    result = verify(spec.question_input, spec)
    assert not result.passed and any("Generated answer" in reason for reason in result.reasons)
    step = _spec().steps[1].model_copy(update={"lines": ["400 / 20 = 30"]})
    altered = _spec().model_copy(update={"steps": [_spec().steps[0], step, _spec().steps[2]]})
    result = verify(altered.question_input, altered)
    assert not result.passed and any("arithmetic is false" in reason for reason in result.reasons)


class _MockProvider(JsonProvider):
    def __init__(self, payload: dict | list[dict]):
        self.payloads = payload if isinstance(payload, list) else [payload]
        self.calls = 0

    def complete(self, prompt: str) -> str:
        payload = self.payloads[min(self.calls, len(self.payloads) - 1)]
        self.calls += 1
        return json.dumps(payload)


def test_generated_wrong_answer_is_blocked_by_mock_provider():
    spec = _spec()
    payload = spec.model_dump(mode="json")
    payload.pop("question_input")
    payload["answer"]["display"] = "90 km/h"
    with pytest.raises(ValueError, match="Accuracy gate"):
        generate_steps(spec.question_input, _MockProvider(payload))


def test_schema_rejects_invented_source_and_missing_answer():
    payload = _spec().model_dump(mode="json")
    payload["steps"][0]["source"] = "invented source"
    with pytest.raises(ValidationError):
        SolutionSpec.model_validate(payload)


def test_generator_repairs_schema_once_with_mock_provider():
    spec = _spec()
    malformed = spec.model_dump(mode="json")
    malformed.pop("question_input")
    malformed["tip"] = "not an object"
    repaired = spec.model_dump(mode="json")
    repaired.pop("question_input")
    provider = _MockProvider([malformed, repaired])
    assert generate_steps(spec.question_input, provider).answer.display == "72 km/h"
    assert provider.calls == 2
    payload = _spec().model_dump(mode="json")
    payload.pop("answer")
    with pytest.raises(ValidationError):
        SolutionSpec.model_validate(payload)
