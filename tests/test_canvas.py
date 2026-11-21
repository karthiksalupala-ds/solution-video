from solution_video.engine.canvas import Canvas


def test_gradient_interpolates_rows_and_preserves_endpoints():
    canvas = Canvas(2, 3)
    canvas.gradient((0, 20, 40), (100, 120, 140))

    assert canvas.image.getpixel((0, 0)) == (0, 20, 40, 255)
    assert canvas.image.getpixel((1, 1)) == (50, 70, 90, 255)
    assert canvas.image.getpixel((0, 2)) == (100, 120, 140, 255)


def test_cropped_overlays_preserve_alpha_and_clip_to_canvas_edges():
    canvas = Canvas(12, 12, track_text_mask=True, background=(0, 0, 0))
    canvas.rounded_rect((-2, -2, 6, 6), 2, (255, 0, 0, 128))
    canvas.line(((2, 2), (11, 11)), (0, 255, 0, 128), width=3)

    pixel = canvas.image.getpixel((4, 4))
    assert pixel[3] == 255
    assert pixel[0] > 0 and pixel[1] > 0
    assert canvas.image.getpixel((11, 0)) == (0, 0, 0, 255)
