"""The existing dark-gradient treatment expressed as a style pack."""

from __future__ import annotations

from PIL import Image

from ..engine.canvas import Canvas
from .base import StyleContext


class ClassicStyle:
    name = "classic"
    tier = 1
    palette = ("bg_top", "bg_bottom", "text", "accent", "success", "info")
    sfx_profile = {"tick": 1.0, "ding": 1.0, "whoosh": 1.0}

    def background(self, canvas: Canvas, context: StyleContext) -> None:
        canvas.gradient(context.theme.colors["bg_top"], context.theme.colors["bg_bottom"])

    def surface(self, canvas: Canvas, context: StyleContext, kind: str, box: tuple[float, float, float, float], radius: float) -> None:
        color = "success" if kind in {"answer", "result"} else "info"
        alpha = round((232 if kind in {"answer", "result"} else 205) * context.opacity)
        canvas.rounded_rect(box, radius, (*context.theme.colors[color], alpha), (*context.theme.colors["text"], 60), 2)

    def text_fx(self, canvas: Canvas, context: StyleContext, box: tuple[float, float, float, float]) -> None:
        del canvas, context, box

    def transition(self, outgoing: Image.Image, incoming: Image.Image, progress: float) -> Image.Image:
        return Image.blend(outgoing, incoming, max(0.0, min(1.0, progress)))

    def post(self, frame: Image.Image, context: StyleContext) -> Image.Image:
        del context
        return frame
