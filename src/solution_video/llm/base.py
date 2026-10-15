"""Provider-neutral, strict JSON generation helpers."""

from __future__ import annotations

import json
import re
import time
from abc import ABC, abstractmethod
from typing import Any
from pathlib import Path


class LLMError(RuntimeError):
    """A provider, response-format, or retry failure."""


def extract_json(text: str) -> dict[str, Any]:
    """Parse a JSON object, accepting a single Markdown code fence."""
    cleaned = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", text.strip(), flags=re.IGNORECASE)
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise LLMError("Provider returned invalid JSON") from exc
    if not isinstance(value, dict):
        raise LLMError("Provider JSON response must be an object")
    return value


class JsonProvider(ABC):
    """Implement one network call; shared retry/JSON behavior lives here."""

    @abstractmethod
    def complete(self, prompt: str) -> str: ...

    def generate_json(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                payload = extract_json(self.complete(prompt))
                # Schema is carried to providers and callers; model validation remains authoritative.
                if not isinstance(schema, dict):
                    raise LLMError("Invalid requested response schema")
                return payload
            except (LLMError, OSError) as exc:
                last_error = exc
                if attempt < 2:
                    time.sleep(0.5 * (2**attempt))
        raise LLMError(f"Generation failed after 3 attempts: {last_error}")


def prompt_for_question(question: dict[str, Any]) -> str:
    """Load the prompt from disk and append caller-owned question data."""
    prompt_path = Path(__file__).with_name("prompts") / "solution_to_steps.md"
    try:
        instructions = prompt_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise LLMError("Solution-to-steps prompt file is missing") from exc
    return f"{instructions}\n\nINPUT JSON:\n{json.dumps(question, ensure_ascii=False)}"
