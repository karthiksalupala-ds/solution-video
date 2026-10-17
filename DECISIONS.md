# DECISIONS.md

## Decided (2026-10-14)

- Separate repo `solution-video` (not inside the WhatsApp bot repo). Bot only consumes `solution.mp4`.
- Core = Python library + CLI first. MCP/HTTP wrapper later, only after 2+ real consumers exist.
- Bot integration: the 6 PM GitHub Actions job renders then sends with Green API `sendFileByUpload`; any failure falls back to the existing text solution.
- Output: MP4, H.264 + AAC, 720x1280, 30 fps, no more than 16 MB.
- Initial video narration language is English, based on the Phase 5 listening test; Telugu and Tanglish samples are retained only as exploratory comparisons.
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
- Groq model selection uses `GROQ_MODEL`, defaulting to `openai/gpt-oss-20b`; an explicitly passed model takes precedence.
- Phase 4 blocks generated solutions unless their checked step equations include a machine-evaluable result matching the numeric final answer; answer narration is required.
- LLM generation uses at most three HTTP attempts total per input, honors 429 Retry-After with capped exponential backoff, and allows at most two schema/accuracy repairs. Only gate-passing specs are cached by normalized question-input hash under ignored `out/.solution-video-cache/`.
- Phase 6 uses package data-files for repository themes/fonts so checkout and standard venv installations resolve the same assets. v0.1.0 exposes `Meta`, `render`, and `render_from_today`; speech synthesis remains deferred, so non-`--no-voice` renders explicitly report that only sound effects were produced.
- Rendered videos are validated with ffprobe against the fixed delivery contract. Oversized output receives one lower-bitrate H.264/AAC re-encode; invalid streams or a still-oversized result fail output validation.
- Apache-2.0 selected for the package. Release tag `v0.1.0` must be created against a release commit containing the package changes, not the pre-existing dirty workspace HEAD.

Prompt packs 05 and 07 in docs/prompts are superseded by prompts_one_by_one/1-4. Follow only the prompt I paste in the session.

- Phase 5 listening test keeps approved narration variants in JSON and provider adapters separate from video rendering. HF requests use the inspected `generate_tts_audio` endpoint and an explicit user-owned reference clip at `local_assets/ref_voice.wav` by default; `local_assets/` is Git-ignored. ElevenLabs synthesis needs separate credit approval and is capped at 1,500 estimated credits. If Telugu is revisited, use ElevenLabs `eleven_v4`, whose current docs list Telugu support, after selecting a suitable voice and confirming account access.
- Phase 4.1 selects English speech via `SPEECH_LANGUAGE_MODE`; generated step, tip, and answer narration follows that same mode, and the mode participates in the successful-steps cache key. Future voice-provider priority is ElevenLabs, Edge TTS, then HF Space. Voice synthesis implementation is unchanged.
- Phase 4.1 grounding requires the first evaluable step's operands to occur in the question or be recognized standard constants, rejects literal tautology/filler equations, and requires the final evaluated result to match the numeric answer. Individual work rates and data components must be calculated before combination.
- Phase 4.1 live Groq reruns did not return model JSON: both examples received HTTP 400 during Groq JSON-output validation; the error response provided no failed-generation detail. Do not claim a gate pass until live output is available.
- Phase 4.1.1 controlled Groq comparison isolated the HTTP 400 to JSON mode with the current prompt, not the model: `openai/gpt-oss-20b` accepted the v0.1.0 prompt, rejected the current prompt with `json_validate_failed`, then returned valid, gate-passing speed-train JSON with `response_format` disabled. Keep that model as default. The adapter retries JSON-validation errors once without JSON mode, forwards provider failed-generation details into the repair prompt, and caps completions at 4,096 tokens while detecting length truncation. The four-live-request budget is tracked across comparisons and post-fix examples.
- Within that four-request budget, the post-fix speed_train response passed schema and accuracy verification. The single post-fix time_work response was correctly blocked: the model rounded 1/12 and 1/24 to 0.0833 and 0.0417, making its displayed equalities false. No retries remained within the authorized live-call cap. Neither fixture was modified.
- Phase 4.1 follow-up: require exact fractions/integers and prohibit rounding except when source questions use decimals. Arithmetic/grounding/filler gate failures get exactly one repair with the verbatim gate reasons, still subject to the shared three-request cap. `GROQ_JSON_MODE=0|1` controls the initial JSON-mode setting; a `json_validate_failed` response disables JSON mode for later Groq providers in that process.
- The first follow-up live `time_work` result passed the gate with exact fractions. `di_average` exhausted its single live request at `finish_reason=length` under the former 4,096-token completion cap; the cap is raised to 8,192 and truncation remains explicit. It was not retried because the user authorized at most three total live calls.
- The third and final authorized follow-up live request, `percent_increase`, returned exact integer/fraction steps and passed the accuracy gate. `di_average` remains unverified live in this run; no fourth request was made.

