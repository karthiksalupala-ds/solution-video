# 07: PHASE 5: Voice (Tanglish) + audio-driven timing

---
Read AGENTS.md, PLAN.md, DECISIONS.md. Show a plan; wait for "go".

## Part A: LISTENING TEST FIRST (do not build the full pipeline before I choose)
Create `scripts/voice_test.py` that generates short audio samples (same 3 sentences) so I can listen and pick:
- Variant 1: pure Telugu script sentences.
- Variant 2: Latin-script Tanglish (e.g. "150 plus 250 ante 400 meters").
- Variant 3: Telugu script with English words kept in Latin (e.g. "ఇప్పుడు total distance 400 meters").
- Variant 4: simple Indian-English.
Providers to test: (a) my Chatterbox Multilingual TTS HF Space via gradio_client (token + space id from env),
(b) edge-tts Telugu voices (te-IN-ShrutiNeural, te-IN-MohanNeural) and en-IN voices.
Save to `examples/voice_tests/` with a table of file -> provider -> variant. STOP and let me listen. I will pick.

## Part B: Build after my decision
1. `voice/` provider interface: `synthesize(text, lang_mode) -> wav`, chain: Chatterbox Space -> edge-tts -> none.
   Timeouts, retries, quota-aware errors (ZeroGPU quota exceeded = move to fallback, do not crash).
2. **Speech normalization**: convert symbols/numbers to speakable text per language mode ("x" -> "multiplied by", "/" -> "divided by",
   "=" -> "is", "%" -> "percent", "km/h" -> "kilometres per hour", thousands/decimals), configurable dictionary file.
3. One TTS call per step (or per sentence batch), cached by hash of (text, voice, mode) to save quota.
4. **Audio-driven timing**: measure each clip with ffprobe; scene duration = clip length + configurable padding; animation
   events (line reveals) distributed across the clip length by word count/timestamps. Trim silence, loudness-normalize (ffmpeg loudnorm),
   duck SFX under voice, final mix to AAC.
5. `--no-voice` and automatic fallback keep working (valid video always).
6. Subtitles: optional burned-in captions (from `display`/`speech` text) as a theme option.

## Definition of Done
- [ ] I listened to the voice tests and the decision is in DECISIONS.md.
- [ ] Full video with voice for all 3 samples; narration and animation visibly in sync (show frame/time table).
- [ ] Fallback chain tested by simulating Chatterbox failure and edge-tts failure.
- [ ] Voice cache works (second run makes no TTS calls).
- [ ] Loudness consistent across the 3 videos; SFX never covers the voice.
- [ ] No keys in repo; quota behavior documented.
---
