"""Input-driven call-to-action scene."""

from __future__ import annotations

from ..engine.assets import FontBook
from ..engine.easing import out_back, progress_at
from ..engine.theme import Theme
from ..schema import TipSpec
from .common import draw_footer, draw_layout, fit, make_canvas


class OutroScene:
    def __init__(self, cta: TipSpec, theme: Theme) -> None:
        self.cta, self.theme, self.fonts = cta, theme, FontBook(theme)

    def render_frame(self, time_s: float):
        canvas, theme = make_canvas(self.theme), self.theme
        progress = min(1.0, out_back(progress_at(time_s, 0.2, 0.5)))
        layout = fit(theme, "bold", self.cta.display, 570, 270, 64, 3)
        draw_layout(canvas, self.fonts, theme, layout, 360, 560 - layout.height / 2, role="bold", alpha=round(255 * progress), anchor="ma")
        draw_footer(canvas, self.fonts, theme)
        return canvas.final_rgb()
