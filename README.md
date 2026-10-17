# solution-video

Turn a verified aptitude-question JSON file into a vertical MP4 plus adjacent metadata. The package supports the CLI and a typed Python API; an HTTP/MCP wrapper can be added by consumers later.

> **Voice status:** rendering can synthesize English narration using the configured provider chain, align scene duration to each clip, and cache audio locally. `--no-voice` always skips provider access and still produces a valid SFX-backed video.

## Install

Python 3.10+ and FFmpeg (including `ffprobe`) are required.

```bash
python -m pip install .
solution-video --version
```

For development:

```bash
python -m pip install ".[dev]"
pytest -q
```

Install a tagged release from GitHub:

```bash
python -m pip install "git+https://github.com/<owner>/solution-video.git@v0.2.0"
```

## Quick start

Render a checked-in example without voice:

```bash
solution-video render --input examples/di_average.json --out out/solution.mp4 --no-voice
```

The command writes `out/solution.mp4` and `out/solution.meta.json`. Fixture files may contain `expected_steps`; production input can instead contain a canonical `question_input` plus generated `steps`, or use `render-from-today` to request verified steps from Groq/Gemini.

```bash
solution-video validate --input examples/di_average.json
solution-video render --input examples/di_average.json --out out/solution.mp4 --dry-run --seed 12
solution-video steps --input examples/speed_train.json --out out/steps.json --provider groq
solution-video render-from-today --input today.json --out out/today.mp4 --provider groq --no-voice
```

`render-from-today` reads `GROQ_API_KEY` or `GEMINI_API_KEY` from the process environment. For local development, an ignored `.env` file is also read by the CLI. Never commit credentials. Set `GROQ_MODEL` to override the Groq model (`openai/gpt-oss-20b` is the default), and `GROQ_JSON_MODE=0` to disable JSON mode initially (`1` enables it unless Groq has already rejected it in this process). If Groq rejects JSON mode with `json_validate_failed`, the adapter remembers that for the process and sends subsequent calls without `response_format`; its strict JSON parser and schema/accuracy repair loop still apply, within the shared three-request limit. The adapter requests up to 8,192 completion tokens and treats a `finish_reason: length` response as truncated JSON eligible for repair. Arithmetic/grounding/filler gate failures receive one repair attempt with the exact gate reasons; gate rules are unchanged. Generated calculations should use exact fractions and integers, never rounded decimals unless decimals appear in the question. Set `SPEECH_LANGUAGE_MODE` to `english`, `tanglish_latin`, `telugu_script`, or `mixed` to guide all generated step, tip, and answer narration; `--speech-language-mode` can override it on `steps` and `render-from-today`. The selected mode is part of the generated-step cache key.

## Python API

```python
from solution_video import Meta, render, render_from_today

result: Meta = render(
    "examples/di_average.json",
    "out/solution.mp4",
    seed=12,
)
print(result.path, result.duration_s, result.answer_verified, result.voice_provider)

# For a raw question file, this generates steps using the selected LLM first.
result = render_from_today(
    "today.json",
    "out/today.mp4",
    provider="groq",
)
```

Both functions return `solution_video.Meta`, with `path`, `duration_s`, `size_bytes`, answer verification, and non-secret voice provider/model/character/credit details. Gate failures and media/output failures raise exceptions; the CLI maps them to documented exit codes.

## Input JSON

Question fields are `day`, `topic`, `question`, four distinct `options`, `correct_option`, and `final_answer`; `solution`, `difficulty`, `time_sec`, and a verified `source` are optional. A render-ready solution adds `steps` (each with `label`, calculation `lines`, and `speech`) plus an `answer` with `display` and `speech`. See [examples/](examples) and the full model contracts in [schema.py](src/solution_video/schema.py).

The accuracy gate checks the selected option and answer, evaluates arithmetic lines, and blocks a render if the final evaluated result differs from `final_answer`.

## Themes and plugins

Themes are JSON files in [themes/](themes); pass one with `--theme path/to/theme.json`. Fonts ship with the package. Scene renderers live in `src/solution_video/scenes/`; optional visual plugins live in `src/solution_video/plugins/`. A step may include `visual: {"name": ..., "data": {...}}`: `bar_chart` reads `values`, `labels`, optional `highlight_indices`, and `title`; `train_crossing` reads train/platform lengths, crossing time, units, and display labels including `distance_label`. The train visual stages the platform entry/exit, travelled-distance counter, and elapsed time from those input values. Plugin data is supplied by the input, while motion and sizing come from the theme. A missing/unknown plugin or invalid data warns and leaves the generic step visible. See [CONTRIBUTING.md](CONTRIBUTING.md) for the extension guide.

## Voice listening test

The `voice-test` command is a historical listening comparison using the approved variants in `examples/voice_tests/approved_variants.json` and narration from `examples/speed_train.json`. It previews the text and character/credit estimates without network access. The current preference for video narration is English only; Telugu and Tanglish samples are retained for reference and are not selected for the video voice:

```bash
solution-video voice-test
```

After reviewing the text, generate samples from providers whose credentials/assets are configured:

```bash
solution-video voice-test --provider all --synthesize --approve-texts
```

The private HF Space uses `HF_TTS_SPACE`, `HF_TOKEN`, and `HF_TTS_REFERENCE_AUDIO` (default `local_assets/ref_voice.wav`). If `local_assets/` is not present, create it in the repository root (next to `.env`) and put your own recording there as `ref_voice.wav`; alternatively, set `HF_TTS_REFERENCE_AUDIO` in `.env` to the recording's path. The folder is ignored by Git, so the recording is not committed. The test passes an explicit reference filepath and never uses the Space's demo default; if the file is absent, the HF part is skipped. The inspected Space endpoint does not request a transcript.

