"""Blocking gate: a failure produces reasons, never a video permission."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import re

from ..schema import QuestionInput, SolutionSpec
from .answers import answers_match
from .arithmetic import (
    equation_has_computation,
    equation_operands,
    equation_result,
    numeric_answer,
    verify_line,
)


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
    if not spec.answer.speech.strip():
        reasons.append("Generated answer is missing spoken narration")
    expected_result = numeric_answer(question.final_answer)
    evaluated_results = []
    first_evaluable_lines: list[str] | None = None
    for step_index, step in enumerate(spec.steps, 1):
        if step.visual and step.visual.name and step.visual.data.get("source"):
            reasons.append(f"Step {step_index} contains unapproved source data")
        step_results = []
        step_evaluable_lines: list[str] = []
        for line_index, line in enumerate(step.lines, 1):
            valid = verify_line(line)
            if valid is False:
                reasons.append(f"Step {step_index} line {line_index} arithmetic is false: {line}")
            elif valid is True:
                if not equation_has_computation(line):
                    reasons.append(
                        f"Step {step_index} line {line_index} is a tautology/filler, not a computation: {line}"
                    )
                    continue
                result = equation_result(line)
                if result is not None:
                    step_results.append(result)
                    step_evaluable_lines.append(line)
        if not step_results:
            reasons.append(f"Step {step_index} has no machine-evaluable arithmetic equality")
        elif first_evaluable_lines is None:
            first_evaluable_lines = step_evaluable_lines
        evaluated_results.extend(step_results)
    if first_evaluable_lines:
        grounded = _question_numbers(question.question)
        standard_operands = {
            Decimal("1"),
            Decimal("100"),
            Decimal("60"),
            Decimal("3600"),
            Decimal("1000"),
        }
        for line in first_evaluable_lines:
            operands = equation_operands(line) or ()
            line_constants = set(standard_operands)
            if re.search(r"(?<!\d)(?:18\s*/\s*5|5\s*/\s*18)(?!\d)", line):
                line_constants.update((Decimal("18"), Decimal("5")))
            ungrounded = sorted({
                operand for operand in operands
                if operand not in grounded and operand not in line_constants
            })
            if ungrounded:
                values = ", ".join(_format_number(value) for value in ungrounded)
                reasons.append(
                    f"First evaluable step uses operands absent from the question or standard constants: {values}"
                )
    if expected_result is None:
        reasons.append("final_answer has no supported numeric value")
    if not evaluated_results:
        reasons.append("Steps contain no machine-evaluable arithmetic equality")
    elif expected_result is not None and abs(evaluated_results[-1] - expected_result) > Decimal("0.000001"):
        reasons.append(
            f"Last evaluated step result {evaluated_results[-1]} does not match "
            f"numeric final_answer {expected_result}"
        )
    return GateResult(not reasons, tuple(reasons))


def _question_numbers(text: str) -> set[Decimal]:
    values: set[Decimal] = set()
    for token in re.findall(r"(?<![\w.])[+-]?\d[\d,]*(?:\.\d+)?(?!\w)", text):
        try:
            values.add(Decimal(token.replace(",", "")))
        except ArithmeticError:
            continue
    return values


def _format_number(value: Decimal) -> str:
    return format(value.normalize(), "f")
