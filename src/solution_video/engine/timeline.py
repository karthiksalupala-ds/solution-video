"""Immutable clip timeline with crossfade overlap mapping."""

from __future__ import annotations

from dataclasses import dataclass

from .easing import clamp


@dataclass(frozen=True)
class Cue:
    """A named reveal position relative to a scene's duration."""

    name: str
    progress: float

    def __post_init__(self) -> None:
        if not self.name or not 0.0 <= self.progress <= 1.0:
            raise ValueError("Cue name must be non-empty and progress must be between 0 and 1")


@dataclass(frozen=True)
class SceneTiming:
    """Maps scene-local time and named cues onto an overridable duration."""

    base_duration_s: float
    duration_s: float
    cues: tuple[Cue, ...] = ()
    event_positions: tuple[Cue, ...] = ()

    def __post_init__(self) -> None:
        if self.base_duration_s <= 0 or self.duration_s <= 0:
            raise ValueError("Scene durations must be positive")
        if len({cue.name for cue in self.cues}) != len(self.cues):
            raise ValueError("Cue names must be unique within a scene")

    def to_base_time(self, time_s: float) -> float:
        progress = clamp(time_s / self.duration_s)
        cue_map = {cue.name: cue.progress for cue in self.cues}
        points = [(0.0, 0.0)]
        points.extend(
            (cue_map[event.name], event.progress)
            for event in self.event_positions
            if event.name in cue_map
        )
        points.append((1.0, 1.0))
        points.sort()
        for (left_target, left_source), (right_target, right_source) in zip(points, points[1:]):
            if progress <= right_target:
                width = right_target - left_target
                if width <= 0:
                    return right_source * self.base_duration_s
                ratio = clamp((progress - left_target) / width)
                return (left_source + (right_source - left_source) * ratio) * self.base_duration_s
        return self.base_duration_s

    def cue_time(self, name: str) -> float:
        for cue in self.cues:
            if cue.name == name:
                return self.duration_s * cue.progress
        raise KeyError(f"Unknown scene cue: {name}")


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
