# Solution Video Generator: Prompt Pack

> **Starter repo note:** `AGENTS.md` already exists in the repo root (compact version, saves credits). Skip saving file 01 as AGENTS.md; the full version is kept at `docs/PROJECT_CONTEXT_FULL.md`. Folders and stubs already exist; phase prompts should fill them, not recreate the layout.


Idhi oka developer AI coder tho project ela build chesthado, ade order lo prompts.
Oka file = oka session. Skip cheyyaku, order important.

## Order (follow exactly)

| # | File | Who | Output |
|---|------|-----|--------|
| 1 | 01_PROJECT_CONTEXT.md | You paste once, then save as `AGENTS.md` / `CLAUDE.md` in the repo | AI ki permanent memory |
| 2 | 02_PLANNING_AGENT.md | Planner (NO code) | `PLAN.md` + questions for you |
| 3 | 03_PHASE1_ENGINE.md | Coder | engine + hello-world video |
| 4 | 04_PHASE2_SCHEMA_SCENES.md | Coder | JSON schema + scene types |
| 5 | 05_PHASE3_MOTION_POLISH.md | Coder | animation quality (the "wow" phase) |
| 6 | 06_PHASE4_STEPS_AND_ACCURACY_GATE.md | Coder | LLM steps + answer verification |
| 7 | 07_PHASE5_VOICE_TANGLISH.md | Coder | voice + sync (starts with a listening test) |
| 8 | 08_PHASE6_PACKAGE_AND_ACTIONS.md | Coder | CLI, package, GitHub Actions |
| 9 | 09_PHASE7_BOT_INTEGRATION.md | Coder (in the BOT repo) | 6 PM video send + fallback |
| 10 | 10_REVIEW_QA_AGENT.md | Reviewer | run after EVERY phase |
| 11 | 11_SAMPLE_INPUTS.md | You | 3 test inputs (verified maths) |
| 12 | 12_MAINTENANCE_PROMPTS.md | Later | add scene / plugin / fix failures |

## How to run each phase (important)
1. New chat/session for every phase. Repo lo `AGENTS.md` (file 1) already undali.
2. Paste that phase file. Tell the AI: "Read AGENTS.md and PLAN.md first."
3. AI **plan chupinchali, code rayakamundu**. Nuvvu "go" cheppaka matrame code.
4. Phase aipoyaka: tests run, `Definition of Done` checklist tick.
5. Run file 10 (reviewer) in a fresh session. Issues fix chesaka commit.
6. Commit + tag (`phase-1-done`). Tarvata next phase.

## Rules for you
- Planning (file 2) skip cheyyaku. Idhi lekapote AI hard-code chesestundhi.
- Phase 3 lo **frames chusi** (contact sheet) feedback ivvu. "Ee slide kaasta better ga" ani specific ga cheppu.
- Voice (phase 5) lo modalu AI create chese **sample audio files nuvvu vini** decide chey (Telugu script / Tanglish).
- Decisions anni `DECISIONS.md` lo likhinchu (AI ki cheppu).
- `reference/` folder = nenu chesina PROTOTYPES (hard-coded). Quality bar chudadaniki, structure copy cheyyakudadu.
  `quality_bar_day10.mp4` = minimum quality. Final output dhaanikante better undali.

## Pack lo inka
- `examples/`: sample JSONs will live here (see file 11).
- Keys (Groq/Gemini, HF token, Green API) ekkadaina chat lo paste cheyyaku. Env/GitHub Secrets matrame.
