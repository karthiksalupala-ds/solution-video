"""Optional shortcut or hint scene."""

from __future__ import annotations

from ..engine.assets import FontBook
from ..engine.easing import out_cubic, progress_at
from ..engine.theme import Theme
from ..schema import TipSpec
from .common import draw_footer, draw_header, draw_layout, fit, make_canvas


class TipScene:
    def __init__(self, tip: TipSpec, theme: Theme) -> None:
        self.tip, self.theme, self.fonts = tip, theme, FontBook(theme)

    def render_frame(self, time_s: float):
        canvas, theme = make_canvas(self.theme, time_s), self.theme
        progress = out_cubic(progress_at(time_s, 0.1, 0.45))
        draw_header(canvas, self.fonts, theme, "QUICK TIP", progress)
        canvas.rounded_rect((70, 370, 650, 760), 36, (*theme.colors["warn"], round(205 * progress)))
        layout = fit(theme, "bold", self.tip.display, 490, 260, 56, 3)
        draw_layout(canvas, self.fonts, theme, layout, 360, 565 - layout.height / 2, role="bold", alpha=round(255 * progress), anchor="ma")
        draw_footer(canvas, self.fonts, theme)
        return canvas.final_rgb()
