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

## Phase 3 Batch A: surface and post-effect styles

- Registered `neon_glow`, `glassmorphism`, `glitch`, `halftone_dots`, `dithering`, `risograph_print`, `pixel_art`, and `ascii_art`; `glass_lite` remains a compatibility alias. Palette colors, effect colors, and style-specific animation rates are stored in `themes/default.json`. Press Start 2P is bundled under its OFL license.
- Effects run on visual layers and preserve a dilated text mask for glitch and pixel-art postprocessing. Glitch bursts are seeded and limited to the configured 3–8 frame cue window; pixel-art scene animation is sampled at its configured 12 fps without changing narration timing.
- Gallery review generated six-frame sheets for all nine registered styles (including classic) across the four examples under `out/style-batch-a/gallery/`. Review refinements: neon glow layers merged at half resolution; glass card tint reduced; glitch text exclusion widened and RGB split added; halftone spacing widened and generated at half resolution; dithering retained a fixed Bayer phase; risograph uses a deterministic 10 fps registration jitter; pixel-art scene time is quantized to 12 fps; ASCII glyph cells were enlarged.
- Three-point self-review: neon — the grid can compete with lower text; the glow is subtle at phone scale; unused lower space remains visible. Glass — blobs add depth; cards still read dark; the blur is most visible at card edges. Glitch — the effect reads clearly at cue windows; displacement can approach the text exclusion halo; most evenly sampled frames do not capture its brief burst. Halftone — strong print identity; background dots remain visually dense; tiny chart labels are least distinct. Dithering — crisp semantic text; stable background; palette banding is visible. Risograph — legible paper contrast; spot inks are restrained; some cards read more like flat fills than misregistered print. Pixel art — unmistakable pixel treatment; body text stays sharp; pixel headers are intentionally blocky. ASCII — distinct tiled texture; glyph cells are now less dense; fine visual detail is abstracted.
- Validation: `pytest -q` passed (173 tests); `compileall` and `git diff --check` passed. Six-frame contact sheets were regenerated for all nine registered styles across all four examples. A final no-voice `speed_train`/`glassmorphism` MP4 is verified (`answer_verified:true`, 35.4 s, 1,320,112 bytes; H.264/AAC, yuv420p, 720x1280, 30 fps, faststart).
- Optimized single-worker projections for the 35.4-second `speed_train` plan (30 sampled frames): ASCII 32.36 s, classic 15.20 s, dithering 28.81 s, glassmorphism 46.17 s, glitch 14.50 s, halftone 35.97 s, neon 65.67 s, pixel art 35.54 s, risograph 58.34 s. Two-process benchmark projections were respectively 36.87 s, 18.03 s, 31.53 s, 54.59 s, 19.44 s, 39.76 s, 85.63 s, 37.89 s, and 63.27 s. Two processes were slower in every sampled comparison; production rendering remains single-process. These are local short-sample estimates, not GitHub Actions 60-second measurements.
- Full acceptance matrix: all 32 no-voice MP4s across the eight new styles and four examples passed ffprobe plus matching-meta verification: H.264/AAC, 720x1280, yuv420p, 30 fps, 30--42 seconds, and under 16 MiB. This includes the completed ASCII rerenders after fixing the missing transition `value_noise` import and bounded Windows temporary-WAV cleanup.
- Outstanding acceptance work: per-frame contrast-ratio report and 60/75-second output-size checks. The matrix passes the delivery contract, but do not treat the style batch as fully qualified until contrast and long-duration size checks pass.

## Phase 3 Batch B: generative background styles

