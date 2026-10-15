import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from solution_video.llm import JsonProvider
from solution_video.pipeline import generate_steps
from solution_video.schema import QuestionInput, SolutionSpec
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


def test_gate_blocks_self_consistent_but_wrong_answer():
    spec = _spec()
    wrong_question = spec.question_input.model_dump(mode="python")
    wrong_question["final_answer"] = "90 km/h"
    wrong_question["correct_option"] = "B"
    wrong_question = QuestionInput.model_validate(wrong_question)
    wrong_spec = spec.model_copy(update={
        "question_input": wrong_question,
        "answer": spec.answer.model_copy(update={"display": "90 km/h", "correct_option": "B"}),
    })

    result = verify(wrong_question, wrong_spec)

    assert not result.passed
    assert any("Last evaluated step result 72" in reason for reason in result.reasons)


def test_gate_blocks_generic_formula_lines_without_evaluable_math():
    spec = _spec()
    generic_steps = [
        step.model_copy(update={"lines": ["Speed = distance / time"]})
        for step in spec.steps
    ]

    result = verify(spec.question_input, spec.model_copy(update={"steps": generic_steps}))

    assert not result.passed
    assert any("no machine-evaluable arithmetic equality" in reason for reason in result.reasons)


def test_gate_requires_an_evaluable_equation_in_each_step():
    spec = _spec()
    steps = list(spec.steps)
    steps[1] = steps[1].model_copy(update={"lines": ["Speed = distance / time"]})

    result = verify(spec.question_input, spec.model_copy(update={"steps": steps}))

    assert not result.passed
    assert any("Step 2 has no machine-evaluable arithmetic equality" in reason for reason in result.reasons)


class _MockProvider(JsonProvider):
    def __init__(self, payload: dict | list[dict]):
        self.payloads = payload if isinstance(payload, list) else [payload]
        self.calls = 0

    def complete(self, prompt: str) -> str:
        payload = self.payloads[min(self.calls, len(self.payloads) - 1)]
        self.calls += 1
        return json.dumps(payload)


def test_generated_wrong_answer_is_blocked_by_mock_provider(monkeypatch):
    import solution_video.pipeline as pipeline

    monkeypatch.setattr(pipeline.time, "sleep", lambda _delay: None)
    spec = _spec()
    payload = spec.model_dump(mode="json")
    payload.pop("question_input")
    payload["answer"]["display"] = "90 km/h"
    with pytest.raises(ValueError, match="Accuracy gate"):
        generate_steps(spec.question_input, _MockProvider(payload))


def test_cli_returns_exit_2_for_self_consistent_but_wrong_input(monkeypatch, tmp_path):
    import solution_video.cli as cli
    import solution_video.pipeline as pipeline

    monkeypatch.setattr(pipeline.time, "sleep", lambda _delay: None)
    spec = _spec()
    wrong_question = spec.question_input.model_dump(mode="python")
    wrong_question["final_answer"] = "90 km/h"
    wrong_question["correct_option"] = "B"
    input_payload = wrong_question
    input_path = tmp_path / "wrong.json"
    input_path.write_text(json.dumps(input_payload), encoding="utf-8")
    generated = spec.model_dump(mode="json")
    generated.pop("question_input")
    generated["answer"].update({"display": "90 km/h", "correct_option": "B"})

    class _WrongAnswerProvider(JsonProvider):
        def complete(self, prompt: str) -> str:
            return json.dumps(generated)

    monkeypatch.setattr(cli, "GroqProvider", _WrongAnswerProvider)
    output_path = tmp_path / "solution.mp4"

    exit_code = cli.main([
        "render-from-today", "--input", str(input_path), "--out", str(output_path),
    ])

    meta = json.loads(output_path.with_suffix(".meta.json").read_text(encoding="utf-8"))
    assert exit_code == 2
    assert meta["answer_verified"] is False
    assert not output_path.exists()


def test_cli_exits_3_after_three_rate_limit_attempts(monkeypatch, tmp_path, capsys):
    import solution_video.cli as cli
    import solution_video.pipeline as pipeline
    from solution_video.llm.base import RateLimitError

    monkeypatch.setattr(pipeline.time, "sleep", lambda _delay: None)
    spec = _spec()
    question_payload = spec.question_input.model_dump(mode="json")
    question_payload["day"] = 999
    input_path = tmp_path / "question.json"
    input_path.write_text(
        json.dumps(question_payload),
        encoding="utf-8",
    )

    class _RateLimitedProvider(JsonProvider):
        calls = 0

        def complete(self, prompt: str) -> str:
            self.calls += 1
            raise RateLimitError("Groq request was rate limited (HTTP 429)", retry_after_s=1)

    provider = _RateLimitedProvider()
    monkeypatch.setattr(cli, "GroqProvider", lambda: provider)

    exit_code = cli.main([
        "steps", "--input", str(input_path), "--out", str(tmp_path / "steps.json"),
    ])

    assert exit_code == 3
    assert provider.calls == 3
    assert "Rate limit persisted after 3 attempts" in capsys.readouterr().err


