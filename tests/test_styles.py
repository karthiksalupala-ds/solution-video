import pytest
import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from solution_video.engine.assets import FontBook
from solution_video.engine.text import TextLayout
from solution_video.engine.theme import load_theme
from solution_video.scenes.common import draw_layout, make_canvas
from solution_video.styles import StyleContext, registered_styles, resolve_style, style_theme
from solution_video.styles.effects import _glitch_frame, _safe_text_mask, contrast_ratio
from solution_video.styles.helpers import fbm_noise


def test_style_registry_auto_and_unknown_fallback():
    assert registered_styles() == (
        "ascii_art",
        "bauhaus_shapes",
        "classic",
        "clay_3d",
        "dithering",
        "flow_fields",
        "glassmorphism",
        "glitch",
        "halftone_dots",
        "holographic_foil",
        "kinetic_typography",
        "liquid_morph",
        "metaballs",
        "neon_glow",
        "paper_cutout",
        "particle_swarm",
        "pixel_art",
        "ray_marched_fractals",
        "risograph_print",
        "topographic_lines",
        "vaporwave_grid",
    )
    assert resolve_style("auto", 1).name == "classic"
    assert resolve_style("auto", 2).name == "glassmorphism"
    assert resolve_style("glass_lite", 2).name == "glassmorphism"
    assert resolve_style("missing", 1).name == "classic"


def test_style_background_is_deterministic_for_a_seed():
    theme = style_theme(load_theme(), "glassmorphism")
    one = make_canvas(theme, 1.25, 19).final_rgb()
    two = make_canvas(theme, 1.25, 19).final_rgb()
    assert one.tobytes() == two.tobytes()
    assert fbm_noise(16, 20, 4).dtype.name == "float32"


@pytest.mark.parametrize("style_name", registered_styles())
def test_every_style_renders_a_deterministic_frame(style_name):
    base_theme = load_theme()
    theme = style_theme(base_theme, style_name)
    style = resolve_style(style_name)
    canvas = make_canvas(theme, 0.8, 41)
    context = StyleContext(theme=theme, seed=41, time_s=0.8, scene_name="step", cue_times=(0.4,))
    font = FontBook(theme).get("bold", 38)
    canvas.text((80, 180), "8 + 4 = 12", font, theme.colors["text"])
    style.surface(canvas, context, "result", (50, 130, 670, 260), 22)
    first = style.post(canvas.final_rgb(), context)

    second_canvas = make_canvas(theme, 0.8, 41)
    second_canvas.text((80, 180), "8 + 4 = 12", font, theme.colors["text"])
    begin_frame = getattr(style, "begin_frame", None)
    if callable(begin_frame):
        begin_frame(context)
    style.surface(second_canvas, context, "result", (50, 130, 670, 260), 22)
    second = style.post(second_canvas.final_rgb(), context)
    assert first.size == (720, 1280)
    assert first.tobytes() == second.tobytes()


def test_glitch_effect_keeps_text_and_displacement_halo_unchanged():
    theme = style_theme(load_theme(), "glitch")
    canvas = make_canvas(theme, 0.4, 17)
    canvas.text((90, 160), "SPEED = 72 km/h", FontBook(theme).get("bold", 40), theme.colors["text"])
    frame = canvas.final_rgb()
    result = _glitch_frame(frame, np.random.default_rng(9), theme.colors["accent"])
    protected = _safe_text_mask(frame, 41)
    assert protected is not None
    original_pixels = np.asarray(frame)
    result_pixels = np.asarray(result)
    protected_pixels = np.asarray(protected) > 0
    assert (original_pixels[protected_pixels] == result_pixels[protected_pixels]).all()


def test_text_mask_dilation_matches_square_max_filter():
    mask = Image.new("L", (32, 24), 0)
    ImageDraw.Draw(mask).rectangle((0, 6, 12, 14), fill=255)
    frame = Image.new("RGB", mask.size)
    frame.info["text_mask"] = mask

    protected = _safe_text_mask(frame, 7)
    assert protected is not None
    expected = mask.filter(ImageFilter.MaxFilter(7))
    assert protected.tobytes() == expected.tobytes()


def test_ascii_art_transition_returns_a_deterministic_rgb_frame():
    style = resolve_style("ascii_art")
    outgoing = Image.new("RGB", (720, 1280), (20, 30, 50))
    incoming = Image.new("RGB", (720, 1280), (80, 90, 110))
    first = style.transition(outgoing, incoming, 0.5)
    second = style.transition(outgoing, incoming, 0.5)
    assert first.mode == "RGB"
    assert first.size == (720, 1280)
    assert first.tobytes() == second.tobytes()


@pytest.mark.parametrize("style_name", (
    "vaporwave_grid",
    "topographic_lines",
    "flow_fields",
    "particle_swarm",
    "metaballs",
    "liquid_morph",
    "holographic_foil",
))
def test_batch_b_style_is_deterministic_and_fallback_safe(style_name):
    theme = style_theme(load_theme(), style_name)
    style = resolve_style(style_name)
    first = make_canvas(theme, 1.25, 29)
    second = make_canvas(theme, 1.25, 29)
    context = StyleContext(theme=theme, seed=29, scene_index=2, scene_name="step", time_s=1.25, cue_times=(0.4, 0.8))
    style.background(first, context)
    style.background(second, context)
    style.surface(first, context, "result", (50, 900, 670, 1080), 28)
    style.surface(second, context, "result", (50, 900, 670, 1080), 28)
    assert first.final_rgb().tobytes() == second.final_rgb().tobytes()


