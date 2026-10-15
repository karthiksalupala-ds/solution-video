"""Canonical answer comparisons used by the blocking verification gate."""

from __future__ import annotations

import re


def normalise_answer(value: str) -> str:
    """Normalize superficial spacing, commas, units and simple fractions."""
    compact = "".join(value.casefold().replace(",", "").split())
    compact = compact.replace("percentage", "%").replace("percent", "%")
    fraction = re.fullmatch(r"([+-]?\d+)\s*/\s*(\d+)", compact)
    if fraction:
        return f"{int(fraction.group(1))}/{int(fraction.group(2))}"
    numeric = re.fullmatch(r"([+-]?\d+(?:\.\d+)?)(?:[a-z/%]+)?", compact)
    return numeric.group(1) if numeric else compact


def answers_match(left: str, right: str) -> bool:
    return normalise_answer(left) == normalise_answer(right)
