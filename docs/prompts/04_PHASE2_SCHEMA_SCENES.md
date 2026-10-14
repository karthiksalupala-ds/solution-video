# 04: PHASE 2: JSON schema + generic scene types

---
Read AGENTS.md, PLAN.md, DECISIONS.md. Show a task plan + file list; wait for "go".

## Goal
Make the generator content-driven: one steps JSON in -> a complete, readable (not yet fancy) solution video out.

## Build
1. `schema.py`: pydantic models for: `QuestionInput` (today.json format), `SolutionSpec` (steps JSON), `Meta` (output).
   Fields: day, topic, question, options[4], correct_option, final_answer, difficulty?, time_sec?, source? (verified only),
   scenes/steps: [{label, lines[] (display), speech (spoken), emphasis?, visual?}], tip?, answer, cta?.
   Validation: options length 4, correct_option in A-D and consistent with final_answer, line length limits, helpful error messages.
2. Scene types (generic): `title`, `question` (auto-wrap, options reveal), `step` (label + 1-4 lines revealed one by one),
   `answer` (big answer + correct option highlight), `tip` (optional), `outro` (CTA from data).
3. Layout rules enforced in code: auto-fit text, max 4 lines, min font 36 px, safe margins from theme, never overflow
   (if content too long: shrink within limits, else split across two scenes and log a warning).
4. Duration model WITHOUT voice: derive scene duration from reading time (characters/word count) with min/max, plus a global cap of 75 s.
5. Scene registry (`scenes/__init__`) keyed by type name; adding a scene = new file + register.
6. `pipeline.render(spec, theme, out, voice=None)` returning Meta (path, duration, size, answer_verified placeholder).
7. Three example inputs in `examples/` (see file 11). Each must render with ZERO code changes between them.

## Definition of Done
- [ ] All 3 examples render to valid mp4 (<16 MB) via the CLI.
- [ ] Changing only JSON changes the video (prove: modify topic/Day/colors, no code edits).
- [ ] Layout tests: fuzz long/short text, 1-4 lines, 4 long options; assert no overflow and min font respected.
- [ ] grep shows no hard-coded topic/day/branding strings in src/.
- [ ] Contact sheets (each scene type) shown to me.
- [ ] DECISIONS.md updated; known gaps listed.
---