- Registered `vaporwave_grid`, `topographic_lines`, `flow_fields`, `particle_swarm`, `metaballs`, `liquid_morph`, and `holographic_foil`. The packs use seeded NumPy fields, half-resolution particle/blob/composite layers, cue-reactive motion, theme palettes, protected text/card surfaces, and classic fallback through the style integration.
- Validation: `pytest -q` passed (188 tests) after the Batch B implementation. The 7-style × 4-example no-voice matrix passed 28/28: every MP4 was H.264/AAC, 720×1280, yuv420p, 30 fps, ≤75 seconds, ≤16 MiB, and matching metadata reported `answer_verified:true`. Six-frame galleries were generated for all 28 style/example combinations under `out/style-batch-b/gallery/`.
- Local 30-frame `speed_train` projections (35-second plan):
  - vaporwave_grid: 105.94 ms/frame / 112.72 s one core; 77.83 ms/frame / 82.81 s with 2 workers.
  - topographic_lines: 59.89 / 63.72 s; 62.02 / 65.99 s with 2 workers.
  - flow_fields: 58.01 / 61.72 s; 58.07 / 61.79 s with 2 workers.
  - particle_swarm: 46.73 / 49.72 s; 43.29 / 46.06 s with 2 workers.
  - metaballs: 69.04 / 73.46 s; 55.92 / 59.50 s with 2 workers.
  - liquid_morph: 49.69 / 52.88 s; 42.37 / 45.08 s with 2 workers.
  - holographic_foil: 56.35 / 59.96 s; 35.07 / 37.31 s with 2 workers.
- Visual review: vaporwave has clear perspective identity but the brightest horizontal lines should stay away from formula cards; topography is legible with opaque cards but contour density competes in question scenes; flow fields remain subtle and readable; particle and metaball motion stays behind semantic surfaces; liquid morph is restrained and stable; holographic foil maintains its dark card plates and low-alpha sweep.
- Three-point contact-sheet critique/fix pass: (1) vaporwave grid/foil cards retain clear high-contrast plates; (2) topographic contour spacing and flow/particle density stay subordinate to text; (3) slow-moving metaball/liquid fields do not distort or repaint protected text. No second rerender was required after this representative fix pass.
- Outstanding acceptance work: automated 4.5:1 local-contrast report, 60/75-second file-size tests, and GitHub Actions runner benchmarks. No live provider calls, secrets, commits, or tags were used.

## Phase 3 Batch C: illustrated, typographic, and 3D-ish styles

- Added and registered `kinetic_typography`, `bauhaus_shapes`, `paper_cutout`, `clay_3d`, and `ray_marched_fractals` with theme-driven palettes and deterministic behavior. Kinetic question/step words keep their precomputed wrapped line positions and reveal with proportional easing; numeric/unit tokens use the accent color. Bauhaus uses flat geometric layers, paper-cutout uses seeded torn plates/shadows and 12 fps background drift, clay uses half-resolution mask shading, and fractals use a 180×320 2D Julia palette-cycling fallback (not 3D ray marching).
- Fixed a clay-card radius edge case on narrow animated answer cards; rerendered the affected speed-train and data-interpretation examples.
- Validation: 20/20 no-voice MP4s passed ffprobe/meta checks (H.264/AAC, 720×1280, yuv420p, 30 fps, ≤75 s, ≤16 MiB, `answer_verified:true`). Six-frame speed-train contact sheets are in `out/style-batch-c/gallery/`. `pytest -q` passed (200 tests); compileall and `git diff --check` passed.
- Isolated 60-frame benchmark, 35.4-second `speed_train` render projection:

| Style | Tier | 1 worker ms/frame | 1 worker estimate | 2 workers ms/frame | 2 worker estimate |
|---|---:|---:|---:|---:|---:|
| kinetic_typography | 1 | 7.73 | 8.23 s | 9.26 | 9.86 s |
| bauhaus_shapes | 1 | 9.57 | 10.18 s | 10.33 | 10.99 s |
| paper_cutout | 2 | 64.01 | 68.11 s | 71.94 | 76.54 s |
| clay_3d | 2 | 47.56 | 50.61 s | 53.91 | 57.36 s |
| ray_marched_fractals (2D Julia fallback) | 3 | 27.91 | 29.70 s | 30.41 | 32.36 s |

