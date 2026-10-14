# 11: SAMPLE INPUTS (maths verified)

Four ready-made inputs live in `examples/` (bot `today.json` format + an `expected_steps` block that the LLM step
should roughly reproduce; the generator's own LLM output is validated, not copied):

| File | Topic | Answer | Purpose |
|------|-------|--------|---------|
| examples/di_average.json | Data Interpretation | 165 (A) | tests bar_chart visual |
| examples/percent_increase.json | Percentages | 25% (B) | plain arithmetic steps |
| examples/time_work.json | Time and Work | 8 days (B) | fractions, 3 steps |
| examples/speed_train.json | Speed, Time & Distance | 72 km/h (A) | tests train_crossing visual + unit conversion |

Use them for: every phase's Definition of Done, the reviewer prompt, and regression tests.
The "same code, different JSON" proof in phase 2: all four must render without any code change.

## Notes
- Speech lines are Tanglish in Latin script only as EXAMPLES. The final speech script is decided after the voice listening test (phase 5).
- `source` is intentionally absent: the generator must not claim any company source unless a verified `source` field is provided.
- Add your own real questions from the bot's `today.json`/fallback bank as more test cases; keep 3 intentionally WRONG variants
  (answer mismatch, wrong arithmetic line, wrong option letter) in `tests/bad_inputs/` for the accuracy gate.
