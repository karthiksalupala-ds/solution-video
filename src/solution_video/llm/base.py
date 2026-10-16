"""Provider-neutral, strict JSON generation helpers."""

from __future__ import annotations

import json
import os
import re
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Literal
from pathlib import Path


class LLMError(RuntimeError):
    """A provider, response-format, or retry failure."""


class RateLimitError(LLMError):
    """A provider rate-limit response, optionally carrying Retry-After seconds."""

    def __init__(self, message: str, retry_after_s: float | None = None) -> None:
        super().__init__(message)
        self.retry_after_s = retry_after_s


class JsonModeValidationError(LLMError):
    """Groq JSON mode rejected a generated response and can be retried once."""

    def __init__(self, message: str, failed_generation: str | None, fallback_available: bool) -> None:
        super().__init__(message)
        self.failed_generation = failed_generation
        self.fallback_available = fallback_available


class JsonParseError(LLMError):
    """The provider response was not a JSON object after fence stripping."""

    def __init__(self, message: str, response_text: str) -> None:
        super().__init__(message)
        self.response_text = response_text


SpeechLanguageMode = Literal["english", "tanglish_latin", "telugu_script", "mixed"]
SPEECH_LANGUAGE_MODES = ("english", "tanglish_latin", "telugu_script", "mixed")


def resolve_speech_language_mode(mode: str | None = None) -> SpeechLanguageMode:
    """Resolve the configured narration mode and reject unsupported values."""
    selected = os.getenv("SPEECH_LANGUAGE_MODE", "english") if mode is None else mode
    if selected == "english":
        return "english"
    if selected == "tanglish_latin":
        return "tanglish_latin"
    if selected == "telugu_script":
        return "telugu_script"
    if selected == "mixed":
        return "mixed"
    raise ValueError(
        "SPEECH_LANGUAGE_MODE must be one of: " + ", ".join(SPEECH_LANGUAGE_MODES)
    )


def retry_after_seconds(value: str | None) -> float | None:
    """Parse Retry-After as seconds or an HTTP date."""
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        try:
            retry_at = parsedate_to_datetime(value)
            if retry_at.tzinfo is None:
                retry_at = retry_at.replace(tzinfo=timezone.utc)
            return max(0.0, (retry_at - datetime.now(timezone.utc)).total_seconds())
        except (TypeError, ValueError, OverflowError):
            return None


def rate_limit_delay(attempt: int, retry_after_s: float | None) -> float:
    """Use a capped exponential delay without retrying before Retry-After."""
    exponential_delay = min(30.0, 1.0 * (2**attempt))
    return max(exponential_delay, retry_after_s or 0.0)


def extract_json(text: str) -> dict[str, Any]:
    """Parse a JSON object, accepting a single Markdown code fence."""
    cleaned = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", text.strip(), flags=re.IGNORECASE)
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise JsonParseError("Provider returned invalid JSON", text) from exc
    if not isinstance(value, dict):
        raise LLMError("Provider JSON response must be an object")
    return value


class JsonProvider(ABC):
    """Implement one network call; shared retry/JSON behavior lives here."""

    @abstractmethod
    def complete(self, prompt: str) -> str: ...

    def generate_json(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(schema, dict):
            raise LLMError("Invalid requested response schema")
        try:
            return extract_json(self.complete(prompt))
        except OSError as exc:
            raise LLMError("Provider request failed") from exc


def prompt_for_question(
    question: dict[str, Any],
    speech_language_mode: str | None = None,
) -> str:
    """Load the prompt from disk and append caller-owned question data."""
    prompt_path = Path(__file__).with_name("prompts") / "solution_to_steps.md"
    try:
        instructions = prompt_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise LLMError("Solution-to-steps prompt file is missing") from exc
    mode = resolve_speech_language_mode(speech_language_mode)
    mode_instructions = {
        "english": "Use natural English only; do not insert Telugu or Tanglish.",
        "tanglish_latin": "Use conversational Telugu written in Latin script, retaining technical English terms naturally.",
        "telugu_script": "Use natural Telugu written in Telugu script, retaining standard technical terms as needed.",
        "mixed": "Use Telugu in Telugu script, but keep technical English terms in Latin script.",
    }
    return (
        f"{instructions}\n\n"
        "SPEECH LANGUAGE CONFIGURATION\n"
        f"Mode: {mode}\n"
        f"{mode_instructions[mode]}\n"
        "Apply this mode consistently to every steps[*].speech, tip.speech, "
        "answer.speech, and any outro/CTA speech. Keep all display text separate "
        "from speech. Spell numbers in speakable words in the selected mode; "
        "say x as times, / as divided by, % as percent, and km/h as kilometres "
        "per hour. Do not read raw calculation symbols aloud.\n\n"
        f"INPUT JSON:\n{json.dumps(question, ensure_ascii=False)}"
    )
