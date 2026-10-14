"""Generic data-driven hello scene used only to prove the Phase-1 engine."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Mapping

from ..engine.assets import FontBook
from ..engine.canvas import Canvas
from ..engine.easing import out_back, out_cubic, progress_at
from ..engine.text import fit_text, reveal_words
from ..engine.theme import Theme


@dataclass(frozen=True)
class HelloSpec:
    title: str
    message: str
    duration_s: float
    seed: int

    @classmethod
    def from_mapping(cls, data: Mapping[str, object]) -> "HelloSpec":
        try:
            title = str(data["title"]).strip()
            message = str(data["message"]).strip()
            duration_s = float(data.get("duration_s", 10.0))
            seed = int(data.get("seed", 1))
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("Hello input requires title, message, optional duration_s and seed") from exc
        if not title or not message or not 1 <= duration_s <= 75:
            raise ValueError("Hello title/message must be non-empty and duration_s must be 1..75")
        return cls(title, message, duration_s, seed)


class HelloScene:
    def __init__(self, spec: HelloSpec, theme: Theme) -> None:
        self.spec, self.theme = spec, theme
        self.fonts = FontBook(theme)
        randomizer = random.Random(spec.seed)
        self.particles = tuple((randomizer.randrange(0, theme.canvas.width), randomizer.randrange(80, theme.canvas.height - 100), randomizer.uniform(8, 24), randomizer.uniform(8, 28)) for _ in range(18))
        self.background = Canvas(theme.canvas.width, theme.canvas.height, background=theme.colors["bg_top"])
        self.background.gradient(theme.colors["bg_top"], theme.colors["bg_bottom"])

    def render_frame(self, time_s: float):
        theme, colors = self.theme, self.theme.colors
        canvas = Canvas(theme.canvas.width, theme.canvas.height, background=colors["bg_top"])
        canvas.composite(self.background.image)
        for x, y, radius, speed in self.particles:
            offset = (y + time_s * speed) % (theme.canvas.height + 120) - 60
            canvas.ellipse((x - radius, offset - radius, x + radius, offset + radius), (*colors["info"], 28))
        margin = theme.safe_margin_px
        title_progress = out_back(progress_at(time_s, 0.30, 0.55))
        layout = fit_text(self.spec.title, str(theme.fonts["bold"]), theme.canvas.width - 2 * margin, 310, theme.sizes["title_px"], max(36, theme.min_body_font_px), 3)
        title_font = self.fonts.get("bold", layout.font_size)
        y = 390 - layout.height / 2 + (1 - min(1.0, title_progress)) * 60
        title_alpha = round(255 * min(1.0, title_progress))
        for line in layout.lines:
            canvas.text((margin, y), line, title_font, (*colors["text"], title_alpha), stroke_width=1, stroke_fill=(*colors["bg_top"], round(190 * min(1.0, title_progress))))
            y += title_font.getbbox("Ag")[3] - title_font.getbbox("Ag")[1]
        card_progress = out_cubic(progress_at(time_s, 0.95, 0.40))
        card_top = 720 + (1 - card_progress) * 80
        card_height = 250
        canvas.rounded_rect((margin, card_top, theme.canvas.width - margin, card_top + card_height), 32, (*colors["info"], round(205 * card_progress)), (*colors["text"], round(80 * card_progress)), 2)
        message_font = self.fonts.get("medium", theme.sizes["body_px"])
        shown = reveal_words(self.spec.message, progress_at(time_s, 1.20, 1.8))
        message_layout = fit_text(shown or " ", str(theme.fonts["medium"]), theme.canvas.width - 2 * margin - 56, 180, theme.sizes["body_px"], theme.min_body_font_px, 4)
        message_font = self.fonts.get("medium", message_layout.font_size)
        canvas.text((theme.canvas.width / 2, card_top + card_height / 2), "\n".join(message_layout.lines), message_font, (*colors["text"], round(255 * card_progress)), anchor="mm")
        footer = str(theme.branding.get("footer_text", ""))
        if footer:
            canvas.text((theme.canvas.width / 2, theme.canvas.height - 58), footer, self.fonts.get("regular", theme.sizes["footer_px"]), (*colors["muted"], 210), anchor="mm")
        return canvas.final_rgb()
