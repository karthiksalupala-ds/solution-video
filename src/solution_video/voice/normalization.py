"""Config-driven speech text normalization."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path


class SpeechNormalizationError(ValueError):
    """Raised when a language mode has no speech-normalization rules."""


@lru_cache(maxsize=1)
def _rules() -> dict[str, dict[str, dict[str, str]]]:
    path = Path(__file__).with_name("normalization.json")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SpeechNormalizationError(f"Unable to load speech normalization rules: {exc}") from exc
    if not isinstance(data, dict):
        raise SpeechNormalizationError("Speech normalization rules must be a JSON object")
    return data


def normalize_speech(text: str, language_mode: str = "english") -> str:
    """Expand common symbols, units, and numeric values using mode-specific rules."""
    mode_rules = _rules().get(language_mode)
    if mode_rules is None:
        raise SpeechNormalizationError(f"Unsupported speech language mode: {language_mode}")
    result = text
    symbols = mode_rules.get("symbols", {})
    for symbol in sorted(symbols, key=len, reverse=True):
        result = re.sub(
            rf"(?i)(?<![A-Za-z]){re.escape(symbol)}(?![A-Za-z])",
            symbols[symbol],
            result,
        )
    result = re.sub(r"(?<=\d)\s*[xX*]\s*(?=\d)", " times ", result)
    result = re.sub(r"(?<=\d)\s*/\s*(?=\d)", " divided by ", result)
    for contraction, expansion in mode_rules.get("contractions", {}).items():
        result = re.sub(rf"(?i)\b{re.escape(contraction)}\b", expansion, result)
    result = re.sub(r"(?<![\w.])-?\d+(?:,\d{3})*(?:\.\d+)?", _number_to_words_match, result)
    return re.sub(r"\s+", " ", result).strip()


def _number_to_words_match(match: re.Match[str]) -> str:
    return number_to_words(match.group(0))


def number_to_words(value: str) -> str:
    """Speak integer or decimal digits in English without changing their value."""
    clean = value.replace(",", "")
    negative = clean.startswith("-")
    if negative:
        clean = clean[1:]
    if "." in clean:
        whole, fractional = clean.split(".", 1)
        words = f"{_integer_to_words(int(whole))} point {' '.join(_ONES[int(digit)] for digit in fractional)}"
    else:
        words = _integer_to_words(int(clean))
    return f"minus {words}" if negative else words


_ONES = (
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
    "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
    "seventeen", "eighteen", "nineteen",
)
_TENS = ("", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety")


def _integer_to_words(value: int) -> str:
    if value < 20:
        return _ONES[value]
    if value < 100:
        quotient, remainder = divmod(value, 10)
        return _TENS[quotient] if remainder == 0 else f"{_TENS[quotient]} {_ONES[remainder]}"
    if value < 1_000:
        quotient, remainder = divmod(value, 100)
        return f"{_ONES[quotient]} hundred" if remainder == 0 else f"{_ONES[quotient]} hundred {_integer_to_words(remainder)}"
    if value < 1_000_000:
        quotient, remainder = divmod(value, 1_000)
        prefix = f"{_integer_to_words(quotient)} thousand"
        return prefix if remainder == 0 else f"{prefix} {_integer_to_words(remainder)}"
    return " ".join(_ONES[int(digit)] for digit in str(value))
