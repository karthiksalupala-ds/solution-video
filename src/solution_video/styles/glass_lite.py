"""Small proof style: gradient blobs plus translucent surfaces."""

from __future__ import annotations

import math

from PIL import Image, ImageDraw

from ..engine.canvas import Canvas
from .base import StyleContext
from .helpers import gaussian_blur


class GlassLiteStyle:
    name = "glass_lite"
    tier = 1
    palette = ("bg_top", "bg_bottom", "text", "accent", "success", "info")
    sfx_profile = {"tick": 0.9, "ding": 1.0, "whoosh": 0.85}

    def background(self, canvas: Canvas, context: StyleContext) -> None:
        canvas.gradient(context.theme.colors["bg_top"], context.theme.colors["bg_bottom"])
        layer = Image.new("RGBA", canvas.image.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        phase = (context.time_s * 0.18 + context.seed * 0.013) % 1.0
        for index, color_name in enumerate(("accent", "info", "success")):
            x = canvas.width * (0.18 + 0.25 * index + 0.08 * math.sin(phase * math.tau + index))
            y = canvas.height * (0.20 + 0.22 * index + 0.08 * math.cos(phase * math.tau + index))
            radius = canvas.width * (0.30 - index * 0.03)
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=(*context.theme.colors[color_name], 42))
        canvas.composite(gaussian_blur(layer, 58))

    def surface(self, canvas: Canvas, context: StyleContext, kind: str, box: tuple[float, float, float, float], radius: float) -> None:
        alpha = round((188 if kind in {"answer", "result"} else 145) * context.opacity)
        tint = context.theme.colors["success"] if kind in {"answer", "result"} else context.theme.colors["text"]
        canvas.rounded_rect(box, radius, (*tint, alpha), (*context.theme.colors["text"], 112), 2)

    def text_fx(self, canvas: Canvas, context: StyleContext, box: tuple[float, float, float, float]) -> None:
        del canvas, context, box

    def transition(self, outgoing: Image.Image, incoming: Image.Image, progress: float) -> Image.Image:
        return Image.blend(outgoing, incoming, max(0.0, min(1.0, progress)))

    def post(self, frame: Image.Image, context: StyleContext) -> Image.Image:
        del context
        return frame
