# Architecture Plan: solution-video

## 1. Goals and non-goals

Build a deterministic Python library and CLI that turns verified aptitude-question data into a polished, phone-readable 720x1280 MP4. It first serves the WhatsApp bot's evening solution but must remain generic for other topics and consumers. Every output also has a machine-readable meta file and is H.264/AAC/yuv420p/30fps/faststart at most 16 MB.

Quality means purposeful animation, rather than animated slides: 40 px safe margins, at least 36 px body type, one idea per scene, line-by-line calculation reveals, and a clear answer payoff. The same input, theme, and seed must yield the same frames. A failed accuracy check yields no MP4.

Non-goals for the MVP: solving arbitrary questions, guaranteeing an LLM is correct, a browser editor, source scraping, a general video editor, or bot/network code in the renderer. The system will not claim an unverified source or promise natural Tanglish TTS before listening tests.

The 3-minute target, 2x supersampling, 30 fps, and a 2--4 vCPU runner conflict if every frame is fully supersampled. The plan retains supersampling selectively and measures it in Actions. “Better than reference” must be established with contact sheets and phone review, not assumed from code.

## 2. Rendering approach comparison

| Approach | Quality and authoring | 60 s / 1,800 frames on 2--4 vCPU runner | Actions, determinism, fonts, extensibility |
| --- | --- | --- | --- |
| Pillow frames | Fine control for diagrams, counters, formula reveals, deterministic drawing. Bundled Poppins is good but needs careful layout. | **Target: 90--170 s render + 20--45 s encode** for cached 720p scenes; full-frame 2x can exceed 3 min. | Small dependency set, no browser install, deterministic when seeded. New scenes are Python renderers over a stable context. |
| HTML/CSS + Playwright screenshots | Best browser typography and simple flex/grid cards; precise frame seeking and bespoke diagrams are awkward. | Usually 3--8 min plus Chromium install/download. | Browser provisioning and version/font behavior increase flakiness; new cards easy, diagrams harder. |
| Hybrid | HTML cards plus Pillow diagrams. | Normally slower than optimized Pillow. | Two layout and dependency systems; reserve for a future editor need. |

**Decision: Pillow-first, with selective supersampling.** Render a 720x1280 master canvas, cache backgrounds/static cards/text layouts, and use 2x offscreen layers only for small vector-heavy elements or an explicitly opted-in scene. Downsample those layers with Lanczos and alpha-composite them. Stream raw `rgb24` frames to FFmpeg; never create thousands of PNGs.

**Fallback:** add an isolated HTML renderer behind the same scene contract only if a future branded template needs it and it passes the Actions benchmark. The immediate performance fallback is 1x master rendering and simpler plugin animation, never lower resolution, FPS, or typography.

## 3. Module design

All public data crossings use Pydantic models or typed dataclasses; renderers receive a `RenderContext`, never raw CLI arguments.

| Module | Responsibility and public surface | Must not know |
| --- | --- | --- |
| `__init__.py` | Version and stable re-exports: `render`, `render_from_today`. | CLI, providers, bot details. |
| `api.py` | Typed API: `render(...) -> Meta`, `render_from_today(...) -> Meta`. | Parsing and FFmpeg commands. |
| `cli.py` | `render`, `steps`, `render-from-today`, `validate`, `voice-test`; exit-code mapping. | Drawing and math. |
| `schema.py` | Pydantic contracts, parsing, normalization, useful errors. | Rendering, network, FFmpeg. |
| `pipeline.py` | Validate → steps → verify → voice/timeline → scenes → encode → output validation. | Shape drawing and plugin details. |
| `engine/canvas.py` | Canvas/layers, gradients, alpha-safe primitives, scaling/assets. | Problem content, TTS. |
| `engine/text.py` | Measure/wrap/fit, anchors, overflow reports, reveal plans. | Scene identity and source data. |
| `engine/easing.py` | Pure easing, clamp, lerp, stagger. | Pillow and content. |
| `engine/timeline.py` | Immutable clips, transitions, time mapping, render plan. | TTS implementation and layout. |
| `engine/audio.py` | Deterministic SFX, mix, gain/ducking, WAV. | Credentials and answer rules. |
| `engine/encode.py` | FFmpeg discovery, raw pipe, mux, loudness/constraint inspection. | Content semantics. |
| `scenes/__init__.py` | Registry and renderer protocol. | Plugin implementation and CLI. |
| `scenes/title.py`, `question.py`, `step.py`, `answer.py`, `tip.py`, `outro.py` | Generic scene layout/animation; `build_scene(model, context) -> Scene`. | LLM/network and bot-specific branding. |
| `plugins/__init__.py` and individual plugins | Registered parameterized visuals with safe fallback. | Timeline ownership, TTS, parsing. |
| `voice/` | Provider protocol, chain, cache keys, normalization. | Geometry and answer rules. |
| `llm/` and `prompts/` | Strict JSON generation/adapters/file prompts. | Rendering and secret storage. |
| `verify/` | Answer normalization, option consistency, safe arithmetic, optional second pass. | Drawing, TTS, FFmpeg. |