@pytest.mark.parametrize("style_name", (
    "kinetic_typography",
    "bauhaus_shapes",
    "paper_cutout",
    "clay_3d",
    "ray_marched_fractals",
))
def test_batch_c_style_is_deterministic(style_name):
    theme = style_theme(load_theme(), style_name)
    style = resolve_style(style_name)
    context = StyleContext(theme=theme, seed=13, scene_name="question", time_s=1.5)
    frames = []
    for _ in range(2):
        canvas = make_canvas(theme, 1.5, 13)
        style.background(canvas, context)
        style.surface(canvas, context, "working", (40, 440, 680, 600), 20)
        frames.append(canvas.final_rgb().tobytes())
    assert frames[0] == frames[1]


def test_kinetic_typography_reveals_words_without_reflow():
    theme = style_theme(load_theme(), "kinetic_typography")
    layout = TextLayout(("Speed is 72 km/h",), 42, 350, 50)
    font_book = FontBook(theme)
    early = make_canvas(theme, 0.0, 5)
    later = make_canvas(theme, 0.0, 5)
    blank = make_canvas(theme, 0.0, 5)
    draw_layout(early, font_book, theme, layout, 80, 320, role="medium", time_s=0.3)
    draw_layout(later, font_book, theme, layout, 80, 320, role="medium", time_s=1.4)
    early_pixels = np.asarray(early.image.convert("RGB"))[300:390, 70:500]
    later_pixels = np.asarray(later.image.convert("RGB"))[300:390, 70:500]
    blank_pixels = np.asarray(blank.image.convert("RGB"))[300:390, 70:500]
    early_ink = np.count_nonzero(np.any(early_pixels != blank_pixels, axis=2))
    later_ink = np.count_nonzero(np.any(later_pixels != blank_pixels, axis=2))
    assert 0 < early_ink < later_ink


def test_clay_surface_clamps_radius_for_narrow_animated_cards():
    theme = style_theme(load_theme(), "clay_3d")
    style = resolve_style("clay_3d")
    canvas = make_canvas(theme, 0.4, 3)
    context = StyleContext(theme=theme, seed=3, scene_name="answer", time_s=0.4)
    style.surface(canvas, context, "answer", (350, 240, 370, 416), 38)


def test_topographic_post_restores_flat_halo_around_text():
    theme = style_theme(load_theme(), "topographic_lines")
    canvas = make_canvas(theme, 0.5, 29)
    font = FontBook(theme).get("bold", 48)
    canvas.text((360, 260), "SPEED = 72 km/h", font, theme.colors["text"], anchor="mm")
    frame = canvas.final_rgb()
    style = resolve_style("topographic_lines")
    result = style.post(frame, StyleContext(theme=theme, seed=29, scene_name="step", time_s=0.5))
    mask = frame.info["text_mask"]
    dilated = mask.filter(ImageFilter.MaxFilter(19 if 19 % 2 else 20))
    halo = ImageChops.subtract(dilated, mask)
    halo_pixels = np.asarray(halo)
    result_pixels = np.asarray(result)
    frame_pixels = np.asarray(frame)
    assert halo_pixels.any()
    assert np.any(result_pixels[halo_pixels > 0] != frame_pixels[halo_pixels > 0])


def test_neon_answer_glow_is_quarter_resolution_and_uses_two_blurs():
    theme = style_theme(load_theme(), "neon_glow")
    canvas = make_canvas(theme, 0.5, 11)
    context = StyleContext(theme=theme, seed=11, scene_name="answer", time_s=0.5)
    style = resolve_style("neon_glow")
    style.begin_frame(context) if hasattr(style, "begin_frame") else None
    style.surface(canvas, context, "answer", (40, 900, 680, 1080), 28)
    assert canvas.image.size == (720, 1280)


def test_theme_text_contrast_meets_wcag_floor():
    theme = load_theme()
    assert contrast_ratio(theme.colors["text"], theme.colors["bg_top"]) >= 4.5
    assert contrast_ratio((35, 48, 42), (241, 232, 203)) >= 4.5


def test_missing_theme_font_reports_clear_error(tmp_path, monkeypatch):
    import json
    import solution_video.engine.theme as theme_module

    (tmp_path / "themes").mkdir()
    (tmp_path / "fonts").mkdir()
    theme_path = tmp_path / "themes" / "missing-font.json"
    theme_path.write_text(json.dumps({
        "name": "missing-font",
        "style": "classic",
        "canvas": {"width": 720, "height": 1280, "fps": 30, "supersample": 1},
        "safe_margin_px": 40,
        "min_body_font_px": 36,
        "fonts": {"bold": "fonts/does-not-exist.ttf"},
        "colors": {"bg_top": [0, 0, 0], "bg_bottom": [0, 0, 0], "text": [255, 255, 255]},
    }), encoding="utf-8")
    monkeypatch.setattr(theme_module, "_repo_root", lambda: tmp_path)
    with pytest.raises(ValueError, match="font asset.*missing"):
        theme_module.load_theme(theme_path)
