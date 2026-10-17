"""Animated train/platform crossing diagram using input-provided dimensions."""

from __future__ import annotations

import math

from ..engine.assets import FontBook
from ..engine.canvas import Canvas
from ..engine.easing import in_out_cubic, progress_at
from ..engine.theme import Theme


def draw_train_crossing(
    canvas: Canvas,
    data: dict[str, object],
    bounds: tuple[float, float, float, float],
    time_s: float,
    theme: Theme,
) -> None:
    """Animate the train front entering and its rear leaving the platform."""
    train_length = _positive_number(data.get("train_length_m"), "train_length_m")
    platform_length = _positive_number(data.get("platform_length_m"), "platform_length_m")
    crossing_time = _positive_number(data.get("crossing_time_s"), "crossing_time_s")
    distance_unit = _required_label(data.get("distance_unit"), "distance_unit")
    time_unit = _required_label(data.get("time_unit"), "time_unit")
    train_label = _required_label(data.get("train_label"), "train_label")
    platform_label = _required_label(data.get("platform_label"), "platform_label")
    front_label = _required_label(data.get("front_marker_label"), "front_marker_label")
    rear_label = _required_label(data.get("rear_marker_label"), "rear_marker_label")
    elapsed_label = _required_label(data.get("elapsed_label"), "elapsed_label")
    distance_label = _required_label(data.get("distance_label"), "distance_label")

    left, top, right, bottom = bounds
    width, height = right - left, bottom - top
    font_book = FontBook(theme)
    title_font = font_book.get("medium", max(24, round(theme.sizes.get("plugin_label_px", 36))))
    counter_font = font_book.get("bold", max(36, round(theme.sizes.get("plugin_counter_px", 54))))
    label_font = font_book.get("medium", max(22, round(theme.sizes.get("plugin_label_px", 36))))

    total_distance = train_length + platform_length
    duration = max(0.1, theme.motion.get("plugin_train_duration_s", 3.0))
    progress = _crossing_progress(time_s, duration)
    distance = total_distance * progress
    elapsed = crossing_time * progress

    canvas.text(
        ((left + right) / 2, top + height * 0.065),
        distance_label,
        title_font,
        (*theme.colors["muted"], 245),
        anchor="mm",
    )
    canvas.text(
        ((left + right) / 2, top + height * 0.19),
        f"{_format_number(distance)} {distance_unit}",
        counter_font,
        (*theme.colors["success"], 255),
        anchor="mm",
    )

    progress_left, progress_right = left + width * 0.04, right - width * 0.04
    progress_y = top + height * 0.31
    progress_height = max(8, height * 0.035)
    canvas.rounded_rect(
        (progress_left, progress_y, progress_right, progress_y + progress_height),
        progress_height / 2,
        (*theme.colors["muted"], 72),
    )
    canvas.rounded_rect(
        (progress_left, progress_y, progress_left + (progress_right - progress_left) * progress, progress_y + progress_height),
        progress_height / 2,
        (*theme.colors["success"], 245),
    )

    train_text = f"{train_label}: {train_length:g} {distance_unit}"
    platform_text = f"{platform_label}: {platform_length:g} {distance_unit}"
    if max(title_font.getlength(train_text), title_font.getlength(platform_text)) > width * 0.48:
        raise ValueError("train and platform labels must fit their dimension cards")
    chip_top = top + height * 0.39
    chip_bottom = top + height * 0.49
    chip_gap = width * 0.04
    chip_width = (width - chip_gap) / 2
    canvas.rounded_rect(
        (left, chip_top, left + chip_width, chip_bottom),
        16,
        (*theme.colors["info"], 210),
    )
    canvas.rounded_rect(
        (left + chip_width + chip_gap, chip_top, right, chip_bottom),
        16,
        (*theme.colors["warn"], 220),
    )
    canvas.text(
        (left + chip_width / 2, (chip_top + chip_bottom) / 2),
        train_text,
        title_font,
        (*theme.colors["text"], 255),
        anchor="mm",
    )
    canvas.text(
        (left + chip_width + chip_gap + chip_width / 2, (chip_top + chip_bottom) / 2),
        platform_text,
        title_font,
        (*theme.colors["text"], 255),
        anchor="mm",
    )

    track_margin = width * 0.035
    track_left, track_right = left + track_margin, right - track_margin
    track_width = track_right - track_left
    train_left, train_width, platform_left, platform_right = _crossing_geometry(
        track_left,
        track_width,
        train_length,
        platform_length,
        progress,
    )
    platform_width = platform_right - platform_left
    track_y = top + height * 0.69

    _draw_cityscape(canvas, track_left, platform_right, top + height * 0.53, track_y - 14, theme)
    tie_count = max(6, round(theme.motion.get("plugin_train_tie_count", 14)))
    for index in range(tie_count):
        tie_x = track_left + index * track_width / max(1, tie_count - 1)
        canvas.rounded_rect(
            (tie_x - 3, track_y + 16, tie_x + 3, track_y + 30),
            2,
            (*theme.colors["muted"], 150),
        )
    canvas.line(((track_left, track_y + 15), (track_right, track_y + 15)), (*theme.colors["text"], 205), width=5)
    canvas.line(((track_left, track_y + 31), (track_right, track_y + 31)), (*theme.colors["muted"], 205), width=4)
    canvas.rounded_rect(
        (platform_left, track_y + 2, platform_right, track_y + 14),
        5,
        (*theme.colors["warn"], 190),
    )
    platform_progress = min(platform_length, max(0.0, distance - train_length)) / platform_length
    if platform_progress > 0:
        canvas.rounded_rect(
            (platform_left, track_y + 2, platform_left + platform_width * platform_progress, track_y + 14),
            5,
            (*theme.colors["success"], 245),
        )

    marker_top = top + height * 0.56
    for marker_x, color_name in ((platform_left, "success"), (platform_right, "accent")):
        canvas.line(
            ((marker_x, marker_top), (marker_x, track_y + 34)),
            (*theme.colors[color_name], 190),
            width=3,
        )
    canvas.text(
        (_clamp_label_x(front_label, label_font, platform_left, left, right), track_y + height * 0.105),
        front_label,
        label_font,
        (*theme.colors["success"], 245),
        anchor="mm",
    )
    rear_color = "success" if progress >= 1 else "muted"
    canvas.text(
        (_clamp_label_x(rear_label, label_font, platform_right, left, right), track_y + height * 0.105),
        rear_label,
        label_font,
        (*theme.colors[rear_color], 245),
        anchor="mm",
    )

    if progress > 0.01 and progress < 1:
        trail_count = max(1, round(theme.motion.get("plugin_train_trail_count", 3)))
        for index in range(trail_count):
            trail_x = train_left - train_width * (0.1 + index * 0.11)
            if trail_x > left:
                canvas.line(
                    ((trail_x, track_y - 28 - index * 6), (trail_x - width * 0.045, track_y - 28 - index * 6)),
                    (*theme.colors["info"], max(55, 160 - index * 30)),
                    width=3,
                )
    _draw_train(canvas, train_left, track_y, train_width, theme)

    elapsed_text = f"{elapsed_label}: {_format_number(elapsed)} / {crossing_time:g} {time_unit}"
    canvas.text(
        ((left + right) / 2, bottom - label_font.size * 0.65),
        elapsed_text,
        label_font,
        (*theme.colors["text"], 240),
        anchor="mm",
    )