Themes, fonts, examples, and prompt templates are package data. No core module reads a current directory or system font path.

## 4. JSON contract

### `today.json` — authoritative source

```json
{
  "schema_version": 1,
  "day": 10,
  "topic": "Speed, Time & Distance",
  "difficulty": "Easy",
  "time_sec": 50,
  "question": "A train 150 m long crosses a platform 250 m long in 20 seconds. What is the speed in km/h?",
  "options": [{"id":"A","display":"72 km/h"}, {"id":"B","display":"90 km/h"}, {"id":"C","display":"108 km/h"}, {"id":"D","display":"120 km/h"}],
  "correct_option": "A",
  "final_answer": {"display":"72 km/h", "normalized":"72 km/h", "speech":"72 kilometres per hour"},
  "solution": "Distance = 150 + 250 = 400 m. Speed = 400/20 = 20 m/s. 20 × 18/5 = 72 km/h.",
  "source": {"label":"Faculty-verified daily question", "url":"https://example.invalid/record/10", "verified":true}
}
```

The CLI accepts the current legacy string array for options and normalizes it. Optional `source` is emitted/displayed only when `verified` is exactly true with a non-empty label. `difficulty` is `Easy|Medium|Hard`; `time_sec` is a requested 30--75 second target, not permission to sacrifice readability.

### `steps.json` — render-ready solution

```json
{
  "schema_version": 1,
  "input_digest": "sha256:...",
  "steps": [{
    "label":{"display":"Step 1: Total distance","speech":"First, total distance."},
    "lines":[{"display":"150 + 250"}, {"display":"= 400 m", "emphasis":"400 m"}],
    "speech":"Train and platform lengths add together. One hundred fifty plus two hundred fifty is four hundred metres.",
    "visual":{"name":"train_crossing","data":{"train_m":150,"platform_m":250,"seconds":20}}
  }],
  "tip":{"display":"m/s to km/h: multiply by 18/5", "speech":"To convert metres per second to kilometres per hour, multiply by eighteen over five."},
  "answer":{"display":"72 km/h", "speech":"The answer is seventy two kilometres per hour.", "correct_option":"A"},
  "outro":{"display":"Try tomorrow's question", "speech":"See you for tomorrow's question."}
}
```

Display fields are screen text; speech fields are pronounceable narration. A step has 1--4 display lines; overlong content splits into more scenes before rendering. `visual` is optional; an unknown name logs a warning and falls back to the generic step.

### `solution.meta.json`

```json
{
  "schema_version":1, "status":"ok", "output_path":"solution.mp4", "duration_s":48.2, "size_bytes":10428320,
  "video":{"width":720,"height":1280,"fps":30,"codec":"h264","pix_fmt":"yuv420p","audio_codec":"aac"},
  "answer_verified":true, "verification":{"checks":["answer_match","option_match","arithmetic"],"reasons":[]},
  "voice":{"requested":true,"provider":"edge","mode":"telugu_mixed_latin","fallback_used":false},
  "input_digest":"sha256:...", "theme":"default", "seed":10, "warnings":[], "version":"0.1.0"
}
```

Gate failures write `status:"blocked"`, `answer_verified:false`, reasons, and no MP4 path.

## 5. Scene catalog

| Scene | Layout and behavior | Duration |
| --- | --- | --- |
| Title | Day/topic chip, up-to-three-line title, optional context visual. | Voice + 0.5 s; else 2.5--4 s. |
| Question | Constrained question box; four option cards stagger in; no answer reveal. | Voice + 0.75 s; else 5--9 s. |
| Step | Indicator, 1--4 formula lines, current line emphasized, prior lines dimmed; bounded optional visual. | Voice + pads; else 1.1 s/line + reading time, 3--9 s. |
| Answer | Large answer card, correct option, check draw-on, restrained confetti. | Voice + 1 s; else 3.5--5 s. |
| Tip | One shortcut/common-mistake card, at most 3 lines. | Voice + 0.5 s; else 2.5--4 s. |
| Outro | Input-driven CTA/branding only. | Voice + 0.5 s; else 2--3 s. |

