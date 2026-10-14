"""Generic calculation-step scene."""

from __future__ import annotations

from ..engine.assets import FontBook
from ..engine.easing import out_cubic, progress_at
from ..engine.theme import Theme
from ..schema import StepSpec
from .common import draw_footer, draw_header, draw_layout, fit, make_canvas


class StepScene:
    def __init__(self, step: StepSpec, step_index: int, step_count: int, theme: Theme) -> None:
        self.step, self.step_index, self.step_count, self.theme, self.fonts = step, step_index, step_count, theme, FontBook(theme)

    def render_frame(self, time_s: float):
        canvas, theme = make_canvas(self.theme), self.theme
        draw_header(canvas, self.fonts, theme, f"STEP {self.step_index}/{self.step_count}", progress_at(time_s, 0, 0.3))
        margin = theme.safe_margin_px
        label = fit(theme, "bold", self.step.label, theme.canvas.width - 2 * margin, 130, 46, 2)
        draw_layout(canvas, self.fonts, theme, label, margin, 200, role="bold", color="text", alpha=round(255 * out_cubic(progress_at(time_s, 0.15, 0.35))))
        base_y = 440
        for index, line in enumerate(self.step.lines):
            progress = out_cubic(progress_at(time_s, 0.55 + index * 0.55, 0.40))
            y = base_y + index * 145
            canvas.rounded_rect((margin, y, theme.canvas.width - margin, y + 108), 22, (*theme.colors["info"], round(180 * progress)))
            layout = fit(theme, "bold", line, theme.canvas.width - 2 * margin - 50, 82, 46, 2)
            color = "success" if self.step.emphasis and self.step.emphasis in line else "text"
            draw_layout(canvas, self.fonts, theme, layout, margin + 26, y + 24, role="bold", color=color, alpha=round(255 * progress), line_gap=2)
        draw_footer(canvas, self.fonts, theme)
        return canvas.final_rgb()
