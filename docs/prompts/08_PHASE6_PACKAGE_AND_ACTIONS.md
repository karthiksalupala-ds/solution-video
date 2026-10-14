# 08: PHASE 6: Package, API, CLI polish, GitHub Actions

---
Read AGENTS.md, PLAN.md, DECISIONS.md. Show a plan; wait for "go".

## Goal
Any future bot can use the generator three ways: CLI, `pip install git+https://github.com/<me>/solution-video@vX.Y`,
or later an HTTP/MCP wrapper. Make the core stable and the GitHub Actions run reliable.

## Build
1. Public Python API: `from solution_video import render, render_from_today` returning a typed `Meta`
   (path, duration_s, size_bytes, answer_verified, voice_provider, warnings, version).
2. CLI commands: `render`, `steps`, `render-from-today`, `validate`, `voice-test`, `--dry-run` (validate input + print the plan: scenes, duration estimate, no rendering),
   `--no-voice`, `--theme`, `--seed`, `--verbose`. Documented exit codes (0 ok, 2 gate failed, 3 LLM failed, 4 render failed, 5 output constraints failed).
3. **Output validator** run at the end: ffprobe checks codec h264/aac, yuv420p, 720x1280, 30 fps, size <= 16 MB, has audio when voice expected.
   If > 16 MB: auto re-encode with a lower bitrate; if still too big, fail with code 5.
4. Versioning: semantic version in pyproject, git tag `v0.1.0`, CHANGELOG.md, `solution-video --version`.
5. `.github/workflows/render.yml`:
   - Triggers: `workflow_dispatch` (inputs: example name/JSON path, voice on/off) and a PR smoke test.
   - Steps: checkout, setup-python with pip cache, install ffmpeg, pip install, run tests, render examples, upload mp4 as artifact.
   - Secrets only via `secrets.*` (HF_TOKEN, LLM keys). No secrets echoed in logs.
   - Timing report in the job summary (install time, render time, size).
6. README: install, quick start, JSON contract, themes, plugins, voice setup, troubleshooting, how another bot calls it.
7. License file and a CONTRIBUTING-style short guide on adding a scene/plugin/theme.

## Definition of Done
- [ ] Clean clone -> `pip install .` -> `solution-video render --input examples/di_average.json --out x.mp4 --no-voice` works.
- [ ] Actions run (workflow_dispatch) is green; artifact mp4 plays; total job time reported; within 5 minutes.
- [ ] `pip install git+...@v0.1.0` works from a separate empty folder (prove with a smoke script).
- [ ] Exit codes tested. Output validator tested with a deliberately oversized/bad file.
- [ ] README lets a stranger run it in 5 minutes.
---
