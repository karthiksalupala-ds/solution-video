"""Measured text layout and reveal utilities."""

from __future__ import annotations

from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageFont


@dataclass(frozen=True)
class TextLayout:
    lines: tuple[str, ...]
    font_size: int
    width: int
    height: int


def wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> tuple[str, ...]:
    if max_width <= 0:
        raise ValueError("max_width must be positive")
    words = text.split()
    if not words:
        return ("",)
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        if font.getlength(candidate) <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return tuple(lines)


def fit_text(text: str, font_path: str, max_width: int, max_height: int, start_size: int, min_size: int, max_lines: int) -> TextLayout:
    """Find the largest fitting size or raise rather than silently clipping."""
    for size in range(start_size, min_size - 1, -1):
        font = ImageFont.truetype(font_path, size)
        lines = wrap_text(text, font, max_width)
        bbox = font.getbbox("Ag")
        line_height = bbox[3] - bbox[1]
        width = max((round(font.getlength(line)) for line in lines), default=0)
        height = line_height * len(lines)
        if len(lines) <= max_lines and height <= max_height:
            return TextLayout(lines, size, width, height)
    raise ValueError("Text does not fit within the requested bounds at the minimum font size")


def draw_text(draw: ImageDraw.ImageDraw, xy: tuple[float, float], text: str, font: ImageFont.FreeTypeFont, fill: tuple[int, int, int, int], *, anchor: str = "la", stroke_width: int = 0, stroke_fill: tuple[int, int, int, int] | None = None) -> None:
    draw.text(xy, text, font=font, fill=fill, anchor=anchor, stroke_width=stroke_width, stroke_fill=stroke_fill)


def reveal_words(text: str, progress: float) -> str:
    words = text.split()
    count = min(len(words), max(0, round(len(words) * max(0.0, min(1.0, progress)))))
    return " ".join(words[:count])


def reveal_chars(text: str, progress: float) -> str:
    count = min(len(text), max(0, round(len(text) * max(0.0, min(1.0, progress)))))
    return text[:count]
