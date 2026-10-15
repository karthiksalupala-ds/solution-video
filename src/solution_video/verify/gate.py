"""Blocking gate: a failure produces reasons, never a video permission."""

from __future__ import annotations

from dataclasses import dataclass

from ..schema import QuestionInput, SolutionSpec
from .answers import answers_match
from .arithmetic import verify_line


@dataclass(frozen=True)
class GateResult:
    passed: bool
    reasons: tuple[str, ...]


def verify(question: QuestionInput, spec: SolutionSpec) -> GateResult:
    reasons: list[str] = []
    expected_option = question.options[ord(question.correct_option) - ord("A")]
    if not answers_match(spec.answer.display, question.final_answer):
        reasons.append("Generated answer does not match final_answer")
    if not answers_match(expected_option, question.final_answer):
        reasons.append("correct_option does not match final_answer")
    if spec.answer.correct_option and spec.answer.correct_option != question.correct_option:
        reasons.append("Generated correct_option differs from input")
    for step_index, step in enumerate(spec.steps, 1):
        if step.visual and step.visual.name and step.visual.data.get("source"):
            reasons.append(f"Step {step_index} contains unapproved source data")
        for line_index, line in enumerate(step.lines, 1):
            valid = verify_line(line)
            if valid is False:
                reasons.append(f"Step {step_index} line {line_index} arithmetic is false: {line}")
    return GateResult(not reasons, tuple(reasons))
