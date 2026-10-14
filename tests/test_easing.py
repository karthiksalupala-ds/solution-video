from solution_video.engine.easing import clamp, in_out_cubic, out_back, out_cubic, progress_at, stagger


def test_easing_boundaries_and_overshoot():
    assert clamp(-1) == 0
    assert clamp(2) == 1
    assert out_cubic(0) == 0
    assert out_cubic(1) == 1
    assert in_out_cubic(0.5) == 0.5
    assert out_back(0.8) > 1


def test_progress_and_stagger():
    assert progress_at(3, 2, 2) == 0.5
    assert stagger(3, 0.12) == 0.36
