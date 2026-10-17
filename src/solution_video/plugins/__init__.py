"""Optional, input-driven topic visuals with generic-scene fallback."""

from __future__ import annotations

import warnings
from typing import Callable

from ..engine.canvas import Canvas
from ..engine.theme import Theme
from ..schema import VisualSpec
from .bar_chart import draw_bar_chart
from .train_crossing import draw_train_crossing


VisualRenderer = Callable[[Canvas, dict[str, object], tuple[float, float, float, float], float, Theme], None]
_VISUALS: dict[str, VisualRenderer] = {
    "bar_chart": draw_bar_chart,
    "train_crossing": draw_train_crossing,
}


def draw_visual(
    canvas: Canvas,
    visual: VisualSpec | None,
    bounds: tuple[float, float, float, float],
    time_s: float,
    theme: Theme,
    *,
    warn: bool = True,
) -> bool:
    """Draw a registered visual; warn and leave generic content visible otherwise."""
    if visual is None:
        return False
    renderer = _VISUALS.get(visual.name)
    if renderer is None:
        if warn:
            warnings.warn(
                f"Unknown visual plugin {visual.name!r}; using the generic step scene",
                RuntimeWarning,
                stacklevel=2,
            )
        return False
    try:
        renderer(canvas, visual.data, bounds, time_s, theme)
    except ValueError as exc:
        if warn:
            warnings.warn(
                f"Invalid {visual.name!r} visual data ({exc}); using the generic step scene",
                RuntimeWarning,
                stacklevel=2,
            )
        return False
    return True
