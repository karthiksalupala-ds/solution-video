"""Question and four options scene."""

from __future__ import annotations

from ..engine.assets import FontBook
from ..engine.easing import out_cubic, progress_at
from ..engine.theme import Theme
from ..schema import QuestionInput
from .common import draw_footer, draw_header, draw_layout, fit, make_canvas


class QuestionScene:
    def __init__(self, question: QuestionInput, theme: Theme) -> None:
        self.question, self.theme, self.fonts = question, theme, FontBook(theme)

    def render_frame(self, time_s: float):
        canvas, theme = make_canvas(self.theme), self.theme
        margin = theme.safe_margin_px
        draw_header(canvas, self.fonts, theme, "QUESTION", progress_at(time_s, 0, 0.3))
        layout = fit(theme, "medium", self.question.question, theme.canvas.width - 2 * margin, 310, 44, 4)
        draw_layout(canvas, self.fonts, theme, layout, margin, 180, role="medium", alpha=round(255 * out_cubic(progress_at(time_s, 0.15, 0.45))))
        base_y = 545
        for index, option in enumerate(self.question.options):
            progress = out_cubic(progress_at(time_s, 0.6 + index * theme.motion["stagger_s"], 0.35))
            y = base_y + index * 142
            offset = (1 - progress) * 100
            canvas.rounded_rect((margin + offset, y, theme.canvas.width - margin + offset, y + 108), 24, (*theme.colors["info"], round(205 * progress)), (*theme.colors["text"], round(70 * progress)), 2)
            canvas.ellipse((margin + 18 + offset, y + 24, margin + 60 + offset, y + 66), (*theme.colors["accent"], round(255 * progress)))
            canvas.text((margin + 39 + offset, y + 45), chr(ord("A") + index), self.fonts.get("bold", 24), (*theme.colors["bg_top"], round(255 * progress)), anchor="mm")
            option_layout = fit(theme, "medium", option, theme.canvas.width - 2 * margin - 105, 72, 36, 2)
            draw_layout(canvas, self.fonts, theme, option_layout, margin + 82 + offset, y + 23, role="medium", alpha=round(255 * progress), line_gap=2)
        draw_footer(canvas, self.fonts, theme)
        return canvas.final_rgb()
