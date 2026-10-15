import json
from pathlib import Path

import pytest

from solution_video.verify.arithmetic import equation_result, numeric_answer, verify_line


CASES = json.loads((Path(__file__).parent / "fixtures" / "verification_cases.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", CASES)
def test_verification_dataset(case):
    assert verify_line(case["line"]) is case["valid"]


def test_safe_arithmetic_accepts_and_rejects_equalities():
    assert verify_line("150 + 250 = 400") is True
    assert verify_line("20 / 80 * 100 = 25") is True
    assert verify_line("A useful sentence") is None
    assert verify_line("__import__('os') = 1") is None


def test_percent_equation_result_matches_percent_answer():
    assert verify_line("20 / 80 * 100 = 25%") is True
    assert equation_result("20 / 80 * 100 = 25%") == 25
    assert numeric_answer("25%") == 25


def test_numeric_answer_ignores_units_and_supports_fractions():
    assert numeric_answer("72 km/h") == 72
    assert numeric_answer("8 days") == 8
    assert numeric_answer("1/8 days") == 0.125
    assert verify_line("150 + 250 = 400 m") is True
    assert verify_line("1 / 12 = 1/12 work/day") is True