def _draw_cityscape(
    canvas: Canvas,
    left: float,
    right: float,
    top: float,
    baseline: float,
    theme: Theme,
) -> None:
    width = right - left
    building_count = max(4, round(theme.motion.get("plugin_city_building_count", 9)))
    gap = width * 0.012
    building_width = (width - gap * (building_count - 1)) / building_count
    max_height = baseline - top
    for index in range(building_count):
        height_ratio = 0.38 + ((index * 7) % 5) * 0.11
        building_height = max_height * height_ratio
        x0 = left + index * (building_width + gap)
        y0 = baseline - building_height
        canvas.rounded_rect(
            (x0, y0, x0 + building_width, baseline),
            4,
            (*theme.colors["info"], 38 + (index % 3) * 8),
        )
        window_width = max(2, building_width * 0.13)
        window_height = max(2, max_height * 0.035)
        for row in range(2):
            for column in range(2):
                window_x = x0 + building_width * (0.25 + column * 0.42)
                window_y = y0 + building_height * (0.25 + row * 0.3)
                canvas.rounded_rect(
                    (window_x, window_y, window_x + window_width, window_y + window_height),
                    1,
                    (*theme.colors["accent"], 70),
                )


def _draw_train(canvas: Canvas, left: float, track_y: float, width: float, theme: Theme) -> None:
    body_top = track_y - 48
    body_bottom = track_y + 8
    nose_width = min(18, width * 0.12)
    body_right = left + width - nose_width
    canvas.rounded_rect(
        (left, body_top, body_right, body_bottom),
        13,
        (*theme.colors["info"], 255),
    )
    canvas.polygon(
        (
            (body_right - 1, body_top + 10),
            (left + width, body_top + 24),
            (left + width, body_bottom),
            (body_right - 1, body_bottom),
        ),
        (*theme.colors["info"], 255),
    )
    canvas.rounded_rect(
        (left + 5, body_bottom - 7, left + width - 3, body_bottom),
        2,
        (*theme.colors["accent"], 255),
    )
    window_count = max(1, round(theme.motion.get("plugin_train_window_count", 3)))
    window_width = max(6, min(22, width * 0.13))
    available = max(0.0, body_right - left - 16 - window_count * window_width)
    window_gap = available / (window_count + 1)
    for index in range(window_count):
        window_left = left + 8 + window_gap * (index + 1) + window_width * index
        canvas.rounded_rect(
            (window_left, body_top + 10, window_left + window_width, body_top + 29),
            4,
            (*theme.colors["text"], 235),
        )
    wheel_radius = max(5, min(8, width * 0.04))
    for wheel_x in (left + width * 0.25, left + width * 0.73):
        canvas.ellipse(
            (wheel_x - wheel_radius, body_bottom - 2, wheel_x + wheel_radius, body_bottom + wheel_radius * 2 - 2),
            (*theme.colors["text"], 255),
        )
        canvas.ellipse(
            (wheel_x - wheel_radius / 2, body_bottom + wheel_radius / 2 - 2, wheel_x + wheel_radius / 2, body_bottom + wheel_radius * 1.5 - 2),
            (*theme.colors["muted"], 255),
        )


def _positive_number(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"{field} must be a positive finite number")
    return float(value)


def _crossing_progress(time_s: float, duration_s: float) -> float:
    return in_out_cubic(progress_at(time_s, 0, duration_s))


def _crossing_geometry(
    track_left: float,
    track_width: float,
    train_length: float,
    platform_length: float,
    progress: float,
) -> tuple[float, float, float, float]:
    scale = track_width / (2 * train_length + platform_length)
    train_width = train_length * scale
    platform_left = track_left + train_width
    platform_right = platform_left + platform_length * scale
    train_left = track_left + (train_length + platform_length) * scale * progress
    return train_left, train_width, platform_left, platform_right


def _required_label(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be non-empty text")
    return value.strip()


def _format_number(value: float) -> str:
    return str(round(value)) if value.is_integer() else f"{value:.1f}".rstrip("0").rstrip(".")


def _clamp_label_x(label: str, font, x: float, left: float, right: float) -> float:
    half_width = font.getlength(label) / 2
    return min(max(x, left + half_width), right - half_width)
