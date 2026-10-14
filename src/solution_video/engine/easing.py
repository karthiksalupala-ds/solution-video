"""Pure deterministic interpolation helpers."""

from __future__ import annotations

import math


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def lerp(start: float, end: float, progress: float) -> float:
    return start + (end - start) * clamp(progress)


def linear(progress: float) -> float:
    return clamp(progress)


def out_cubic(progress: float) -> float:
    value = 1.0 - clamp(progress)
    return 1.0 - value * value * value


def in_out_cubic(progress: float) -> float:
    value = clamp(progress)
    return 4 * value**3 if value < 0.5 else 1 - (-2 * value + 2) ** 3 / 2


def out_back(progress: float) -> float:
    value = clamp(progress) - 1
    return 1 + 2.70158 * value**3 + 1.70158 * value**2


def out_spring(progress: float) -> float:
    value = clamp(progress)
    return 1.0 if value in (0.0, 1.0) else 1 - math.exp(-6 * value) * math.cos(12 * value)


def progress_at(time_s: float, start_s: float, duration_s: float) -> float:
    if duration_s <= 0:
        raise ValueError("duration_s must be positive")
    return clamp((time_s - start_s) / duration_s)


def stagger(index: int, delay_s: float) -> float:
    if index < 0 or delay_s < 0:
        raise ValueError("stagger index and delay must be non-negative")
    return index * delay_s
