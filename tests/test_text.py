from pathlib import Path

import pytest
from PIL import ImageFont

from solution_video.engine.text import fit_text, reveal_chars, reveal_words, wrap_text


ROOT = Path(__file__).resolve().parents[1]
FONT = ROOT / "fonts" / "Poppins-Regular.ttf"


def test_wrap_and_reveals():
    font = ImageFont.truetype(FONT, 36)
    lines = wrap_text("one two three four", font, round(font.getlength("one two")))
    assert len(lines) >= 2
    assert reveal_words("one two three", 0.5) == "one two"
    assert reveal_chars("abcdef", 0.5) == "abc"


def test_fit_text_respects_limits():
    layout = fit_text("A measured line of text", str(FONT), 400, 120, 48, 36, 2)
    assert layout.font_size >= 36
    assert len(layout.lines) <= 2
    with pytest.raises(ValueError):
        fit_text("a very long sentence " * 20, str(FONT), 100, 30, 36, 36, 1)
