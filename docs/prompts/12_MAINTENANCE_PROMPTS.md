# 12: MAINTENANCE PROMPTS (use later, one at a time)

Always start with: "Read AGENTS.md, PLAN.md, DECISIONS.md. Show a plan, wait for go."

## A. Add a new scene type
"Add scene type `<name>`. Purpose: <when it is used>. Input fields: <list>. Layout/animation: <describe>.
Register it, add schema validation, a layout-overflow test, an example JSON, and a contact sheet. No changes to existing scenes."

## B. Add a new visual plugin
"Add plugin `<name>` for <topic> (e.g. pie_chart, venn, clock, calendar). Parameters come from the step's `visual` object.
It must degrade gracefully if missing. Provide: schema, renderer, 2 examples, tests, contact sheet, render-time impact."

## C. Add a new theme
"Create theme `<name>` (palette, fonts, motion tuning, footer). Only theme JSON + font files. Show the 4 examples in both themes side by side.
Prove no code changes were needed."

## D. Add a new output format
"Add 16:9 (1920x1080) output for YouTube. Layouts must adapt from theme/safe-area data. Keep 9:16 untouched.
Update the output validator and examples."

## E. Debug a failed GitHub Actions run
"Here is the failing log: <paste, remove secrets>. Find the root cause, explain it in plain language, propose the smallest fix,
add a regression test or a workflow guard, and tell me how to verify it."

## F. Quality upgrade pass
"Run the reviewer checklist (file 10) on the 4 examples, then fix ONLY the MAJOR visual issues. Show before/after contact sheets."

## G. New consumer (another bot / Shorts)
"Write a 20-line example showing how a different bot calls render_from_today via the Python API and via the CLI.
Update README. Do not change core behavior."

## H. Optional MCP / HTTP wrapper (only after 2+ real consumers exist)
"Create a thin wrapper that exposes `render_from_today` as an MCP tool (and/or FastAPI endpoint) with auth, size limits and timeouts.
The core library must not import the wrapper. Include tests and a security note about running code from untrusted input."
