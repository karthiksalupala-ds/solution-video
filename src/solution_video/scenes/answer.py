"""Final answer payoff scene."""

from __future__ import annotations

from ..engine.assets import FontBook
from ..engine.easing import out_back, progress_at
from ..engine.theme import Theme
from ..schema import AnswerSpec, QuestionInput
from .common import draw_footer, draw_header, draw_layout, fit, make_canvas


class AnswerScene:
    def __init__(self, answer: AnswerSpec, question: QuestionInput, theme: Theme) -> None:
        self.answer, self.question, self.theme, self.fonts = answer, question, theme, FontBook(theme)

    def render_frame(self, time_s: float):
        canvas, theme = make_canvas(self.theme), self.theme
        progress = min(1.0, out_back(progress_at(time_s, 0.3, 0.55)))
        draw_header(canvas, self.fonts, theme, "ANSWER", progress)
        width = 570 * progress
        canvas.rounded_rect((360 - width / 2, 370, 360 + width / 2, 700), 38, (*theme.colors["success"], round(225 * progress)))
        layout = fit(theme, "bold", self.answer.display, 500, 185, 82, 3)
        draw_layout(canvas, self.fonts, theme, layout, 360, 505 - layout.height / 2, role="bold", alpha=round(255 * progress), anchor="ma")
        option = self.answer.correct_option or self.question.correct_option
        canvas.rounded_rect((188, 795, 532, 875), 34, (*theme.colors["accent"], round(255 * progress)))
        canvas.text((360, 835), f"OPTION {option}", self.fonts.get("bold", 34), (*theme.colors["bg_top"], round(255 * progress)), anchor="mm")
        draw_footer(canvas, self.fonts, theme)
        return canvas.final_rgb()
