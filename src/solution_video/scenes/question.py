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
        canvas, theme = make_canvas(self.theme, time_s, self.question.day), self.theme
        margin = theme.safe_margin_px
        draw_header(canvas, self.fonts, theme, "QUESTION", progress_at(time_s, 0, 0.3))
        question_top = round(theme.canvas.height * 0.16)
        layout = fit(
            theme,
            "medium",
            self.question.question,
            theme.canvas.width - 2 * margin - 28,
            390,
            theme.sizes.get("question_px", 48),
            5,
        )
        question_progress = out_cubic(progress_at(time_s, 0.08, theme.motion["reveal_s"]))
        draw_layout(
            canvas,
            self.fonts,
            theme,
            layout,
            margin + 14,
            question_top,
            role="medium",
            alpha=round(255 * question_progress),
            line_gap=14,
        )
        base_y = max(question_top + layout.height + 54, round(theme.canvas.height * 0.50))
        option_height = int(theme.motion.get("option_card_height_px", 104))
        option_gap = int(theme.motion.get("option_card_gap_px", 16))
        option_start = theme.motion.get("question_option_start_s", 0.6)
        for index, option in enumerate(self.question.options):
            progress = out_cubic(progress_at(
                time_s,
                option_start + index * theme.motion["stagger_s"],
                theme.motion["reveal_s"],
            ))
            y = base_y + index * (option_height + option_gap)
            offset = (1 - progress) * theme.motion.get("option_slide_px", 60)
            radius = option_height / 2
            canvas.rounded_rect(
                (margin + offset, y, theme.canvas.width - margin + offset, y + option_height),
                radius,
                (*theme.colors["info"], round(215 * progress)),
                (*theme.colors["text"], round(72 * progress)),
                2,
            )
            badge_size = min(64, option_height - 28)
            badge_x = margin + 18 + offset
            badge_y = y + (option_height - badge_size) / 2
            canvas.ellipse(
                (badge_x, badge_y, badge_x + badge_size, badge_y + badge_size),
                (*theme.colors["accent"], round(255 * progress)),
            )
            letter = chr(ord("A") + index)
            canvas.text(
                (badge_x + badge_size / 2, badge_y + badge_size / 2),
                letter,
                self.fonts.get("bold", 30),
                (*theme.colors["bg_top"], round(255 * progress)),
                anchor="mm",
            )
            option_layout = fit(
                theme,
                "medium",
                option,
                theme.canvas.width - 2 * margin - 118,
                option_height - 24,
                theme.sizes.get("option_px", 42),
                2,
            )
            draw_layout(
                canvas,
                self.fonts,
                theme,
                option_layout,
                margin + 102 + offset,
                y + (option_height - option_layout.height) / 2,
                role="medium",
                alpha=round(255 * progress),
                line_gap=4,
            )
        draw_footer(canvas, self.fonts, theme)
        return canvas.final_rgb()
