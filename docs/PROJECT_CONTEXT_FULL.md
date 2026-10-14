# 01: PROJECT CONTEXT (save as AGENTS.md / CLAUDE.md in the repo root)

## What we are building
`solution-video`: a reusable, JSON-driven generator that turns an aptitude question + solution
into a short, polished, vertical (9:16) explainer video with a Tanglish (Telugu + English) voice-over.
Input: JSON. Output: `solution.mp4` + `solution.meta.json`.

First consumer: a college WhatsApp group bot (about 400 students, principal and faculty are members).
Every day 8 AM: question poll. Every day 6 PM: solution. We replace the text solution with this video.
Later consumers: YouTube Shorts / Instagram Reels, other bots, other topics. So NOTHING topic-specific
or bot-specific may be hard-coded in the core.

## Quality bar (non-negotiable)
- Must look clearly BETTER than `reference/quality_bar_day10.mp4` (a hard-coded prototype).
- Motion: easing on everything, staggered reveals, smooth transitions, no abrupt pops, no static slides.
- Readable on a phone: body text >= 36 px at 720 px width, safe margins 40 px, high contrast, max 4 lines per screen.
- Pacing: 30-75 s total, one idea per scene, steps revealed in sync with the narration.
- Sound: voice clear and loudness-normalized; SFX subtle (never louder than the voice).
- Looks professional enough that a principal would not cringe.

## Hard rules
1. Content never lives in code. Day number, topic, question, steps, answer, branding text, colors,
   fonts, timings: all from input JSON or theme files.
2. Accuracy gate: if the video's final answer != input `final_answer` (or correct option mismatches),
   do NOT produce a video. Exit with code 2 and write meta `answer_verified:false`. A wrong video in front of
   faculty is worse than no video.
3. Never invent facts. Never add a company/source name unless the input provides a verified `source`.
4. `display` text (shown on screen) and `speech` text (spoken) are separate fields. TTS must never read raw symbols.
5. Output constraints: mp4, H.264 video + AAC audio, 720x1280, 30 fps, <= 16 MB (WhatsApp/Green API limit), yuv420p, faststart.
6. No secrets in code or repo. Keys only via env vars. Public repo assumed.
7. Deterministic: same input + same theme = same frames (seed any randomness).
8. Runs on a free GitHub Actions Ubuntu runner (CPU only, no GPU, 2-4 vCPU, internet available).
   Target total render <= 3 minutes for a 60 s video. Fonts live IN the repo (runner has none).
9. Graceful degradation: voice fails -> fallback chain -> `--no-voice` still produces a valid video.
10. Small functions, type hints, docstrings, tests. No giant files. No dead code.

## Architecture (3 layers)
1. `engine/`: generic primitives: canvas (supersampled), text layout and wrap, shapes, easing, color,
   audio synth and mixing, FFmpeg encode, timeline.
2. `scenes/`: generic scene types driven by JSON: title, question, step, answer, tip, outro (+ optional `visual` plugins).
3. Content JSON + `themes/*.json`: everything that changes day to day.

Optional topic `visual` plugins (e.g. `bar_chart`, `train_crossing`) live in `plugins/`, registered by name.
Missing plugin field -> generic scene still works.

## Repo layout (target)
```
solution-video/
  AGENTS.md  PLAN.md  DECISIONS.md  README.md  pyproject.toml
  src/solution_video/
    cli.py  api.py  schema.py  pipeline.py
    engine/   scenes/   plugins/   voice/   llm/   verify/
  themes/default.json
  fonts/            (Poppins etc, committed)
  examples/         (input JSONs)
  tests/
  .github/workflows/render.yml
  reference/        (hard-coded prototypes: read for techniques, do NOT copy the structure)
```

## Glossary
- today.json (bot format): topic, question, options[4], correct_option, final_answer, solution (text), day.
- steps JSON: LLM-converted structured solution: [{label, lines[], speech}] + answer.
- Tanglish: Telugu + English mixed, written in Latin script by students; for TTS we decide script per the voice test.

## Working agreement for the AI coder
- Read this file, PLAN.md and DECISIONS.md before every task.
- Show a short plan and the file list first. Wait for my "go". Then implement in small steps.
- After coding: run tests, render examples, show me frames/contact sheet, list what is NOT done.
- If something is ambiguous, ask. Do not guess silently. Record decisions in DECISIONS.md.
