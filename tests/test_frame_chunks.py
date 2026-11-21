from solution_video.engine.frame_chunks import chunks, render_ordered


def test_chunk_schedule_and_single_process_order_are_deterministic():
    scheduled = chunks(7, 3)
    assert [(chunk.start, chunk.stop) for chunk in scheduled] == [(0, 3), (3, 6), (6, 7)]

    def render(chunk):
        return list(range(chunk.start, chunk.stop))

    assert list(render_ordered(7, render, workers=1, chunk_size=3)) == list(range(7))
