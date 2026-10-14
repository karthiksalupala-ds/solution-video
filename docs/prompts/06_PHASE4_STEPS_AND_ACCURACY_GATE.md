# 06: PHASE 4: LLM solution->steps + accuracy gate

---
Read AGENTS.md, PLAN.md, DECISIONS.md. Show a plan; wait for "go".

## Goal
Take the bot's `today.json` (question, options, correct_option, final_answer, solution text) and produce the validated
steps JSON automatically. A wrong or unverifiable video must never be produced.

## Build
1. `llm/` provider interface (`generate_json(prompt, schema) -> dict`) with adapters for Groq and Gemini free tiers
   (keys from env), retries with backoff, timeouts, strict JSON parsing (strip code fences), schema validation, max 2 repair retries.
2. Prompt template stored as a FILE (`prompts/solution_to_steps.md`), not inline strings. It must instruct the LLM to:
   - use ONLY the given question/options/solution; never introduce new facts; never name a company or source;
   - output 2-5 steps; each step: `label`, `lines` (short display lines with real numbers/symbols), `speech` (natural spoken Tanglish
     sentence, no raw symbols), optional `emphasis`; plus `tip` (optional shortcut) and `answer`;
   - keep every display line <= the layout limits from the schema.
3. **Accuracy gate** (`verify/`), all must pass or exit code 2:
   a. `answer` == input `final_answer` (normalized: units, commas, fractions, %).
   b. `options[correct_option]` is consistent with `final_answer`.
   c. Arithmetic lines are evaluated with a SAFE evaluator (ast-based or sympy, no eval): every `a op b = c` line must be numerically true.
   d. Optional second LLM pass: "does this solution reach the stated answer? reply JSON" (cheap sanity check).
   e. On failure: write meta `{answer_verified:false, reasons:[...]}`, no mp4, exit code 2, clear log.
4. `solution-video steps --input today.json --out steps.json` and `solution-video render-from-today --input today.json --out solution.mp4`.
5. Tests: a dataset of 10 questions (include tricky ones: percentages, fractions, units) + tests with deliberately WRONG LLM outputs
   (mock the LLM) proving the gate blocks them.

## Definition of Done
- [ ] Mock-LLM tests prove: wrong answer, wrong arithmetic line, missing field, invented source -> all blocked.
- [ ] Real LLM run (my key via env) on the 3 sample inputs produces verified steps.
- [ ] No API keys in repo/logs. Prompt is a file. Provider swappable via config.
- [ ] Exit codes documented (0 ok, 2 gate failed, 3 LLM failed, 4 render failed).
- [ ] DECISIONS.md updated.
---
