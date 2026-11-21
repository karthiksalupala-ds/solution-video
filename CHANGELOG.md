# Changelog

## 0.2.1 - 2026-11-21

- Add `concise` and `tutor` narration styles, with concise as the default.
- Add a short question-read cue and bounded question/title pacing.
- Reject identity, filler, and repeated-result equations in the accuracy gate.
- Add final peak limiting to protect rendered audio peaks while preserving mix level.
- Treat over-cap generated narration as an accuracy/output failure rather than speeding speech.

## 0.2.0 - 2026-10-17

- Add configurable voice providers, per-scene narration, audio mixing, caching, credit safeguards, captions, and narration/reveal synchronization.
- Polish scene motion and transitions, and add input-driven train-crossing and bar-chart visuals with generic-scene fallback.
- Strengthen solution verification and add an exact-fraction car-speed example.
- Update packaged version metadata and release documentation.

## 0.1.0 - 2026-10-15

- Expose the typed `Meta`, `render`, and `render_from_today` public API.
- Add CLI validation, dry-run planning, seed selection, and voice capability reporting.
- Validate rendered MP4 codecs, dimensions, pixel format, frame rate, audio, and size; retry oversized output at a lower bitrate.
- Package themes and fonts and add README, contributor guide, Apache-2.0 licensing, and GitHub Actions rendering workflow.
