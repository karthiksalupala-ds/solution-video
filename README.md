# solution-video

JSON in -> polished vertical solution video out (mp4 + meta JSON). Built for a college WhatsApp aptitude bot; reusable for Shorts/Reels and other bots.

## START HERE
1. Read AGENTS.md (rules) and docs/prompts/00_README.md (how the prompt pack works).
2. Run `docs/prompts/02_PLANNING_AGENT.md` in a fresh AI-coder session (plan only). Commit PLAN.md + DECISIONS.md.
3. Then phases in order: 03, 04, 06, 08, 09 (MVP), later 05, 07, and reviewer 10 after each phase.

## Status
- [ ] Planning   - [ ] Phase 1 engine   - [ ] Phase 2 schema+scenes   - [ ] Phase 3 polish
- [ ] Phase 4 steps+gate   - [ ] Phase 5 voice   - [ ] Phase 6 package+Actions   - [ ] Phase 7 bot integration

## Dev
```
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
solution-video --version
```
Needs ffmpeg on PATH.