## Phase 5 voice build (2026-10-16)

- Current video narration remains English. The earlier listening-test provider preference (ElevenLabs, Edge, HF) is superseded for routine rendering: default provider order is `hf_space,edge_tts,none`. ElevenLabs requires `--voice-provider elevenlabs`; automatic fallback from it is disabled unless `VOICE_ELEVENLABS_FALLBACK=1`.
- Each scene may override its duration and exposes normalized reveal cues. Voice clips are normalized/trimmed, cached by normalized text/provider/voice/model/language mode, mixed with ducked SFX, and recorded in metadata without secrets. `--no-voice` always skips TTS.
- ElevenLabs is guarded before every uncached synthesis request with the official `GET /v1/user/subscription` endpoint. The implementation uses `character_limit - character_count`, estimates one credit per submitted character, and fails closed if the usage response is unavailable or invalid; the configured reserve defaults to 1,500 characters/credits.
- Public-facing ElevenLabs renders enable theme-provided attribution text. Captions and scene-padding are theme settings. Videos remain capped at 75 seconds; padding is removed first and speech may be sped up by at most 12% before the renderer fails with a clear error.

## Phase 5 narration synchronization (2026-10-16)

- Edge TTS uses its `WordBoundary` stream metadata (`text`, `offset`) to align reveal cues; offsets are 100-nanosecond ticks converted to seconds. Other providers and Edge cues without a matching token retain proportional timing.
- Edge playback rate is configurable with `EDGE_TTS_RATE` and defaults to `-8%`. Word boundaries are cached beside each normalized audio clip and scaled to the processed clip duration.
- Equation-line cues anchor to their first spoken numeric operand, and question option cues anchor to their spoken option. Reveals lead the boundary by 0.05 seconds, within the 0.15-second limit.
- Question narration includes the options so each option can appear as it is spoken. Theme scene padding is 0.45 seconds.
- `solution-video render --sync-report` prints expected word-boundary and actual reveal times for QA.
- HF Space file inputs are identified from `Client.view_api(return_format="dict")` and wrapped with `gradio_client.handle_file`; the configured reference audio is resolved and checked before client use. HF warnings retain provider error details after credential redaction. `HF_TTS_REQUEST_LIMIT` and `HF_TTS_REQUEST_PAUSE_S` support bounded, paced runs.
- Per-scene voice metadata includes synthesized clip duration.

## Phase 3 Slice A: core scene motion and polish

- Core scenes use theme-configured type sizes, card spacing, reveal timings, background glow/particles, and answer confetti confined above the option rows. Step results are visually emphasized, progress dots reflect the current step, and the answer scene highlights the correct option.
- Scene boundaries crossfade the animated background and top header only; the outgoing scene's working content remains intact through the transition. Frame count, scene duration, cue positions, and narration offsets are unchanged.
- Reveal SFX follow existing option/line/answer cue positions at reduced gains. Visual changes do not adjust narration text, duration, or provider timing.
- Validation: `pytest -q` passed (141 tests). All four examples rendered with Edge TTS and passed answer verification and output checks: H.264/AAC, yuv420p, 720x1280 at 30 fps, under 16 MB and 75 seconds. Contact sheets are in `out/phase3/contact_sheets/`.

