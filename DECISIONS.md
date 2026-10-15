# DECISIONS.md

## Decided (2026-10-14)

- Separate repo `solution-video` (not inside the WhatsApp bot repo). Bot only consumes `solution.mp4`.
- Core = Python library + CLI first. MCP/HTTP wrapper later, only after 2+ real consumers exist.
- Bot integration: the 6 PM GitHub Actions job renders then sends with Green API `sendFileByUpload`; any failure falls back to the existing text solution.
- Output: MP4, H.264 + AAC, 720x1280, 30 fps, no more than 16 MB.
- Voice language is Tanglish; the exact script format is decided after the Phase 5 listening test.
- Never invent company/source names. The accuracy gate blocks unverifiable answers.
- MVP order is phases 1, 2, 4, 6, and 7 with `--no-voice`; then motion polish, voice, and review.
- Rendering is Pillow-first with cached 720p layers and selective 2x supersampling. HTML/CSS is a future isolated fallback, not the default path.
- v0.1 ships with `--no-voice`; voice integration waits for the listening test.
- Every answer that cannot be machine-verified is blocked. There is no faculty-review override in v0.1. A block exits 2, writes `answer_verified:false`, creates no video, and lets the bot send its text solution.
- 75 seconds is the hard runtime maximum.
- Poppins ships as package data with the official `fonts/OFL.txt`; code never relies on system fonts.
- Phase 4 supports both Groq and Gemini adapters, selected by environment configuration.
- Voice fallback is Chatterbox Multilingual HF Space, then edge-tts, then a valid silent timeline. Voice, script mode, and provider preference remain deferred to the Phase 5 listening test.

## Phase 1 implementation notes

- Engine: 720p Pillow master canvas, optional supersampled layers, real RGBA alpha compositing, bundled-font loading, deterministic synthesized SFX, and raw-frame FFmpeg piping. The hello smoke scene reads visible copy from JSON/theme data.
- Validation: local FFmpeg is absent. The encoder returns a clear error rather than generating an invalid file; its MP4 integration test will run in GitHub Actions where FFmpeg is installed.

## Known Phase-1 gaps

- Phase 1 intentionally has no answer schema, accuracy gate, aptitude scene catalog, LLM steps, narration, or bot integration.
- The sandbox prevents copying binary font files into `src/` package data. Clean-clone repository runs use `fonts/`; installed-wheel font packaging is deferred to Phase 6.

## Phase 2 implementation notes

- Input accepts the checked-in `today.json` plus `expected_steps` examples and the canonical `SolutionSpec` contract. Legacy string options and string plugin names are normalized at the boundary.
- Generic title, question, step, answer, tip, and outro renderers are registered by scene type. No aptitude topic, day, answer, or branding copy is embedded in them.
- No-voice duration is reading-time based and capped by `time_sec` or 75 seconds. Phase 2 deliberately marks `answer_verified:false`; the mandatory gate arrives in Phase 4.

## Known Phase-2 gaps

- FFmpeg remains unavailable locally, so the three MP4 encodes and output-size checks must run in GitHub Actions or an FFmpeg-enabled machine.
- Long content currently raises a clear layout error rather than automatically splitting one step across multiple scenes; automatic splitting is deferred to motion/layout refinement.

## Phase 4 implementation notes

- `solution-video steps` turns a valid `today.json` into a bound, checked `SolutionSpec`; `render-from-today` only starts rendering after the same gate passes.
- Groq and Gemini use swappable REST adapters with timeouts, three total attempts (initial plus two retries), strict JSON extraction, and no secret logging. The instruction prompt is checked in at `src/solution_video/llm/prompts/solution_to_steps.md`.
- The mandatory gate compares generated answer and option to the authoritative input and safely evaluates display equalities. It blocks wrong answers, false arithmetic, missing required fields, and unapproved source fields with exit code 2 and blocked meta JSON.

## Known Phase-4 gaps

- The optional independent second-LLM sanity pass is intentionally disabled until provider reliability and cost are measured.
- Live Groq validation passes for all three Phase-2 examples. Gemini's initial default was discontinued for this account; its adapter now defaults to the current model Google recommends in the API response, but this account received an HTTP 503 during one live attempt. Keep model defaults configurable in a future package phase.
