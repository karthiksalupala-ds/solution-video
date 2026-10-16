"""Validated, content-only contracts for question and solution videos."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator


OptionId = Literal["A", "B", "C", "D"]


class Source(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str = Field(min_length=1, max_length=120)
    url: HttpUrl | None = None
    verified: Literal[True]


class QuestionInput(BaseModel):
    """The authoritative daily-question payload, independent of rendering."""

    model_config = ConfigDict(extra="forbid")
    day: int = Field(ge=1, le=999)
    topic: str = Field(min_length=1, max_length=80)
    question: str = Field(min_length=1, max_length=420)
    options: list[str] = Field(min_length=4, max_length=4)
    correct_option: OptionId
    final_answer: str = Field(min_length=1, max_length=100)
    solution: str | None = Field(default=None, max_length=2_000)
    difficulty: Literal["Easy", "Medium", "Hard"] | None = None
    time_sec: int | None = Field(default=None, ge=30, le=75)
    source: Source | None = None

    @field_validator("options", mode="before")
    @classmethod
    def normalize_option_objects(cls, value: Any) -> Any:
        if isinstance(value, list):
            return [item.get("display", "") if isinstance(item, dict) else item for item in value]
        return value

    @field_validator("options")
    @classmethod
    def validate_options(cls, value: list[str]) -> list[str]:
        clean = [item.strip() for item in value]
        if any(not item or len(item) > 110 for item in clean):
            raise ValueError("Each option must contain 1-110 display characters")
        if len({item.casefold() for item in clean}) != 4:
            raise ValueError("Options must be distinct")
        return clean

    @model_validator(mode="after")
    def option_matches_final_answer(self) -> "QuestionInput":
        actual = self.options[ord(self.correct_option) - ord("A")]
        if _normalise_answer(actual) != _normalise_answer(self.final_answer):
            raise ValueError("correct_option must point to final_answer")
        return self


class VisualSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=48)
    data: dict[str, Any] = Field(default_factory=dict)


class StepSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str = Field(min_length=1, max_length=80)
    lines: list[str] = Field(min_length=1, max_length=4)
    speech: str = Field(min_length=1, max_length=600)
    emphasis: str | None = Field(default=None, max_length=80)
    visual: VisualSpec | None = None

    @field_validator("lines")
    @classmethod
    def validate_lines(cls, value: list[str]) -> list[str]:
        clean = [line.strip() for line in value]
        if any(not line or len(line) > 90 for line in clean):
            raise ValueError("Each display line must contain 1-90 characters")
        return clean


class AnswerSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    display: str = Field(min_length=1, max_length=100)
    speech: str = Field(min_length=1, max_length=300)
    correct_option: OptionId | None = None


class TipSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    display: str = Field(min_length=1, max_length=180)
    speech: str | None = Field(default=None, max_length=400)


class VoiceClipMeta(BaseModel):
    """Non-secret accounting details for one synthesized scene."""

    model_config = ConfigDict(extra="forbid")
    scene: str
    provider: str
    model: str
    characters: int = Field(ge=0)
    credits: int = Field(ge=0)


class SolutionSpec(BaseModel):
    """A render-ready solution paired with its authoritative question."""

    model_config = ConfigDict(extra="forbid")
    question_input: QuestionInput
    steps: list[StepSpec] = Field(min_length=1, max_length=8)
    answer: AnswerSpec
    tip: TipSpec | None = None
    cta: TipSpec | None = None
    seed: int = Field(default=1, ge=0, le=2**31 - 1)

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "SolutionSpec":
        """Accept the canonical contract and the checked-in example shape."""
        if "question_input" in payload:
            return cls.model_validate(payload)
        expected = payload.get("expected_steps")
        if not isinstance(expected, dict):
            raise ValueError("Expected steps JSON with question_input, or a today.json payload containing expected_steps")
        question_fields = {key: value for key, value in payload.items() if key != "expected_steps"}
        answer = expected.get("answer", payload.get("final_answer"))
        steps = []
        for raw_step in expected.get("steps", []):
            step = dict(raw_step)
            if isinstance(step.get("visual"), str):
                step["visual"] = {"name": step["visual"]}
            steps.append(step)
        return cls.model_validate({
            "question_input": question_fields,
            "steps": steps,
            "answer": {
                "display": answer,
                "speech": expected.get("answer_speech", ""),
                "correct_option": payload.get("correct_option"),
            },
            "tip": {"display": expected["tip"]} if expected.get("tip") else None,
            "seed": payload.get("day", 1),
        })


class Meta(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str
    duration_s: float = Field(ge=0)
    size_bytes: int = Field(ge=0)
    answer_verified: bool
    status: Literal["ok", "blocked"] = "ok"
    reasons: list[str] = Field(default_factory=list)
    voice_provider: str | None = None
    voice_model: str | None = None
    voice_language_mode: str | None = None
    voice_characters: int = Field(default=0, ge=0)
    voice_credits: int = Field(default=0, ge=0)
    voice_clips: list[VoiceClipMeta] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    version: str = "0.1.0"


def _normalise_answer(value: str) -> str:
    compact = "".join(value.casefold().replace(",", "").split())
    match = re.fullmatch(r"([+-]?\d+(?:\.\d+)?)(?:[a-z/]+)?", compact)
    return match.group(1) if match else compact
