import json
from pathlib import Path

import pytest

from solution_video.verify.arithmetic import verify_line


CASES = json.loads((Path(__file__).parent / "fixtures" / "verification_cases.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", CASES)
def test_verification_dataset(case):
    assert verify_line(case["line"]) is case["valid"]


def test_safe_arithmetic_accepts_and_rejects_equalities():
    assert verify_line("150 + 250 = 400") is True
    assert verify_line("20 / 80 * 100 = 25") is True
    assert verify_line("A useful sentence") is None
    assert verify_line("__import__('os') = 1") is None