def test_schema_rejects_invented_source_and_missing_answer():
    payload = _spec().model_dump(mode="json")
    payload["steps"][0]["source"] = "invented source"
    with pytest.raises(ValidationError):
        SolutionSpec.model_validate(payload)


def test_generator_repairs_schema_once_with_mock_provider(monkeypatch):
    import solution_video.pipeline as pipeline

    monkeypatch.setattr(pipeline.time, "sleep", lambda _delay: None)
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


def test_schema_repair_prompt_contains_exact_validation_error(monkeypatch, capsys):
    import solution_video.pipeline as pipeline

    monkeypatch.setattr(pipeline.time, "sleep", lambda _delay: None)
    spec = _spec()
    malformed = spec.model_dump(mode="json")
    malformed.pop("question_input")
    malformed["answer"].pop("speech")
    repaired = spec.model_dump(mode="json")
    repaired.pop("question_input")

    class _CaptureProvider(JsonProvider):
        prompts = []
        payloads = [malformed, repaired]

        def complete(self, prompt: str) -> str:
            self.prompts.append(prompt)
            return json.dumps(self.payloads.pop(0))

    provider = _CaptureProvider()
    result = generate_steps(spec.question_input, provider)

    assert result.answer.speech
    exact_error = "Field required"
    assert exact_error in provider.prompts[1]
    invalid_payload = dict(malformed, question_input=spec.question_input.model_dump(mode="json"))
    with pytest.raises(ValidationError) as validation_error:
        SolutionSpec.model_validate(invalid_payload)
    assert provider.prompts[1].endswith(f"Exact validation error:\n{validation_error.value}")
    diagnostic = capsys.readouterr().err
    assert "answer.speech" in diagnostic
    assert '"<missing>"' in diagnostic


def test_steps_cache_skips_provider_after_success(monkeypatch, tmp_path):
    import solution_video.pipeline as pipeline

    monkeypatch.setattr(pipeline.time, "sleep", lambda _delay: None)
    spec = _spec()
    payload = spec.model_dump(mode="json")
    payload.pop("question_input")

    class _Provider(JsonProvider):
        calls = 0

        def complete(self, prompt: str) -> str:
            self.calls += 1
            return json.dumps(payload)

    provider = _Provider()
    cache_dir = tmp_path / "step-cache"
    first = generate_steps(spec.question_input, provider, cache_dir=cache_dir)
    second = generate_steps(spec.question_input, provider, cache_dir=cache_dir)

    assert first == second
    assert provider.calls == 1
    assert len(list(cache_dir.glob("*.json"))) == 1


def test_schema_repair_stops_after_two_repairs(monkeypatch):
    import solution_video.pipeline as pipeline

    monkeypatch.setattr(pipeline.time, "sleep", lambda _delay: None)
    spec = _spec()
    malformed = spec.model_dump(mode="json")
    malformed.pop("question_input")
    malformed["answer"].pop("speech")

    class _AlwaysInvalidProvider(JsonProvider):
        calls = 0

        def complete(self, prompt: str) -> str:
            self.calls += 1
            return json.dumps(malformed)

    provider = _AlwaysInvalidProvider()

    with pytest.raises(ValueError, match="after 2 repairs"):
        generate_steps(spec.question_input, provider)

    assert provider.calls == 3


def test_rate_limits_and_schema_repairs_share_three_attempt_budget(monkeypatch):
    import solution_video.pipeline as pipeline
    from solution_video.llm.base import RateLimitError

    monkeypatch.setattr(pipeline.time, "sleep", lambda _delay: None)
    spec = _spec()
    malformed = spec.model_dump(mode="json")
    malformed.pop("question_input")
    malformed["answer"].pop("speech")

    class _MixedFailureProvider(JsonProvider):
        calls = 0

        def complete(self, prompt: str) -> str:
            self.calls += 1
            if self.calls == 1:
                raise RateLimitError("rate limited", retry_after_s=1)
            return json.dumps(malformed)

    provider = _MixedFailureProvider()
    with pytest.raises(ValueError, match="exhausted 3 API attempts"):
        generate_steps(spec.question_input, provider)

    assert provider.calls == 3
