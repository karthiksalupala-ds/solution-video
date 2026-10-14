# 09: PHASE 7: Integrate into the WhatsApp bot repo (6 PM video, safe fallback)

Run this in the BOT repo (Green API + GitHub Actions cron). The generator stays in its own repo.

---
Read the bot repo structure first. Show a plan with the exact files and diffs you intend; wait for "go".

## Goal
At 6 PM the existing evening job renders the solution video via the generator and sends it to the group with Green API.
If anything fails, the current text solution is sent exactly as today. The solution must never be skipped.

## Build
1. `evening.yml`: cron at 5:50 PM IST (convert to UTC correctly), plus `workflow_dispatch`.
   Steps: checkout bot, checkout generator repo at a PINNED tag (or `pip install git+...@vX.Y`), setup python with cache,
   install ffmpeg, render step with `continue-on-error: true` producing `solution.mp4` from `today.json`
   (`solution-video render-from-today --input today.json --out solution.mp4 --seed <day>`), then the send step.
   Generator keys come from this repo's Secrets.
2. `send_video(path, caption)` using Green API `sendFileByUpload` (multipart: chatId, file, fileName, caption).
   Use the media host/URL shown in my Green API console for my instance. Check the official Green API docs for limits:
   video mp4, H.264 + AAC, up to 16 MB. Group chatId ends with `@g.us`.
3. Decision logic in `main.py --evening`:
   - If `solution.mp4` exists, size <= 16 MB, and meta says `answer_verified:true` -> send video with caption
     (answer + one-line hint, no streak claims, no invented sources).
   - Else -> send the existing text solution unchanged.
   - If the video upload API call fails -> send text solution.
4. **Idempotency**: record `solution_sent` state so a re-run never posts twice; keep behavior consistent with the morning job's state mechanism.
5. `--dry-run`: print which path would be taken (video or text), file size, caption; send nothing.
6. Keep the change minimal: no rendering code in the bot repo.
7. Logging: clear reason when falling back (gate failed / render failed / too large / API error).

## Test plan (do in order)
1. Dry-run locally.
2. Private TEST group: send a real video (different chatId via env), confirm it plays on phone, caption correct.
3. Simulate failures: delete solution.mp4, corrupt it, set answer_verified false -> text fallback each time.
4. Trigger `workflow_dispatch` against the test group, then enable cron for the real group.

## Definition of Done
- [ ] All four failure simulations produce the text solution.
- [ ] A successful run posts exactly one video message.
- [ ] No secrets in logs; generator version pinned; rollback = one config flag or revert.
- [ ] Day N and answer in the video match today.json (spot check by me).
---