ElevenLabs uses `ELEVENLABS_API_KEY`. The command lists account premade voices first; select one with `--elevenlabs-voice-id`. Synthesis requires a separate explicit credit confirmation equal to or above the printed estimate, for example `--approve-elevenlabs-credits 1200`. The command refuses ElevenLabs generation above 1,500 estimated credits. The existing comparison tested `eleven_v3` and `eleven_multilingual_v2`; no more Telugu/Tanglish generation is planned for the current English-first narration. If Telugu is tested later, ElevenLabs documents Telugu support for `eleven_v4` (a multilingual model, not a Telugu-only model); choose a voice suited to Telugu and confirm the account supports that model before spending credits. Only premade voices are used; no voice cloning is performed. Treat free-tier samples as non-commercial.

The three Edge voices are `te-IN-ShrutiNeural`, `te-IN-MohanNeural`, and `en-IN-NeerjaNeural`. Audio and `INDEX.md` are written to `examples/voice_tests/`. Test-provider network calls are mocked.

## Voice rendering

The default provider order is `hf_space,edge_tts,none`. HF uses `HF_TTS_SPACE`, `HF_TOKEN`, and the user-owned reference recording configured by `HF_TTS_REFERENCE_AUDIO`; the recording is resolved to an absolute readable file and uploaded with `gradio_client.handle_file` based on the file component reported by `view_api()`. Optional `HF_TTS_REQUEST_LIMIT` caps Space synthesis requests per render, and `HF_TTS_REQUEST_PAUSE_S` sets a pause between requests. Edge uses `EDGE_TTS_VOICE` (default `en-IN-NeerjaNeural`) and `EDGE_TTS_RATE` (default `-8%`). Configure the chain with `VOICE_PROVIDER_ORDER`. `--voice-provider` selects a provider for one run; `--voice-provider none` disables TTS. The chosen narration language is `SPEECH_LANGUAGE_MODE` (default `english`).

ElevenLabs is opt-in with `--voice-provider elevenlabs`. Set `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID`, and optionally `ELEVENLABS_MODEL_ID` (default `eleven_multilingual_v2`). Before every synthesis request, the renderer reads the documented [subscription endpoint](https://elevenlabs.io/docs/api-reference/user/subscription/get) and requires remaining characters minus the request estimate to stay at or above `ELEVENLABS_RESERVE_CREDITS` (default `1500`). If usage cannot be checked, ElevenLabs is skipped. Set `VOICE_ELEVENLABS_FALLBACK=1` only if an ElevenLabs failure may continue to the configured providers. Audio already in the local cache makes no provider request and uses zero credits. Check the account plan's commercial-use rights before publishing; an attribution footer does not grant rights.

`--dry-run` prints the selected provider/model and estimated characters/credits without contacting TTS providers. `--sync-report` prints expected Edge TTS word-boundary times beside actual scene reveal times; other providers use proportional cue timing. Edge word timings are cached alongside audio. The default theme uses 0.45 seconds of scene padding. `solution.meta.json` records provider, model, language mode, characters, credits, duration per synthesized scene, and warnings, never credentials. The default theme enables the small `Voice: ElevenLabs` attribution on public-facing outputs using ElevenLabs audio; theme `voice.captions` optionally enables word-progressive captions. FFmpeg trims silence and normalizes each clip before mixing; SFX are ducked under speech. Scene durations are overridden by clip length plus theme padding and are constrained to 75 seconds (with at most a small pitch-preserving speech speed-up).

## Another bot calling the generator

A bot can invoke the CLI as a subprocess and use the exit status and meta JSON as the contract:

```python
import subprocess

result = subprocess.run(
    [
        "solution-video", "render",
        "--input", "today-solution.json",
        "--out", "out/solution.mp4",
        "--no-voice",
    ],
    check=False,
)
if result.returncode == 0:
    send_video("out/solution.mp4")
else:
    send_text_fallback("today-solution.json")
```

Alternatively, install the package into the bot's Python environment and call `render(...)`. Keep the generator process isolated from bot delivery credentials and use the returned `Meta` to confirm the accuracy gate passed before sending.

## Themes, output constraints, and troubleshooting

- Output is validated with `ffprobe`: H.264 video, AAC audio, `yuv420p`, 720x1280, 30 fps, positive duration, and no more than 16 MiB.
- An oversized file gets one lower-bitrate H.264/AAC encode. If it still violates the size constraint, it is rejected.
- Install FFmpeg with `ffprobe` on `PATH` if rendering or validation reports either tool missing.
- Exit codes: `0` success; `2` invalid input or accuracy-gate block; `3` LLM/provider failure; `4` rendering failure (including unavailable requested voice); `5` output media/size constraints failed.
- Use `--dry-run` to validate a render-ready JSON and inspect planned scenes and estimated duration/provider usage without rendering or making provider calls.
- Use `--verbose` to print the result metadata summary and warnings.

## GitHub Actions

Pull requests run the test suite and render all aptitude examples. `workflow_dispatch` accepts an example JSON path and a voice on/off selection, then uploads the MP4 artifact and reports install/render times and file size in the job summary. No LLM key is needed to render checked-in fixtures; provider credentials should only be added as GitHub Secrets when a workflow is intentionally configured to synthesize voice.

## License

Apache-2.0; see [LICENSE](LICENSE).