## Phase 3 Slice B: optional topic visuals

- Added input-driven `bar_chart` and `train_crossing` step visuals. Values, labels, highlighting, lengths, crossing duration, units, and marker copy come from each step's `visual.data`; plugin sizing, colors, and animation pacing come from the theme.
- Unknown plugins, invalid data, and layouts that cannot preserve readable calculation cards emit warnings and leave the generic step scene available. Steps without a visual continue to render unchanged.
- Contact-sheet review found three improvements: anchor front-entry/rear-exit markers to the platform boundaries and keep labels inside the frame; shorten the count-up and train animations so they finish within their narration scene; preserve enough equation-card height for multi-line steps before drawing a plugin. These were implemented, with tests covering visual animation, example wiring, and generic fallback.
- Validation: `pytest -q` passed (149 tests). All four examples rendered with Edge TTS, `answer_verified:true`, H.264/AAC, yuv420p, 720x1280 at 30 fps, and under 16 MB / 75 seconds. `speed_train` and `di_average` exercise the plugins; `time_work` and `percent_increase` validate the unchanged generic path. Final outputs and contact sheets are under `out/phase3/`.

## Phase 3 Slice B motion revision

- Revised the train visual into a scene-driven crossing: the train moves from front-at-entry to rear-at-exit, while a distance counter, elapsed time, platform progress, markers, rail, train details, and subdued skyline animate from the supplied dimensions. The distance heading is input-provided; motion, sizes, and palette remain theme-driven.
- Visual review identified three issues and fixes: train movement compressed after cue-time remapping, so plugin animation now uses scene-local time anchored to the step-label cue without changing narration or reveal cues; the crossing diagram was too bare, so it now has a progress HUD, physical platform markers, rail/train details, and skyline; integer DI values briefly displayed noisy decimals during count-up, so integer inputs animate as integers.
- The DI chart now grows bars in a staggered sequence over guide lines, with selected bars visibly outlined and pulsing; non-integer source values retain decimal count-up formatting.
- Validation: `pytest -q` passed (151 tests). All four Edge TTS renders have `answer_verified:true` and meet H.264/AAC, yuv420p, 720x1280 at 30 fps, under 16 MB and 75 seconds. Durations/sizes: `speed_train` 21.78 s / 794,880 B; `time_work` 19.51 s / 737,374 B; `di_average` 14.27 s / 586,396 B; `percent_increase` 15.15 s / 556,804 B. Refreshed contact sheets are in `out/phase3/contact_sheets/`.
- This remains deterministic local motion graphics; no generated-footage provider was added. Narration text, clip timing, cue positions, and provider behavior were not changed.

## v0.2.0 release qualification

- Corrected the train-crossing geometry so the train travels the full train-plus-platform distance before its rear clears the platform. The car-speed example now uses exact fractions and the generic visual path.
- Validation: `python -m pytest -q` passed (152 tests); `python -m compileall -q src tests` and `git diff --check` passed; `python -m pip wheel . --no-deps` built `solution_video-0.2.0-py3-none-any.whl`.
- Rendered all five examples without voice or live provider calls. Every output has `answer_verified:true`, H.264/AAC, yuv420p, 720x1280 at 30 fps, duration under 75 seconds, and size under 16 MiB. Durations/sizes: `speed_train` 35.4 s / 859,780 B; `time_work` 41.5 s / 909,596 B; `di_average` 30.9 s / 794,456 B; `percent_increase` 29.2 s / 660,561 B; `car_speed` 29.6 s / 669,597 B. These release-check outputs are in ignored `out/release-check/`.
- `.env` is ignored and untracked. The remote `main` is unchanged at `1bc300c`, and no remote `v0.2.0` tag exists; the release has not yet been committed or pushed.