"""Immutable clip timeline with crossfade overlap mapping."""

from __future__ import annotations

from dataclasses import dataclass

from .easing import clamp


@dataclass(frozen=True)
class Clip:
    name: str
    duration_s: float
    transition_s: float = 0.0

    def __post_init__(self) -> None:
        if self.duration_s <= 0 or self.transition_s < 0 or self.transition_s >= self.duration_s:
            raise ValueError("Clip duration must be positive and transition shorter than the clip")


@dataclass(frozen=True)
class ClipState:
    clip: Clip
    start_s: float
    local_s: float
    progress: float
    opacity: float


class Timeline:
    def __init__(self, clips: tuple[Clip, ...]) -> None:
        if not clips:
            raise ValueError("Timeline needs at least one clip")
        self.clips = clips
        starts: list[float] = []
        cursor = 0.0
        for clip in clips:
            starts.append(cursor)
            cursor += clip.duration_s - clip.transition_s
        self.starts = tuple(starts)
        self.duration_s = cursor + clips[-1].transition_s

    def active_at(self, time_s: float) -> tuple[ClipState, ...]:
        states: list[ClipState] = []
        for index, clip in enumerate(self.clips):
            start = self.starts[index]
            local = time_s - start
            if 0 <= local <= clip.duration_s:
                opacity = 1.0
                if clip.transition_s and index < len(self.clips) - 1 and local > clip.duration_s - clip.transition_s:
                    opacity = clamp((clip.duration_s - local) / clip.transition_s)
                states.append(ClipState(clip, start, local, clamp(local / clip.duration_s), opacity))
        return tuple(states)
