"""Generic calculation-step scene."""

from __future__ import annotations

import warnings

from ..engine.assets import FontBook
from ..engine.easing import out_cubic, progress_at
from ..engine.text import reveal_chars
from ..engine.theme import Theme
from ..schema import StepSpec
from ..plugins import draw_visual
from .common import draw_footer, draw_header, draw_layout, fit, make_canvas


class StepScene:
    def __init__(self, step: StepSpec, step_index: int, step_count: int, theme: Theme) -> None:
        self.step, self.step_index, self.step_count, self.theme, self.fonts = step, step_index, step_count, theme, FontBook(theme)
        self._visual_warning_emitted = False

    def render_frame(self, time_s: float, *, visual_time_s: float | None = None):
        canvas, theme = make_canvas(self.theme, time_s, self.step_index), self.theme
        draw_header(canvas, self.fonts, theme, f"STEP {self.step_index} OF {self.step_count}", progress_at(time_s, 0, 0.3))
        margin = theme.safe_margin_px
        dot_radius = theme.motion.get("step_dot_radius_px", 10)
        dot_gap = theme.motion.get("step_dot_gap_px", 14)
        dots_width = self.step_count * dot_radius * 2 + max(0, self.step_count - 1) * dot_gap
        dots_start = theme.canvas.width - margin - dots_width
        for index in range(self.step_count):
            center_x = dots_start + dot_radius + index * (2 * dot_radius + dot_gap)
            fill = theme.colors["success"] if index + 1 == self.step_index else theme.colors["muted"]
            alpha = 245 if index + 1 <= self.step_index else 105
            canvas.ellipse(
                (center_x - dot_radius, 98 - dot_radius, center_x + dot_radius, 98 + dot_radius),
                (*fill, alpha),
            )
        label = fit(
            theme,
            "bold",
            self.step.label,
            theme.canvas.width - 2 * margin,
            130,
            theme.sizes.get("step_label_px", 48),
            2,
        )
        label_y = round(theme.canvas.height * 0.18)
        draw_layout(
            canvas,
            self.fonts,
            theme,
            label,
            margin,
            label_y,
            role="bold",
            color="text",
            alpha=round(255 * out_cubic(progress_at(time_s, 0.08, theme.motion["reveal_s"]))),
            line_gap=12,
        )
        line_count = len(self.step.lines)
        line_start = theme.motion.get("step_line_start_s", 0.55)
        line_stagger = theme.motion.get("step_line_stagger_s", 0.55)
        card_gap = theme.motion.get("step_card_gap_px", 16)
        base_available_height = theme.canvas.height - label_y - label.height - 150
        min_card_height = theme.motion.get("step_card_min_height_px", 118)
        visual_reserve = theme.motion.get("plugin_reserve_height_px", 390) if self.step.visual else 0
        available_height = base_available_height - visual_reserve
        card_height = min(
            theme.motion.get("step_card_max_height_px", 188),
            (available_height - card_gap * (line_count - 1)) / line_count,
        )
        show_visual = self.step.visual is not None and card_height >= min_card_height
        if self.step.visual is not None and not show_visual:
            self._warn_visual_layout()
            card_height = min(
                theme.motion.get("step_card_max_height_px", 188),
                (base_available_height - card_gap * (line_count - 1)) / line_count,
            )
        base_y = label_y + label.height + 52
        for index, line in enumerate(self.step.lines):
            start_s = line_start + index * line_stagger
            progress = out_cubic(progress_at(time_s, start_s, theme.motion["reveal_s"]))
            y = base_y + index * (card_height + card_gap)
            drift = (1 - progress) * theme.motion.get("step_card_slide_px", 46)
            card_top, card_bottom = y + drift, y + card_height + drift
            canvas.rounded_rect(
                (margin, card_top, theme.canvas.width - margin, card_bottom),
                28,
                (*theme.colors["info"], round(208 * progress)),
                (*theme.colors["text"], round(58 * progress)),
                2,
            )
            working, separator, result = line.rpartition("=")
            if separator:
                working = reveal_chars(working.strip(), progress)
                result_text = reveal_chars(f"= {result.strip()}", progress)
                if working:
                    working_layout = fit(
                        theme,
                        "medium",
                        working,
                        theme.canvas.width - 2 * margin - 52,
                        card_height * 0.42,
                        theme.sizes.get("formula_work_px", 40),
                        2,
                    )
                    draw_layout(
                        canvas,
                        self.fonts,
                        theme,
                        working_layout,
                        margin + 26,
                        card_top + 18,
                        role="medium",
                        alpha=round(255 * progress),
                        line_gap=4,
                    )
                result_layout = fit(
                    theme,
                    "bold",
                    result_text or "= ",
                    theme.canvas.width - 2 * margin - 52,
                    card_height * 0.45,
                    theme.sizes.get("formula_result_px", 52),
                    2,
                )
                result_color = "accent" if self.step.emphasis and self.step.emphasis in line else "success"
                draw_layout(
                    canvas,
                    self.fonts,
                    theme,
                    result_layout,
                    margin + 26,
                    card_top + card_height * 0.51,
                    role="bold",
                    color=result_color,
                    alpha=round(255 * progress),
                    line_gap=2,
                )
            else:
                text = reveal_chars(line, progress)
                emphasized = self.step.emphasis is not None and self.step.emphasis in line
                layout = fit(
                    theme,
                    "bold",
                    text or " ",
                    theme.canvas.width - 2 * margin - 52,
                    card_height - 40,
                    theme.sizes.get("formula_result_px", 52) if emphasized else theme.sizes.get("formula_work_px", 44),
                    2,
                )
                draw_layout(
                    canvas,
                    self.fonts,
                    theme,
                    layout,
                    margin + 26,
                    card_top + (card_height - layout.height) / 2,
                    role="bold" if emphasized else "medium",
                    color="accent" if emphasized else "text",
                    alpha=round(255 * progress),
                    line_gap=4,
                )
        if show_visual and self.step.visual is not None:
            visual_top = base_y + line_count * (card_height + card_gap) + 24
            visual_bottom = theme.canvas.height - margin - theme.motion.get("plugin_footer_gap_px", 100)
            if visual_bottom - visual_top >= theme.motion.get("plugin_min_height_px", 170):
                draw_visual(
                    canvas,
                    self.step.visual,
                    (margin, visual_top, theme.canvas.width - margin, visual_bottom),
                    (
                        max(0.0, time_s - line_start)
                        if visual_time_s is None
                        else visual_time_s
                    ),
                    theme,
                    warn=not self._visual_warning_emitted,
                )
                if self.step.visual is not None:
                    self._visual_warning_emitted = True
            else:
                self._warn_visual_layout()
        draw_footer(canvas, self.fonts, theme)
        return canvas.final_rgb()

    def _warn_visual_layout(self) -> None:
        if self._visual_warning_emitted:
            return
        warnings.warn(
            f"Not enough room for {self.step.visual.name!r} visual; using the generic step scene",
            RuntimeWarning,
            stacklevel=2,
        )
        self._visual_warning_emitted = True
