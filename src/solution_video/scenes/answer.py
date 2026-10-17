"""Final answer payoff scene."""

from __future__ import annotations

from ..engine.assets import FontBook
from ..engine.easing import out_back, progress_at
from ..engine.theme import Theme
from ..schema import AnswerSpec, QuestionInput
from .common import draw_confetti, draw_footer, draw_header, draw_layout, fit, make_canvas


class AnswerScene:
    def __init__(self, answer: AnswerSpec, question: QuestionInput, theme: Theme) -> None:
        self.answer, self.question, self.theme, self.fonts = answer, question, theme, FontBook(theme)

    def render_frame(self, time_s: float):
        canvas, theme = make_canvas(self.theme, time_s, self.question.day), self.theme
        progress = min(1.0, out_back(progress_at(time_s, 0.3, 0.55)))
        draw_header(canvas, self.fonts, theme, "ANSWER", progress)
        draw_confetti(canvas, theme, time_s, self.question.day)
        width = 600 * progress
        banner_top = round(theme.canvas.height * theme.motion.get("answer_banner_top_ratio", 0.22))
        banner_bottom = banner_top + theme.motion.get("answer_banner_height_px", 176)
        canvas.rounded_rect(
            (theme.canvas.width / 2 - width / 2, banner_top,
             theme.canvas.width / 2 + width / 2, banner_bottom),
            38,
            (*theme.colors["success"], round(230 * progress)),
        )
        layout = fit(
            theme,
            "bold",
            self.answer.display,
            530,
            128,
            theme.sizes.get("answer_px", 82),
            3,
        )
        draw_layout(
            canvas,
            self.fonts,
            theme,
            layout,
            theme.canvas.width / 2,
            (banner_top + banner_bottom - layout.height) / 2,
            role="bold",
            alpha=round(255 * progress),
            anchor="ma",
        )
        options_progress = out_back(progress_at(
            time_s,
            theme.motion.get("answer_options_start_s", 1.55),
            theme.motion.get("answer_options_reveal_s", 0.45),
        ))
        option_height = theme.motion.get("answer_option_height_px", 104)
        option_gap = theme.motion.get("answer_option_gap_px", 14)
        list_top = banner_bottom + 54
        correct_option = self.answer.correct_option or self.question.correct_option
        for index, option_text in enumerate(self.question.options):
            letter = chr(ord("A") + index)
            correct = letter == correct_option
            option_progress = min(1.0, max(0.0, options_progress))
            y = list_top + index * (option_height + option_gap)
            slide = (1 - option_progress) * theme.motion.get("answer_option_slide_px", 42)
            background = theme.colors["success"] if correct else theme.colors["info"]
            alpha = round((238 if correct else 145) * option_progress)
            canvas.rounded_rect(
                (theme.safe_margin_px + slide, y,
                 theme.canvas.width - theme.safe_margin_px + slide, y + option_height),
                option_height / 2,
                (*background, alpha),
                (*theme.colors["text"], round(72 * option_progress)),
                2,
            )
            badge_size = min(64, option_height - 28)
            badge_x, badge_y = theme.safe_margin_px + 18 + slide, y + (option_height - badge_size) / 2
            badge_color = theme.colors["accent"] if correct else theme.colors["muted"]
            canvas.ellipse(
                (badge_x, badge_y, badge_x + badge_size, badge_y + badge_size),
                (*badge_color, round(255 * option_progress)),
            )
            canvas.text(
                (badge_x + badge_size / 2, badge_y + badge_size / 2),
                letter,
                self.fonts.get("bold", 30),
                (*theme.colors["bg_top"], round(255 * option_progress)),
                anchor="mm",
            )
            option_layout = fit(
                theme,
                "medium",
                option_text,
                theme.canvas.width - 2 * theme.safe_margin_px - 150,
                option_height - 24,
                theme.sizes.get("option_px", 42),
                2,
            )
            draw_layout(
                canvas,
                self.fonts,
                theme,
                option_layout,
                theme.safe_margin_px + 102 + slide,
                y + (option_height - option_layout.height) / 2,
                role="medium",
                alpha=round(255 * option_progress),
                line_gap=4,
            )
            if correct and option_progress > 0:
                check_progress = min(1.0, option_progress * 1.5)
                check_x = theme.canvas.width - theme.safe_margin_px - 66 + slide
                check_y = y + option_height / 2
                first = (check_x - 13, check_y + 1)
                middle = (check_x - 3, check_y + 12)
                end = (check_x + 18, check_y - 14)
                if check_progress < 0.5:
                    ratio = check_progress * 2
                    points = (first, (first[0] + (middle[0] - first[0]) * ratio,
                                      first[1] + (middle[1] - first[1]) * ratio))
                else:
                    ratio = (check_progress - 0.5) * 2
                    points = (first, middle, (middle[0] + (end[0] - middle[0]) * ratio,
                                               middle[1] + (end[1] - middle[1]) * ratio))
                canvas.line(points, (*theme.colors["text"], round(255 * option_progress)), width=7)
        draw_footer(canvas, self.fonts, theme)
        return canvas.final_rgb()
