"""Shared content-free scene drawing helpers."""

from __future__ import annotations

from functools import lru_cache

from ..engine.assets import FontBook
from ..engine.canvas import Canvas
from ..engine.easing import out_cubic, progress_at
from ..engine.text import TextLayout, fit_text
from ..engine.theme import Theme


@lru_cache(maxsize=8)
def _background(width: int, height: int, top: tuple[int, int, int], bottom: tuple[int, int, int]):
    base = Canvas(width, height, background=top)
    base.gradient(top, bottom)
    return base.image


def make_canvas(theme: Theme) -> Canvas:
    canvas = Canvas(theme.canvas.width, theme.canvas.height, background=theme.colors["bg_top"])
    canvas.composite(_background(theme.canvas.width, theme.canvas.height, theme.colors["bg_top"], theme.colors["bg_bottom"]))
    return canvas


def draw_footer(canvas: Canvas, fonts: FontBook, theme: Theme) -> None:
    footer = str(theme.branding.get("footer_text", ""))
    if footer:
        canvas.text((theme.canvas.width / 2, theme.canvas.height - 52), footer, fonts.get("regular", theme.sizes["footer_px"]), (*theme.colors["muted"], 210), anchor="mm")


def draw_header(canvas: Canvas, fonts: FontBook, theme: Theme, title: str, progress: float = 1.0) -> None:
    alpha = round(255 * out_cubic(progress))
    canvas.text((theme.safe_margin_px, 105), title, fonts.get("bold", 30), (*theme.colors["accent"], alpha), anchor="la")


def fit(theme: Theme, role: str, text: str, width: int, height: int, start_size: int, max_lines: int) -> TextLayout:
    return fit_text(text, str(theme.fonts[role]), width, height, start_size, theme.min_body_font_px, max_lines)


def draw_layout(canvas: Canvas, fonts: FontBook, theme: Theme, layout: TextLayout, x: float, y: float, *, role: str, color: str = "text", alpha: int = 255, anchor: str = "la", line_gap: int = 8) -> None:
    font = fonts.get(role, layout.font_size)
    line_height = font.getbbox("Ag")[3] - font.getbbox("Ag")[1] + line_gap
    for index, line in enumerate(layout.lines):
        canvas.text((x, y + index * line_height), line, font, (*theme.colors[color], alpha), anchor=anchor)


def scene_progress(time_s: float, reveal_s: float) -> float:
    return out_cubic(progress_at(time_s, 0.0, reveal_s))
