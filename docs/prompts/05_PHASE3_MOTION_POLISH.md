# 05: PHASE 3: Motion design + polish (the "wow" phase)

This phase decides whether the output looks like a student script or a professional explainer.
Do it with visual feedback loops: render -> contact sheet -> critique -> improve.

---
Read AGENTS.md, PLAN.md, DECISIONS.md. Study reference/quality_bar_day10.mp4 techniques and list what is weak in it
(static text blocks, uniform pacing, no visual explanation). Show a plan; wait for "go".

## Goal
Videos that explain, not just display text. Every scene has purposeful motion that supports comprehension.

## Build
1. **Motion language** in the theme: durations, easing curves, stagger delays, transition types (crossfade, slide, wipe, scale).
   One consistent system, not random effects.
2. **Step animation**: each calculation line appears left-to-right/typed, the key number highlights (color pulse), previous lines
   dim, operators animate. Final result of a step "lands" with a subtle scale + SFX.
3. **Number animations**: count-up/down, formula morphing (e.g. 660 / 4 -> 165), strike-through on cancelled terms.
4. **Question scene**: words revealed in reading rhythm, options slide in staggered, correct option highlighted in the answer scene.
5. **Background system**: soft animated gradient + subtle particles/parallax (cheap to render), consistent across scenes, theme-driven.
6. **Progress and context UI**: Day N/100 pill, topic chip, step indicator (1/3, 2/3), brand footer, all from data.
7. **Answer scene**: strong payoff (answer card, check mark draw-on, small confetti); optional "common mistake" and "shortcut tip" cards.
8. **Visual plugins** (registered by name, optional `visual` field in a step):
   - `bar_chart` / `table_highlight` for Data Interpretation (animated bars growing, values counting).
   - `number_line` or `timeline` for speed/time/work style problems.
   - `train_crossing` (port the idea from reference prototype, but parameterized: lengths, speeds from JSON).
   - A plugin must never be required; missing/unknown visual -> graceful generic scene.
9. **Sound design**: SFX synced to visual events (tick on reveal, whoosh on transition, ding on answer), low volume, ducked under voice later.
10. **Performance**: cache static layers; keep 60 s render <= the budget in PLAN.md. Report numbers.

## Process requirement (visual QA loop)
After each major piece: render, extract a contact sheet (6-12 frames across the scene), LOOK at it, write 3 concrete
critiques (alignment, contrast, spacing, hierarchy, motion), fix, re-render. Show me the final contact sheets and the critique log.

## Definition of Done
- [ ] All 3 sample inputs look clearly better than quality_bar_day10.mp4 (side-by-side contact sheets).
- [ ] At least 2 visual plugins working + fallback verified.
- [ ] Motion system documented in theme/README; no scene uses ad-hoc timings.
- [ ] No text overflow, no clipped elements, no flicker between frames (check sequential frames).
- [ ] Render time within budget; mp4 < 16 MB.
- [ ] Tests still pass; DECISIONS.md updated.
---