Transitions use the theme profile (default 0.35 s crossfade/slide), and each scene includes a readable stable period. Renderers publish semantic reveal events instead of hard-coded timestamps.

## 6. Timeline and sync model

Build an immutable `RenderPlan` before drawing frames. Each clip contains start, duration, local cues, audio asset, and transition overlap. With voice, synthesize one clip per scene, trim silence, measure it, then set `duration = max(minimum, clip_duration + lead_pad + tail_pad)`. Distribute line reveals by speech-word weight over the speech window, pin the final calculation before the final phrase, and never hide a narrated line.

With `--no-voice` or total provider failure, derive duration from display/speech word count using a documented reading rate and clamp to each scene's min/max. Above 75 seconds, reduce pads and remove optional tip/outro first; never accelerate speech or shrink text below the floor. Meta records timing mode and fallbacks.

## 7. Voice strategy

Define `VoiceProvider.synthesize(request) -> VoiceClip`; chain **Chatterbox Multilingual HF Space → edge-tts → silent timeline**. Bound timeout/retry behavior, classify quota errors, and cache by normalized speech + provider + voice + language mode.

Tanglish is a listening-test decision, not an assumption. Phase 5 creates the same three samples in Telugu script, Latin Tanglish, Telugu script with Latin technical English, and Indian English; tests requested Chatterbox plus Edge Telugu/Indian-English voices; then waits for user selection. A configurable normalizer speaks symbols, fractions, units, numbers, and acronyms; TTS never receives raw display formulas.

Free HF space quotas/cold starts and Telugu code-switching quality are material risks. Voice stays optional for the MVP, with no SLA dependency.

## 8. Accuracy gate design

Before rendering or TTS:

1. Validate both schemas and canonicalize case, whitespace, commas, percent/fraction notation, and configured units.
2. Require `steps.answer` to equal `today.final_answer` after canonicalization.
3. Require `today.options[today.correct_option]` to match it; reject ambiguous duplicates.
4. Safely evaluate supported arithmetic equalities with a whitelist AST evaluator (Decimal numbers, fractions, `+ - * / **`, parentheses, percentages, configured conversions). Each evaluable equality must hold within explicit tolerance. Unsupported prose is reported as non-machine-checkable, never silently verified.
5. Reject unverified/invented source data.
6. An optional independent LLM second pass can add a failure reason but cannot convert a failed deterministic check to pass.

Failure writes blocked meta, exits 2, keeps diagnostics, and creates no video. First release should block a non-evaluable final derivation unless an explicit, auditable faculty-review override is approved.

## 9. Performance and size budget

Budget a 60-second no-voice render at **<=170 seconds**: 90--140 seconds frame rendering and 20--45 seconds encode/validation. Prove it in Actions. Stream frames/audio to keep peak renderer memory under 650 MB; cache only bounded static assets.

For 75 seconds under 16 MB, keep total media near 1.55--1.65 Mb/s. Start H.264 around 1.38 Mb/s video plus AAC mono 64 kb/s (96 kb/s only when budget allows). If oversized, calculate a lower video bitrate from duration and actual audio bytes, re-encode once, then exit 5 if still oversized. Always validate faststart, yuv420p, dimensions, frame rate, codec, audio, and size.

## 10. Test strategy

- Unit tests: easing, timeline overlap, answer normalization, safe arithmetic, schema errors, provider failure classes, wrap/fit, bitrate calculation.
- Property/fuzz tests: long questions/options, 1--4 formula lines, Unicode/Telugu, plugin fallback. Require in-bounds boxes and font floor or a split/warning.
- Deterministic golden examples with perceptual selected-frame comparisons, plus all-black/all-transparent/flicker sanity checks.
- Encoder integration tests for short fixtures, bad codecs, missing audio, and oversize repair/failure.
- Human visual gate: 6--12-frame contact sheet per example, 1x phone-size review, and three written critiques during motion work. Humans approve “better than reference”; tests stop regressions.

## 11. GitHub Actions design

Begin with `workflow_dispatch` inputs for example/input, theme, seed, and voice on/off. Ubuntu workflow: checkout; set up Python with pip cache; install FFmpeg; install package/dev extras; unit tests; validate/dry-run; render one no-voice example; ffprobe validation; upload MP4/meta/contact sheet; write install/render/encode/size metrics to job summary. Add PR smoke only after dispatch is stable.

