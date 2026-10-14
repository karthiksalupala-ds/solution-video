# AGENTS.md (read before every task)

## Project
`solution-video`: JSON-driven generator: aptitude question + solution -> polished 9:16 explainer mp4 with Tanglish voice-over.
Input: JSON. Output: `solution.mp4` + `solution.meta.json`. First consumer: a college WhatsApp bot (400 students, faculty included),
which sends the video at 6 PM instead of a text solution. Later: YouTube Shorts/Reels, other bots. Full context: docs/PROJECT_CONTEXT_FULL.md.

## Hard rules
1. No content in code: day, topic, question, steps, answer, branding, colors, fonts, timings come from input JSON or themes/*.json.
2. Accuracy gate: video answer must equal input `final_answer` and match `correct_option`; otherwise NO video, exit code 2,
   meta `answer_verified:false`. A wrong video in front of faculty is worse than none.
3. Never invent facts or company names. `source` only if provided and verified.
4. `display` text (on screen) and `speech` text (spoken) are separate fields.
5. Output: mp4, H.264 + AAC, yuv420p, 720x1280, 30 fps, <= 16 MB, faststart.
6. No secrets in repo or logs. Env vars only (see .env.example). Repo is public.
7. Deterministic: same input + theme + seed = same frames.
8. Must run on a free GitHub Actions Ubuntu runner (CPU only). Target render <= 3 min for 60 s. Fonts come from fonts/.
9. Graceful degradation: voice failure -> fallback chain -> `--no-voice` still yields a valid video.
10. Small functions, type hints, docstrings, tests. No dead code.

## Quality bar
Must look clearly better than reference/quality_bar_day10.mp4: easing everywhere, staggered reveals, smooth transitions,
text >= 36 px at 720 px width, safe margins, high contrast, 30-75 s, one idea per scene.
reference/*.py are HARD-CODED prototypes: borrow techniques (supersampled Pillow, easing, FFmpeg frame piping, numpy SFX), never their structure.

## Layout
engine/ (canvas, text, easing, timeline, audio, encode) | scenes/ (title, question, step, answer, tip, outro) |
plugins/ (optional visuals: bar_chart, train_crossing...) | voice/ | llm/ | verify/ | themes/ | fonts/ | examples/ | tests/

## Exit codes
0 ok | 2 accuracy gate failed | 3 LLM failed | 4 render failed | 5 output constraints failed

## Working agreement
Read AGENTS.md, PLAN.md, DECISIONS.md first. Show a short plan + file list, WAIT for "go". Then implement in small steps.
After coding: run tests, render examples, show frames, list what is NOT done. Ask when unclear. Record decisions in DECISIONS.md.
Credit-saving: do not re-read reference/ files in full each time; do not paste large files back; keep replies short.
