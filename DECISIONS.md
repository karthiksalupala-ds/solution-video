# DECISIONS.md

## Decided (2026-10-14)
- Separate repo `solution-video` (not inside the WhatsApp bot repo). Bot only consumes `solution.mp4`.
- Core = Python library + CLI first. MCP/HTTP wrapper later, only after 2+ real consumers exist.
- Bot integration: same GitHub Actions run as the 6 PM job renders then sends via Green API `sendFileByUpload`; any failure falls back to the existing text solution.
- Output spec: mp4, H.264 + AAC, 720x1280, 30 fps, <= 16 MB.
- Voice language: Tanglish (Telugu + English mix). Exact script format decided AFTER the listening test (phase 5).
- Never invent company/source names. Accuracy gate blocks unverifiable answers.
- Credits are limited: build the MVP first (phases 1, 2, 4, 6, 7 with `--no-voice`), then polish (phase 3), voice (phase 5), reviewer (10).
- Rendering: Pillow-first, with cached 720p layers and selective 2x supersampling for vector-heavy elements. HTML/CSS is a future isolated fallback, not the default pipeline.
- v0.1 ships with `--no-voice`; voice integration waits for the Phase 5 listening test.
- Accuracy: block every answer that cannot be machine-verified. There is no faculty-review override in v0.1. A block exits 2, writes `answer_verified:false`, creates no video, and lets the bot send its existing text solution.
- Runtime: 75 seconds is the hard maximum.
- Fonts: ship Poppins as package data; Phase 1 adds the official `OFL.txt` under `fonts/` and never relies on system fonts.
- LLM steps: support both Groq and Gemini adapters, selected by environment configuration in Phase 4.
- Voice fallback strategy: Chatterbox Multilingual HF Space → edge-tts → valid silent timeline. The final voice, script mode, and provider preference remain intentionally deferred until the Phase 5 listening test.
