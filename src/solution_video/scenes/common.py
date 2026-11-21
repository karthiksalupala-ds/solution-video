"""Shared content-free scene drawing helpers."""

from __future__ import annotations

import math
import re
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFilter

from ..engine.assets import FontBook
from ..engine.canvas import Canvas
from ..engine.easing import out_cubic, progress_at
from ..engine.text import TextLayout, fit_text
from ..engine.theme import Theme
from ..styles import StyleContext, resolve_style


STYLE_FALLBACK_EXCEPTIONS = (
    OSError,
    RuntimeError,
    ValueError,
    KeyError,
    TypeError,
    AttributeError,
    IndexError,
)


@lru_cache(maxsize=8)
def _background(width: int, height: int, top: tuple[int, int, int], bottom: tuple[int, int, int]):
    base = Canvas(width, height, background=top)
    base.gradient(top, bottom)
    return base.image


def make_canvas(theme: Theme, time_s: float = 0.0, seed: int = 1) -> Canvas:
    context = StyleContext(theme=theme, seed=seed, time_s=time_s)
    style = resolve_style(theme.style, seed)
    canvas = Canvas(
        theme.canvas.width,
        theme.canvas.height,
        background=theme.colors["bg_top"],
        track_text_mask=bool(getattr(style, "requires_text_mask", False)),
    )
    begin_frame = getattr(style, "begin_frame", None)
    if callable(begin_frame):
        begin_frame(context)
    try:
        style.background(canvas, context)
    except STYLE_FALLBACK_EXCEPTIONS as exc:
        import warnings

        from ..styles import ClassicStyle

        warnings.warn(f"Style {style.name!r} background failed; using classic: {exc}", RuntimeWarning, stacklevel=2)
        ClassicStyle().background(canvas, context)
    if getattr(style, "handles_background_fx", False):
        return canvas
    period = max(1.0, theme.motion.get("background_period_s", 18.0))
    phase = (time_s % period) / period
    glow_bucket = round(phase * 24) % 24
    canvas.composite(_animated_glow(
        theme.canvas.width,
        theme.canvas.height,
        theme.colors["accent"],
        round(theme.motion.get("background_glow_alpha", 15)),
        glow_bucket,
        round(theme.motion.get("background_glow_blur_px", 54)),
    ))
    particle_count = max(0, round(theme.motion.get("background_particle_count", 12)))
    particle_alpha = max(0, min(255, round(theme.motion.get("background_particle_alpha", 22))))
    if particle_count and particle_alpha:
        layer = Image.new("RGBA", (theme.canvas.width, theme.canvas.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        speed = max(0.0, theme.motion.get("background_particle_speed", 0.025))
        for index in range(particle_count):
            phase_offset = (index * 0.61803398875 + time_s * speed + seed * 0.013) % 1.0
            x = round((index * 0.754877666 + phase_offset * 0.22) % 1.0 * theme.canvas.width)
            y = round((0.18 + (index * 0.569840291 + phase_offset * 0.32) % 0.78) * theme.canvas.height)
            radius = 2 + index % 3
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=(*theme.colors["text"], particle_alpha))
        canvas.composite(layer)
    return canvas


def draw_surface(
    canvas: Canvas,
    theme: Theme,
    kind: str,
    box: tuple[float, float, float, float],
    radius: float,
    *,
    seed: int = 1,
    time_s: float = 0.0,
    opacity: float = 1.0,
) -> None:
    """Ask the selected style for a semantic card surface."""
    if opacity <= 0 or box[2] <= box[0] or box[3] <= box[1]:
        return
    style = resolve_style(theme.style, seed)
    context = StyleContext(theme=theme, seed=seed, time_s=time_s, opacity=max(0.0, min(1.0, opacity)))
    try:
        style.surface(canvas, context, kind, box, radius)
    except STYLE_FALLBACK_EXCEPTIONS as exc:
        import warnings

        from ..styles import ClassicStyle

        warnings.warn(f"Style {style.name!r} surface failed; using classic: {exc}", RuntimeWarning, stacklevel=2)
        ClassicStyle().surface(canvas, context, kind, box, radius)


@lru_cache(maxsize=32)
def _animated_glow(
    width: int,
    height: int,
    color: tuple[int, int, int],
    alpha: int,
    phase_bucket: int,
    blur_radius: int,
) -> Image.Image:
    glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(glow)
    phase = phase_bucket / 24
    center_x = round(width * (0.30 + 0.40 * (0.5 - 0.5 * math.cos(2 * math.pi * phase))))
    center_y = round(height * (0.28 + 0.08 * math.sin(2 * math.pi * phase)))
    draw.ellipse(
        (center_x - width * 0.48, center_y - height * 0.20,
         center_x + width * 0.48, center_y + height * 0.20),
        fill=(*color, alpha),
    )
    return glow.filter(ImageFilter.GaussianBlur(blur_radius))


def draw_footer(canvas: Canvas, fonts: FontBook, theme: Theme) -> None:
    footer = str(theme.branding.get("footer_text", ""))
    if footer:
        canvas.text((theme.canvas.width / 2, theme.canvas.height - 52), footer, fonts.get("regular", theme.sizes["footer_px"]), (*theme.colors["muted"], 210), anchor="mm")
    attribution = str(theme.branding.get("voice_attribution_text", ""))
    if attribution:
        canvas.text(
            (theme.canvas.width / 2, theme.canvas.height - 90),
            attribution,
            fonts.get("regular", max(16, theme.sizes["footer_px"] - 4)),
            (*theme.colors["muted"], 210),
            anchor="mm",
        )


def draw_confetti(canvas: Canvas, theme: Theme, time_s: float, seed: int = 1) -> None:
    count = max(0, round(theme.motion.get("answer_confetti_count", 18)))
    duration = max(0.1, theme.motion.get("answer_confetti_duration_s", 1.0))
    progress = progress_at(time_s, theme.motion.get("answer_confetti_start_s", 0.3), duration)
    if progress <= 0 or count == 0:
        return
    layer = Image.new("RGBA", (theme.canvas.width, theme.canvas.height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    colors = tuple(theme.colors[name] for name in ("accent", "success", "info", "warn"))
    for index in range(count):
        phase = (index * 0.61803398875 + seed * 0.017) % 1.0
        x = round(theme.canvas.width * (0.12 + phase * 0.76))
        y = round(theme.canvas.height * (0.10 + (phase + progress * (0.8 + index % 3 * 0.2)) % 0.25))
        size = 5 + index % 5
        color = colors[index % len(colors)]
        draw.polygon(
            ((x, y - size), (x + size, y), (x, y + size), (x - size, y)),
            fill=(*color, round(190 * (1 - progress * 0.35))),
        )
    canvas.composite(layer)


def draw_header(canvas: Canvas, fonts: FontBook, theme: Theme, title: str, progress: float = 1.0) -> None:
    alpha = round(255 * out_cubic(max(progress, theme.motion.get("header_min_progress", 0.48))))
    role = "pixel" if theme.style == "pixel_art" else "bold"
    size = 30
    canvas.text((theme.safe_margin_px, 105), title, fonts.get(role, size), (*theme.colors["accent"], alpha), anchor="la")


def fit(
    theme: Theme,
    role: str,
    text: str,
    width: int,
    height: int,
    start_size: int,
    max_lines: int,
    *,
    min_size: int | None = None,
) -> TextLayout:
    return fit_text(text, str(theme.fonts[role]), width, height, start_size, max(theme.min_body_font_px, min_size or 0), max_lines)


def draw_layout(canvas: Canvas, fonts: FontBook, theme: Theme, layout: TextLayout, x: float, y: float, *, role: str, color: str = "text", alpha: int = 255, anchor: str = "la", line_gap: int = 8, time_s: float | None = None) -> None:
    font_role = "pixel" if theme.style == "pixel_art" and role == "bold" and layout.font_size <= 36 else role
    font_size = layout.font_size
    font = fonts.get(font_role, font_size)
    line_height = font.getbbox("Ag")[3] - font.getbbox("Ag")[1] + line_gap
    if theme.style == "kinetic_typography" and time_s is not None:
        word_index = 0
        interval = float(theme.style_palettes["kinetic_typography"]["word_interval_s"])
        for line_index, line in enumerate(layout.lines):
            cursor_x = x
            if anchor in {"ma", "mm"}:
                cursor_x -= font.getlength(line) / 2
            elif anchor in {"ra", "rm"}:
                cursor_x -= font.getlength(line)
            for match in re.finditer(r"\S+", line):
                word = match.group()
                word_x = cursor_x + font.getlength(line[:match.start()])
                progress = out_cubic(progress_at(time_s, 0.18 + word_index * interval, 0.24))
                if progress > 0:
                    emphasis = bool(re.search(r"\d|%|km/h|m/s|days?", word, re.IGNORECASE))
                    word_color = theme.colors["accent"] if emphasis else theme.colors[color]
                    canvas.text(
                        (word_x + (1.0 - progress) * 18, y + line_index * line_height),
                        word,
                        font,
                        (*word_color, round(alpha * progress)),
                        anchor="la",
                    )
                word_index += 1
        return
    for index, line in enumerate(layout.lines):
        canvas.text((x, y + index * line_height), line, font, (*theme.colors[color], alpha), anchor=anchor)


def scene_progress(time_s: float, reveal_s: float) -> float:
    return out_cubic(progress_at(time_s, 0.0, reveal_s))
