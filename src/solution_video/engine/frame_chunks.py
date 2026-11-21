"""Deterministic, bounded chunk scheduling for expensive style frame loops."""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from typing import Callable, Iterable, TypeVar


T = TypeVar("T")


@dataclass(frozen=True)
class FrameChunk:
    index: int
    start: int
    stop: int


def chunks(frame_count: int, chunk_size: int = 60) -> tuple[FrameChunk, ...]:
    if frame_count < 0 or chunk_size <= 0:
        raise ValueError("frame_count must be non-negative and chunk_size must be positive")
    return tuple(FrameChunk(index, start, min(frame_count, start + chunk_size)) for index, start in enumerate(range(0, frame_count, chunk_size)))


def render_ordered(
    frame_count: int,
    render_chunk: Callable[[FrameChunk], list[T]],
    *,
    workers: int = 1,
    chunk_size: int = 60,
) -> Iterable[T]:
    """Yield chunks in frame order; multiprocessing is opt-in and bounded by chunks."""
    work = chunks(frame_count, chunk_size)
    if workers <= 1:
        for chunk in work:
            yield from render_chunk(chunk)
        return
    with ProcessPoolExecutor(max_workers=workers) as executor:
        # map preserves input order and therefore lets the caller stream safely to FFmpeg.
        for rendered in executor.map(render_chunk, work):
            yield from rendered
