"""Stable public API for rendering and generating solution videos."""

from __future__ import annotations

import json
from pathlib import Path

from .llm import GeminiProvider, GroqProvider
from .pipeline import generate_steps, render as render_spec, render_from_file
from .schema import Meta, QuestionInput
from .engine.theme import load_theme


def render(
    input_path: str | Path,
    output_path: str | Path,
    *,
    theme_path: str | Path | None = None,
    no_voice: bool = False,
    seed: int | None = None,
    voice_provider: str | None = None,
) -> Meta:
    """Render a validated solution JSON file and return its output metadata."""
    return render_from_file(
        Path(input_path),
        Path(output_path),
        theme_path=theme_path,
        no_voice=no_voice,
        seed=seed,
        voice_provider=voice_provider,
    )


def render_from_today(
    input_path: str | Path,
    output_path: str | Path,
    *,
    provider: str = "groq",
    theme_path: str | Path | None = None,
    no_voice: bool = False,
    seed: int | None = None,
    speech_language_mode: str | None = None,
    voice_provider: str | None = None,
) -> Meta:
    """Generate verified steps for a today-question JSON file, then render it."""
    try:
        payload = json.loads(Path(input_path).read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"Unable to read input JSON: {input_path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid input JSON: {exc.msg}") from exc
    payload.pop("expected_steps", None)
    question = QuestionInput.model_validate(payload)
    if provider == "groq":
        llm = GroqProvider()
    elif provider == "gemini":
        llm = GeminiProvider()
    else:
        raise ValueError("provider must be 'groq' or 'gemini'")
    spec = generate_steps(question, llm, speech_language_mode=speech_language_mode)
    if seed is not None:
        if not 0 <= seed <= 2**31 - 1:
            raise ValueError("seed must be between 0 and 2147483647")
        spec = spec.model_copy(update={"seed": seed})
    return render_spec(
        spec,
        load_theme(Path(theme_path) if theme_path else None),
        Path(output_path),
        no_voice=no_voice,
        voice_provider=voice_provider,
    )
