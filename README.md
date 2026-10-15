# solution-video

Turn a verified aptitude-question JSON file into a vertical MP4 plus adjacent metadata. The package supports the CLI and a typed Python API; an HTTP/MCP wrapper can be added by consumers later.

> **v0.1.0 status:** speech synthesis is not integrated yet. MP4s contain a synthesized sound-effects track (AAC), and `--no-voice` explicitly requests that mode. A render without `--no-voice` includes a warning in its metadata; `voice-test` reports that TTS is unavailable.

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
python -m pip install "git+https://github.com/<owner>/solution-video.git@v0.1.0"
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

`render-from-today` reads `GROQ_API_KEY` or `GEMINI_API_KEY` from the process environment. For local development, an ignored `.env` file is also read by the CLI. Never commit credentials. Set `GROQ_MODEL` to override the Groq model.

## Python API

```python
from solution_video import Meta, render, render_from_today

result: Meta = render(
    "examples/di_average.json",
    "out/solution.mp4",
    no_voice=True,
    seed=12,
)
print(result.path, result.duration_s, result.answer_verified)

# For a raw question file, this generates steps using the selected LLM first.
result = render_from_today(
    "today.json",
    "out/today.mp4",
    provider="groq",
    no_voice=True,
)
```

Both functions return `solution_video.Meta`, with `path`, `duration_s`, `size_bytes`, `answer_verified`, `voice_provider`, `warnings`, and `version`. Gate failures and media/output failures raise exceptions; the CLI maps them to documented exit codes.

## Input JSON

Question fields are `day`, `topic`, `question`, four distinct `options`, `correct_option`, and `final_answer`; `solution`, `difficulty`, `time_sec`, and a verified `source` are optional. A render-ready solution adds `steps` (each with `label`, calculation `lines`, and `speech`) plus an `answer` with `display` and `speech`. See [examples/](examples) and the full model contracts in [schema.py](src/solution_video/schema.py).

The accuracy gate checks the selected option and answer, evaluates arithmetic lines, and blocks a render if the final evaluated result differs from `final_answer`.

## Themes and plugins

Themes are JSON files in [themes/](themes); pass one with `--theme path/to/theme.json`. Fonts ship with the package. Scene renderers live in `src/solution_video/scenes/`; optional visual plugins live in `src/solution_video/plugins/`. See [CONTRIBUTING.md](CONTRIBUTING.md) for the extension guide.

## Voice setup

v0.1.0 does not synthesize narration. `--no-voice` produces a valid MP4 with its sound-effects soundtrack, while `voice-test` exits with code 4 and explains that TTS is not available. Installing the optional `voice` extra alone does not enable TTS; voice support is deferred until its provider/fallback chain is integrated and tested.

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
- Use `--dry-run` to validate a render-ready JSON and inspect planned scenes and estimated duration without rendering.
- Use `--verbose` to print the result metadata summary and warnings.

## GitHub Actions

Pull requests run the test suite and render all aptitude examples. `workflow_dispatch` accepts an example JSON path and a voice on/off selection, then uploads the MP4 artifact and reports install/render times and file size in the job summary. v0.1.0 has no TTS integration; selecting voice on is rejected by `voice-test` rather than silently producing a speech-free video. No LLM key is needed to render checked-in fixtures.

## License

Apache-2.0; see [LICENSE](LICENSE).
