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
        canvas, theme = make_canvas(self.theme, time_s, self.question.day), self.theme
        progress = scene_progress(time_s, theme.motion["reveal_s"])
        margin = theme.safe_margin_px
        if theme.branding.get("show_day_pill", True):
            intro = f"DAY {self.question.day}"
            pill_font = self.fonts.get("bold", theme.sizes.get("day_pill_px", 34))
            pill_width = max(
                theme.motion.get("day_pill_min_width_px", 210),
                round(pill_font.getlength(intro) + theme.motion.get("difficulty_chip_padding_px", 54) + 10),
            )
            pill_y = round(theme.canvas.height * theme.motion.get("day_pill_top_ratio", 0.22))
            pill_height = theme.motion.get("day_pill_height_px", 84)
            lift = (1 - min(1.0, out_back(progress))) * theme.motion.get("day_pill_lift_px", 54)
            canvas.rounded_rect(
                (theme.canvas.width / 2 - pill_width / 2, pill_y + lift,
                 theme.canvas.width / 2 + pill_width / 2, pill_y + pill_height + lift),
                pill_height / 2,
                (*theme.colors["accent"], round(255 * progress)),
            )
            canvas.text(
                (theme.canvas.width / 2, pill_y + pill_height / 2 + lift),
                intro,
                pill_font,
                (*theme.colors["bg_top"], round(255 * progress)),
                anchor="mm",
            )
        else:
            lift = (1 - min(1.0, out_back(progress))) * 54
        layout = fit(
            theme,
            "bold",
            self.question.topic,
            theme.canvas.width - 2 * margin - 20,
            350,
            theme.sizes.get("title_px", 82),
            3,
        )
        draw_layout(
            canvas,
            self.fonts,
            theme,
            layout,
            theme.canvas.width / 2,
            theme.canvas.height * theme.motion.get("title_topic_center_ratio", 0.53) - layout.height / 2 + lift,
            role="bold",
            alpha=round(255 * progress),
            anchor="ma",
            line_gap=16,
        )
        if self.question.difficulty:
            chip_font = self.fonts.get("medium", theme.sizes.get("difficulty_chip_px", 30))
            chip_height = theme.motion.get("difficulty_chip_height_px", 68)
            chip_width = round(
                chip_font.getlength(self.question.difficulty)
                + theme.motion.get("difficulty_chip_padding_px", 54)
            )
            chip_y = round(theme.canvas.height * theme.motion.get("title_difficulty_center_ratio", 0.73) - chip_height / 2)
            canvas.rounded_rect(
                (theme.canvas.width / 2 - chip_width / 2, chip_y,
                 theme.canvas.width / 2 + chip_width / 2, chip_y + chip_height),
                chip_height / 2,
                (*theme.colors["info"], round(225 * progress)),
            )
            canvas.text(
                (theme.canvas.width / 2, chip_y + chip_height / 2),
                self.question.difficulty,
                chip_font,
                (*theme.colors["text"], round(255 * progress)),
                anchor="mm",
            )
        draw_footer(canvas, self.fonts, theme)
        return canvas.final_rgb()
