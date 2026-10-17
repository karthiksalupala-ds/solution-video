"""solution-video: deterministic JSON-driven video rendering."""

__version__ = "0.2.0"

from .api import render, render_from_today
from .schema import Meta

__all__ = ["Meta", "__version__", "render", "render_from_today"]
