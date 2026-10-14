"""Asset loading helpers that fail clearly instead of falling back to system fonts."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from PIL import ImageFont

from .theme import Theme


@dataclass
class FontBook:
    """Per-render font cache; keys are immutable font role and pixel size."""

    theme: Theme
    _fonts: dict[tuple[str, int], ImageFont.FreeTypeFont] = field(default_factory=dict)

    def get(self, role: str, size: int) -> ImageFont.FreeTypeFont:
        if role not in self.theme.fonts:
            raise ValueError(f"Unknown font role: {role}")
        if size < 1:
            raise ValueError("Font size must be positive")
        key = (role, size)
        if key not in self._fonts:
            path: Path = self.theme.fonts[role]
            try:
                self._fonts[key] = ImageFont.truetype(path, size=size)
            except OSError as exc:
                raise ValueError(f"Unable to load bundled font {path}") from exc
        return self._fonts[key]
