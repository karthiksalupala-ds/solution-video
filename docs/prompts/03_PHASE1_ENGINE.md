# 03: PHASE 1: Scaffold + Engine + Hello-World video

Prerequisite: PLAN.md and DECISIONS.md exist and I approved them.

---
Read AGENTS.md, PLAN.md, DECISIONS.md. First show me your task plan and the exact file list; wait for "go".

## Goal
A clean repo skeleton and a generic engine that can render a trivial, beautiful hello-world video from a tiny JSON.
No topic-specific code.

## Build
1. Repo skeleton per AGENTS.md, `pyproject.toml` (dependencies pinned), `fonts/` with an open-license font family
   (use Poppins from Google Fonts; include its license file) and a font loader that resolves paths relative to the package
   (never system font paths) and fails loudly if missing.
2. `engine/canvas`: supersampled drawing (render at 2x, downscale), gradient backgrounds, rounded rects, circles, lines, polygons,
   alpha handling that is correct on non-flat backgrounds (use real alpha compositing, not color-mixing hacks).
3. `engine/text`: measure, wrap, auto-fit-to-box, anchors, per-word and per-char reveal helpers, outline/shadow option.
4. `engine/easing`: out-cubic, in-out, back/overshoot, spring, linear, clamp, lerp, stagger helpers.
5. `engine/timeline`: a scene/clip timeline with start, duration, crossfade/transition support; maps global time to local progress.
6. `engine/audio`: numpy synth SFX (pop, whoosh, tick, ding), mixer with gain and ducking, WAV writer, loudness normalize via ffmpeg.
7. `engine/encode`: stream raw frames to ffmpeg (H.264 + AAC, yuv420p, 720x1280, 30 fps, faststart, CRF tuned for <= 16 MB at 75 s),
   fail with a clear error if ffmpeg is missing.
8. CLI stub: `solution-video render --input examples/hello.json --out out.mp4 [--no-voice] [--theme themes/default.json]`.
9. `themes/default.json`: palette, fonts, sizes, safe margins, easing defaults, brand footer text (as DATA).
10. A hello-world scene using the engine (title + animated text + background + SFX) from `examples/hello.json`.

## Constraints
- Deterministic output. No global mutable state. No hard-coded colors/strings in engine code (read from theme).
- Fast: profile the frame loop; avoid per-frame allocations that can be cached (backgrounds, fonts, static layers).

## Definition of Done
- [ ] `pytest` passes (tests for easing, text wrap/fit, timeline mapping, encode smoke test).
- [ ] `render` produces a valid mp4: ffprobe shows h264+aac, 720x1280, 30 fps, size < 5 MB for 10 s.
- [ ] Render time reported; profile summary included.
- [ ] Contact sheet of 6 frames shown to me; text crisp, no jagged edges, no overflow.
- [ ] No fonts/paths outside the repo; works from a clean clone.
- [ ] DECISIONS.md updated; list of what is NOT done.
---