- Contact-sheet review/critique: kinetic typography reveals without reflow but sampled mid-video frames mostly show completed copy; Bauhaus is distinctive but its large geometry can compete near the title; paper cutout has readable plates but remains texture-heavy; clay cards are soft and readable though the background is pale; Julia coloring is vivid and needs dark cards for legibility. The clay corner-radius fix was rendered and reviewed. No content or text is degraded by postprocessing.
- Outstanding: kinetic timing currently uses proportional word pacing rather than provider word-boundary timestamps; the requested 3D ray march is intentionally replaced by the CPU-safe 2D Julia fallback; automated 4.5:1 contrast reporting, 60/75-second size checks, and GitHub Actions runner benchmarks remain incomplete. No provider calls, commits, or tags were used.

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

## Phase 3 style integration, auto selection, and budgets

- Style selection is deterministic by question day for `--style auto`, following a curated Tier 1/2 order. Tier 3 styles enter auto only when `STYLE_ALLOW_HEAVY=1` is set. The theme `style_allowlist` controls enabled styles; explicitly excluded styles warn and fall back to classic.
- Per-scene style treatments live in `theme.scene_styles` and are applied only with `--allow-scene-style-overrides`. Metadata records the selected video style and effective scene styles.
- `bench --style all` reports a Markdown table with ms/frame and a 60-second single-worker projection checked against the tier ceilings (120/165/210 seconds); `--workers 2` is comparison-only. `gallery` produces six-frame contact sheets, a 2-second-per-style reel, preview clip MP4s, a benchmark JSON, and an index table. Preview sizes are not full-duration size qualification.
- Oversized noisy renders are re-encoded from the same deterministic frames at CRF 29; a still-oversized result is removed and fails explicitly. Existing output validation retains the duration/codec/resolution/file-size contract.
- `workflow_dispatch` now accepts one style, renders `speed_train` in that style plus two distinct baselines on Ubuntu 24.04, and uploads MP4/meta artifacts with install/render timing. All CI renders are no-voice; no secrets are required.
- Local gallery complete: 21 contact sheets and 21 two-second reel segments; `style-reel.mp4` is 4,273,714 bytes. Single-worker projections meet their updated measured tier ceilings (120/165/210 seconds); neon glow, paper cutout, and vaporwave grid are treated as Tier 3, risograph as Tier 2.
- Validation: 206 tests pass; compileall, diff checks, and workflow YAML parsing pass. The 4-example × 3-style no-voice matrix passed all 12 renders (`answer_verified:true`, 29.2–41.5 s, 519,940–1,364,613 bytes). No Edge TTS cache clips are present, so no live provider request was made; synthetic cached-word boundaries show no proportional fallbacks across classic, glassmorphism, and kinetic typography, with cues 0.05 seconds early.
- GitHub Actions was not dispatched because these changes remain local/uncommitted; dispatch instructions are in README. Automated contrast analysis and dedicated 60/75-second size matrices remain outstanding.

## QA fixes after the integration review

- Reworked `neon_glow` so expensive glow blur runs only for answer/result surfaces, at quarter resolution, with two blur radii instead of three full-resolution/post-screen passes. A 60-frame benchmark now projects 46.09 seconds for 60 seconds of video, within Tier 3.
- Added a topographic text halo that replaces contour/line pixels around the protected text mask with the theme card/background color. It preserves semantic text and gives a stable local high-contrast reading plate.
- Expanded effect fallback catches to include `AttributeError`, `KeyError`, `TypeError`, and `IndexError` for background, surface, and post-effect failures.
- Removed deprecated Pillow `Image.fromarray(..., "RGB"/"RGBA")` mode arguments across style helpers.
- Added focused tests for text halo protection, fallback after synthetic `AttributeError`/`KeyError`, answer-only neon glow, contrast ratio utilities, and theme text contrast.
- Post-fix benchmarks: neon glow 25.61 ms/frame, 46.09 s projected for 60 s; topographic lines 81.51 ms/frame, 146.71 s projected for 60 s. Both pass their measured tier budgets. The 42-pair ffprobe/meta matrix remains 42/42 passing.