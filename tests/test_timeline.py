from solution_video.engine.timeline import Clip, Timeline


def test_crossfade_maps_two_active_clips():
    timeline = Timeline((Clip("first", 3, 0.5), Clip("second", 2)))
    states = timeline.active_at(2.75)
    assert [state.clip.name for state in states] == ["first", "second"]
    assert states[0].opacity == 0.5
    assert states[1].progress == 0.125
    assert timeline.duration_s == 4.5
