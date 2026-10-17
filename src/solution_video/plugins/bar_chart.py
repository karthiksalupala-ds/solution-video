"""Animated bar chart for values supplied by the question input."""

from __future__ import annotations

import math

from ..engine.assets import FontBook
from ..engine.canvas import Canvas
from ..engine.easing import out_cubic, progress_at
from ..engine.theme import Theme


def draw_bar_chart(
    canvas: Canvas,
    data: dict[str, object],
    bounds: tuple[float, float, float, float],
    time_s: float,
    theme: Theme,
) -> None:
    """Draw input values growing upward and count them to their final values."""
    values = data.get("values")
    labels = data.get("labels")
    highlights = data.get("highlight_indices", [])
    if (
        not isinstance(values, list)
        or not 2 <= len(values) <= 8
        or not isinstance(labels, list)
        or len(labels) != len(values)
        or any(not isinstance(label, str) or not label.strip() for label in labels)
        or not isinstance(highlights, list)
        or any(isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < len(values) for index in highlights)
    ):
        raise ValueError("expected 2-8 values, matching labels, and valid highlight_indices")
    numeric_values = [_finite_number(value) for value in values]
    if min(numeric_values) < 0 or max(numeric_values) <= 0:
        raise ValueError("bar chart values must be non-negative with a positive maximum")
    title = data.get("title", "")
    if not isinstance(title, str):
        raise ValueError("title must be text")

    left, top, right, bottom = bounds
    width, height = right - left, bottom - top
    reveal_s = theme.motion.get("plugin_reveal_s", 1.4)
    title_font = FontBook(theme).get("bold", max(24, round(theme.sizes.get("plugin_title_px", 30))))
    chart_top = top + height * 0.23
    baseline = bottom - height * 0.24
    chart_height = max(1.0, baseline - chart_top)
    gap = width * 0.035
    bar_width = (width - gap * (len(values) + 1)) / len(values)
    maximum = max(numeric_values)
    fonts = FontBook(theme)
    label_font = fonts.get("medium", max(24, round(theme.sizes.get("plugin_label_px", 36))))
    value_font = fonts.get("bold", max(24, round(theme.sizes.get("plugin_value_px", 36))))
    if any(label_font.getlength(label) > bar_width + gap for label in labels):
        raise ValueError("labels must fit within their chart columns")
    if any(value_font.getlength(_format_number(value)) > bar_width + gap for value in numeric_values):
        raise ValueError("values must fit within their chart columns")
    if title and title_font.getlength(title) > width:
        raise ValueError("title must fit within the chart width")
    if title:
        canvas.text(
            ((left + right) / 2, top + height * 0.07),
            title,
            title_font,
            (*theme.colors["text"], 245),
            anchor="mm",
        )
    grid_count = max(2, round(theme.motion.get("plugin_chart_grid_lines", 4)))
    for index in range(grid_count):
        grid_y = chart_top + chart_height * index / max(1, grid_count - 1)
        canvas.line(
            ((left, grid_y), (right, grid_y)),
            (*theme.colors["muted"], 52 if index else 90),
            width=2,
        )
    canvas.rounded_rect(
        (left, baseline, right, baseline + 5),
        2,
        (*theme.colors["muted"], 205),
    )

    for index, (value, label) in enumerate(zip(numeric_values, labels)):
        bar_progress = _bar_progress(
            time_s,
            index,
            reveal_s,
            theme.motion.get("plugin_stagger_s", 0.18),
        )
        bar_height = chart_height * value / maximum * bar_progress
        x0 = left + gap + index * (bar_width + gap)
        x1 = x0 + bar_width
        y0 = baseline - bar_height
        color_name = "accent" if index in highlights else "info"
        if bar_height > 0:
            canvas.rounded_rect(
                (x0 + 4, y0 + 5, x1 + 4, baseline + 3),
                min(bar_width / 2, theme.motion.get("plugin_bar_radius_px", 12)),
                (*theme.colors["bg_top"], 140),
            )
        canvas.rounded_rect(
            (x0, y0, x1, baseline),
            min(bar_width / 2, theme.motion.get("plugin_bar_radius_px", 12)),
            (*theme.colors[color_name], round(245 * bar_progress)),
            (
                (*theme.colors["success"], round(90 + 140 * _highlight_pulse(time_s, theme)))
                if index in highlights and bar_progress > 0.92
                else None
            ),
            3,
        )
        shown_value = value * bar_progress
        if bar_progress > 0.08:
            canvas.text(
                ((x0 + x1) / 2, max(top + label_font.size, y0 - 10)),
                _format_animated_value(value, bar_progress),
                value_font,
                (*theme.colors["text"], round(255 * bar_progress)),
                anchor="ms",
            )
        canvas.text(
            ((x0 + x1) / 2, baseline + label_font.size * 0.9),
            label,
            label_font,
            (*theme.colors["text"], round(235 * bar_progress)),
            anchor="mm",
        )


def _bar_progress(time_s: float, index: int, reveal_s: float, stagger_s: float) -> float:
    return out_cubic(progress_at(time_s, index * stagger_s, reveal_s))


def _highlight_pulse(time_s: float, theme: Theme) -> float:
    frequency = theme.motion.get("plugin_highlight_pulse_hz", 1.4)
    return 0.5 + 0.5 * math.sin(2 * math.pi * frequency * max(0.0, time_s))


def _format_animated_value(value: float, progress: float) -> str:
    shown_value = value * progress
    return str(round(shown_value)) if value.is_integer() else _format_number(shown_value)


def _finite_number(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("values must be finite numbers")
    return float(value)


def _format_number(value: float) -> str:
    if value.is_integer():
        return str(int(value))
    return f"{value:.1f}".rstrip("0").rstrip(".")