Cache pip wheels and only an approved content-hash voice cache; never credentials or generated media as dependencies. Fonts are bundled package/repository assets. Secrets use only `secrets.*` environment variables and provider errors are redacted. Expected failures are: setup/font/FFmpeg, gate (2), LLM (3), renderer/encoder (4), and output constraints (5). Planned voice failure still produces an artifact with warning.

## 12. Risk register

| Risk | Likelihood | Impact | Mitigation |
| --- | --- | --- | --- |
| Wrong LLM solution | Medium | Critical | Deterministic gate, option checks, arithmetic tests, no-video default. |
| Tanglish is unnatural | High | High | Listening spike, chain, no-voice fallback. |
| 2x Pillow misses Actions budget | Medium | High | Static caching, selective 2x, benchmark per phase. |
| MP4 exceeds 16 MB | Medium | High | Bitrate budget, inspect, one retry. |
| Phone text overflow | High | High | Measured layout, split policy, fuzz/contact-sheet tests. |
| Plugin data does not fit | Medium | Medium | Typed data and generic fallback. |
| Free provider outage/quota | High | Medium | Cache, bounded retry, fallback, silent output. |
| Non-deterministic output | Medium | Medium | Seed RNG, pin dependencies, no clock state. |
| Missing fonts/assets | Medium | High | Package data, explicit resolver, clean-clone Action. |
| Bot posts invalid/duplicate media | Medium | Critical | Keep outside renderer; meta/size gate and bot idempotency. |

## 13. Phased roadmap

| Phase | Deliverables | Acceptance test | Effort |
| --- | --- | --- | --- |
| 1. Engine | Canvas/text/easing/timeline/audio/encode, asset loader, hello render. | 10-s valid MP4, tests, contact sheet, clean clone. | 3--4 days |
| 2. Schema + scenes | Contracts, generic catalog, registry, examples, layout guardrails. | Examples render unchanged; fuzz layout passes. | 3--4 days |
| 3. Motion polish | Motion language, formula motion, background/progress, two plugins, visual QA. | Contact sheets beat reference; budget met. | 4--6 days |
| 4. Steps + gate | LLM adapters/prompts, verifier, checked dataset, blocked-meta behavior. | Wrong output never creates MP4; real examples verify. | 4--5 days |
| 5. Voice | Listening test, chosen provider, normalization/cache, sync/mix. | Approved samples; fallback and sync table pass. | 3--5 days after choice |
| 6. Package + Actions | Stable API/CLI, output validator, docs, dispatch artifacts. | Clean install and green dispatch within 5-minute job target. | 3--4 days |
| 7. Bot integration | Pinned package, evening render/send, text fallback, idempotency. | Private test success and all failure fallbacks. | 2--3 days in bot repo |

MVP order remains 1 → 2 → 4 → 6 → 7 with no voice. Add motion then voice after the safe baseline. Estimates exclude reviews, accounts, and phone-feedback iteration.

## 14. Open questions for approval

1. **Must decide:** Ship v0.1 no-voice while listening tests are pending? **Default:** yes.
2. **Must decide:** Permit a faculty-reviewed override for non-machine-evaluable solutions? **Default:** no override in v0.1; block them.
3. **Must decide:** Who verifies `today.json` before the bot runs? **Default:** existing bot/faculty workflow, upstream of renderer.
4. Should verified `source` appear on video, only in meta, or both? **Default:** meta only unless requested.
5. Is 60 seconds normal and 75 seconds absolute? **Default:** yes.
6. Is bundled Poppins with its license acceptable? **Default:** yes.
7. Approve Pillow-first/selective-2x rendering? **Default:** yes.
8. Do you need a logo/CTA per input or only theme data? **Default:** theme/input data, never code.
9. For listening tests, is natural Telugu, correct maths/English terms, or voice gender most important? **Default:** maths/English intelligibility.
10. May voice-cache artifacts persist between Actions runs? **Default:** no until retention is approved.
11. Which LLM account should Phase 4 use (Groq, Gemini, both)? **Default:** support both and choose via environment configuration.
12. Which two plugins ship first? **Default:** `bar_chart` and `train_crossing`.

## Decisions required before Phase 1

Approve the Pillow-first/selective-supersampling architecture; confirm the no-voice MVP; choose the policy for non-machine-verifiable answers; confirm 75 seconds as the hard cap; and confirm Poppins can ship with its license. Voice provider and script mode are intentionally deferred to the Phase 5 listening test.
