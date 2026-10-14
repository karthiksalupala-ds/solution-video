"""Topic and day opening scene."""

from __future__ import annotations

from ..engine.assets import FontBook
from ..engine.easing import out_back
from ..engine.theme import Theme
from ..schema import QuestionInput
from .common import draw_footer, draw_layout, fit, make_canvas, scene_progress


class TitleScene:
    def __init__(self, question: QuestionInput, theme: Theme) -> None:
        self.question, self.theme, self.fonts = question, theme, FontBook(theme)

    def render_frame(self, time_s: float):
        canvas, theme = make_canvas(self.theme), self.theme
        progress = scene_progress(time_s, theme.motion["reveal_s"])
        margin = theme.safe_margin_px
        canvas.rounded_rect((margin, 120, 260, 178), 28, (*theme.colors["accent"], round(255 * progress)))
        canvas.text((150, 149), f"DAY {self.question.day}", self.fonts.get("bold", 25), (*theme.colors["bg_top"], round(255 * progress)), anchor="mm")
        canvas.text((margin, 260), self.question.topic, self.fonts.get("medium", 34), (*theme.colors["muted"], round(255 * progress)))
        layout = fit(theme, "bold", self.question.topic, theme.canvas.width - 2 * margin, 350, theme.sizes["title_px"], 3)
        draw_layout(canvas, self.fonts, theme, layout, margin, 340 + (1 - min(1.0, out_back(progress))) * 60, role="bold", alpha=round(255 * progress))
        if self.question.difficulty:
            canvas.rounded_rect((margin, 770, 270, 826), 20, (*theme.colors["info"], round(210 * progress)))
            canvas.text((margin + 20, 798), self.question.difficulty, self.fonts.get("medium", 27), (*theme.colors["text"], round(255 * progress)), anchor="lm")
        draw_footer(canvas, self.fonts, theme)
        return canvas.final_rgb()
