# Visual Styles Architecture Plan

## Purpose and constraints

Render the same verified solution JSON through interchangeable visual style packs without changing content, accuracy verification, narration, scene timing, or the 720x1280 / 30 fps / 16 MiB delivery contract. Styles must improve perceived quality while preserving the existing floor of 36 px readable text, safe margins, deterministic output, and the 75-second maximum.

### Current implementation batch

Batch A currently registers `neon_glow`, `glassmorphism`, `glitch`, `halftone_dots`, `dithering`, `risograph_print`, `pixel_art`, and `ascii_art` alongside `classic`. Batch B adds `vaporwave_grid`, `topographic_lines`, `flow_fields`, `particle_swarm`, `metaballs`, `liquid_morph`, and `holographic_foil`. Style-specific palettes and motion rates live in the theme. Six-frame gallery previews are available for the four checked-in examples across both batches. The `bench --workers 1|2` command measures frame rendering in one process or two worker processes; multiprocessing remains a benchmark option only, not the production FFmpeg render path. The 28-file Batch B MP4 matrix passed its current ffprobe/meta gate; contrast and 60/75-second size gates remain.

Batch C adds `kinetic_typography` (Tier 1), `bauhaus_shapes` (Tier 1), `paper_cutout` (Tier 3 after local budget measurement), `clay_3d` (Tier 2), and `ray_marched_fractals` (Tier 3). The fractal style is intentionally a bounded 2D Julia-set fallback, not a 3D ray marcher. All five styles passed a 20-video no-voice MP4 matrix and have six-frame speed-train contact sheets. Voice word-boundary-fed kinetic timing is not wired; the style uses deterministic proportional word pacing. Contrast and 60/75-second size gates remain.

The integration pass adds a theme allowlist, day-stable auto selection, explicit heavy-style opt-in, flag-gated theme scene overrides, an all-style sheet/reel/index command, a tier-budget benchmark table, CRF 29 retry for oversized noisy styles, and a style-selecting Actions dispatch. Local measurements classify `neon_glow`, `paper_cutout`, and `vaporwave_grid` as Tier 3, and `risograph_print` as Tier 2. Gallery segment sizes are 2-second preview sizes and are not substitutes for full-video size validation.

This is a visual system, not twenty unrelated scene implementations. Every style must leave question, calculation, option, and answer semantics intact. Content remains data-driven; style code must not contain topic-specific copy, answers, or branding.

## 1. StylePack architecture

### Contract

Add a `StylePack` protocol eventually, selected before scene construction. A style pack owns visual treatment only and never changes the content model, verification result, scene duration, voice text, or cue positions.

```python
class StylePack(Protocol):
    name: str
    tier: Literal[1, 2, 3]

    def prepare(self, context: StyleContext) -> PreparedStyle: ...
    def background(self, frame: FrameContext) -> Image.Image: ...
    def surface(self, frame: FrameContext, layout: SceneLayout) -> Image.Image: ...
    def decorate_text(self, frame: FrameContext, text_box: TextBox) -> Image.Image | None: ...
    def overlays(self, frame: FrameContext, cues: tuple[RevealCue, ...]) -> Image.Image | None: ...
    def postprocess(self, frame: FrameContext, image: Image.Image) -> Image.Image: ...
```

`StyleContext` carries only immutable rendering inputs: theme tokens, canvas geometry, scene index/type, duration, seed, and optional per-scene style parameters. `FrameContext` adds local time, global time, deterministic frame number, active cue state, and precomputed layers. `SceneLayout` is produced by the generic scene renderer and provides bounded named regions such as header, question card, equation card, visual area, option rows, and footer.

Scenes ask the style for layers through a narrow render context:

- scene renderer computes layout, semantic reveal state, and text boxes first;
- StylePack supplies background, card/surface, decorative text treatment, FX overlays, and post-processing;
- generic scene renderer draws semantic text and verified visuals into protected content masks;
- style may draw behind text, around text, or above text only through masks; it cannot repaint or obscure protected content.

The fixed compositing order is:

1. **Background** — gradients, grids, noise fields, paper, particles, topology, or abstract form.
2. **Surface/cards** — cards, panels, frames, shadows, masks, diagram containers.
3. **Content text and verified visuals** — scene text, equation lines, options, bar chart, train crossing, captions, progress dots.
4. **FX overlays** — bounded glow, scanlines, grain, particles, foil shimmer, ink texture, glitch slices.
5. **Post** — optional palette LUT, very light dither/grain, chromatic treatment, output-safe sharpening.

Text and answer highlighting are always rendered after background/surface layers and before any overlay that could reduce contrast. A style declares `overlay_exclusion_masks=(text, answer, options)` when its FX must avoid those regions.

### Selection and overrides

Style selection is data/configuration, never a new scene type:

- `theme.style`: default style pack name for the theme.
- `theme.style_allowlist`: explicit enabled-style list; remove entries to prevent automatic or explicit selection.
- `solution-video render --style NAME`: CLI override, taking priority over `theme.style`.
- `--style auto`: rotate deterministically by `day` through the curated enabled Tier 1/2 list; Tier 3 is included only with `STYLE_ALLOW_HEAVY=1`.
- `theme.scene_styles`: optional per-scene style map; apply it only with `--allow-scene-style-overrides`.
- `--style default`: existing polished default look, preserving backward-compatible output.

Selection resolves once into a render manifest, recorded in meta as video style plus per-scene effective styles. The day-to-style mapping is versioned so the same day/seed produces the same style after a release.

### Voice, word timing, and SFX hooks

Style receives read-only cue data emitted by the existing timeline: scene enter/exit, word boundaries, option reveals, step-line reveals, result reveal, answer reveal, and beat/SFX markers. It can attach visual reactions but cannot move the semantic cue:

- word cues can drive kinetic typography emphasis, gentle foil/glow pulse, particle burst, or diagram count-up;
- step-result cue can trigger a protected accent halo or result-card expansion;
- answer cue can drive a restrained, masked payoff effect;
- SFX remains owned by the audio mixer; style can request named existing SFX at an existing cue with theme-configured gain, not synthesize arbitrary audio per frame.

With `--no-voice`, the same normalized cue timeline remains the source of animation timing. Cached narration clips and timestamps are consumed as-is; no style may make a provider call.

## 2. CPU-only rendering strategy

### Rules for 2–4 vCPU GitHub runners

- Use Pillow for final RGBA composition and NumPy for field generation, masks, LUTs, particle positions, and pixel transforms. Avoid Python loops over pixels.
- Render expensive non-text fields at half resolution (360x640) or quarter resolution when visually safe, upscale with an explicit filter, then composite beneath protected text.
- Precompute loopable layers once per scene/style: noise tiles, foil phase frames, flow vectors, particle trajectories, metaball grids, topology line maps, palettes, and glyph atlases.
- Cache static background/surface layers and text layouts. Only dynamic regions redraw each frame.
- For a costly post effect, update at 10–15 fps and hold/interpolate it across 30 fps output frames when the visual language permits it.
- Use bounded arrays (`uint8`/`float32` only where necessary); release per-scene caches when a scene ends.
- Seed every pseudo-random operation from `(video_seed, style_name, scene_index)`. Never depend on wall time, unordered dict traversal, or unseeded library RNG.

### Frame multiprocessing

The default remains single-process, ordered raw-frame piping to FFmpeg: predictable, low-memory, and easy to debug. Add chunked multiprocessing only for Tier 3 styles after the baseline profiler proves it helps:

- partition a scene into 30–90 frame chunks with overlap-free deterministic state;
- workers render independent chunks from a serialized immutable `RenderPlan` and precomputed data;
- parent process buffers a bounded number of completed chunks, reorders by frame number, and is the sole FFmpeg writer;
- cap workers at `min(2, cpu_count - 1)` on 2–4 vCPU runners; never allow frame queues to hold more than 90 full frames;
- disable multiprocessing for voice, encode, and light styles; startup and inter-process image transfer can cost more than it saves.

### Memory and time budgets for a 60-second / 1,800-frame video

| Tier | Intended styles | Render budget (2–4 vCPU) | Encode + validation | Peak renderer memory | Policy |
| --- | --- | ---: | ---: | --- |
| 1 — cheap | mostly cached/vectorized | 70–120 s | 25–45 s | <= 550 MiB | eligible for `auto` |
| 2 — medium | bounded dynamic fields | 120–165 s | 25–45 s | <= 700 MiB | opt-in and curated `auto` rotation |
| 3 — heavy | simulation-like fields | 165–210 s | 25–45 s | <= 850 MiB | explicit selection only |

The target remains under three minutes total. A Tier 3 style that exceeds 210 seconds for rendering or 850 MiB peak memory on the reference runner is not shipped as a video style; it must receive a cheaper visual approximation.

### Measurement plan

`solution-video bench --style all --example examples/speed_train.json --frames 60` prints ms/frame and a 60-second single-worker projection against the tier ceilings (120/165/210 seconds) and exits 5 if any enabled style exceeds its tier. `--workers 2` is a comparison-only measurement because process startup/transfer overhead makes it unsuitable as the budget gate. `solution-video gallery` writes the same single-worker benchmark table with 2-second preview MP4 bytes and builds the contact sheets and reel. These are local projections, not GitHub runner or peak-memory measurements; CI dispatch separately renders three no-voice `speed_train` styles and reports wall-clock timings.

## 3. Legibility rules and automated contrast check

### Non-negotiable rules

- Body/display text remains at least 36 px at 720 px width; result/answer text is larger than the working line.
- Text is confined to scene safe margins and measured layout boxes. Decorative elements cannot force a smaller font.
- Every text box has a stable surface, shadow, outline, blur-backplate, or local dim mask when its background is not reliably flat.
- Accent colors may identify results and correct answers, but never become the sole signal; retain label, border/icon, and contrast distinction.
- Motion under text is reduced during the scene's stable reading window; glitch, grain, particles, and dither are masked out or attenuated under text.
- Result line uses a semantic `result` role, not a fragile string match like `=`. It gets a larger font/card treatment and the theme's success/accent token.

### Automated check

For every sampled frame (scene start, each reveal, mid-scene, scene end), render or reuse the final text masks and calculate local contrast:

1. Dilate each text mask by 4 px to sample the immediate background/surface around glyphs.
2. Convert foreground and sampled background pixels to relative luminance.
3. Require minimum contrast ratio of 4.5:1 for normal body text, 3:1 for large text (>= 48 px), and 3:1 for non-text accent borders/icons.
4. Check at least the 10th percentile pixel contrast, not only the mean, to catch foil/glitch/particle hotspots.
5. If a check fails, apply the style-declared safety fallback in this order: strengthen local backplate, increase shadow/outline, reduce overlay alpha in mask, then use the theme's high-contrast text color. Never silently shrink text or continue with a failed visual.

The result is saved as a per-style/per-frame legibility report. Tests assert no failures for all shipped style/example combinations.

## 4. File-size control for noisy styles

Grain, halftone, dithering, glitch, and particle fields create high inter-frame entropy and can inflate H.264 output dramatically. Style packs must declare a `noise_budget` and observe these controls:

- use static or slowly looping noise tiles instead of new random full-frame noise each frame;
- apply grain at half resolution and only to background/surface masks;
- update dither/halftone phase at <= 10 fps unless the style specifically needs animation;
- prefer limited palettes and large coherent regions; do not apply full-frame animated pixel noise;
- keep post FX out of text/option/answer masks;
- start encoding from the existing duration-aware bitrate budget, validate, then allow only the existing one-pass lower-bitrate repair;
- if a noisy style's initial output exceeds 16 MiB, re-render at CRF 29 and fail explicitly if still oversized;
- style-specific fallback: reduce noise alpha/temporal update rate first, then simplify effect geometry before lowering semantic/text quality.

At 75 seconds, audio plus container reserve leaves roughly 1.4–1.5 Mb/s for video to remain under 16 MiB. Each shipped noisy style needs a 60-second and 75-second size test; it is rejected if one repair cannot reach the delivery limit without visibly damaging text.

## 5. Style tiers and recommended build order

| # | Style | Tier | Technique | Main risk | Build order |
| ---: | --- | --- | --- | ---: |
| 1 | Bauhaus shapes | 1 | cached geometric primitives, limited palette, staggered transforms | busy geometry competing with text | 1 |
| 2 | Glassmorphism | 1 | translucent blurred card backplates, gradient blobs, local blur cache | blur cost / weak contrast | 2 |
| 3 | Paper cutout | 3 | layered vector silhouettes, offset shadows, masked reveals | measured 174–212 s full render | 3 |
| 4 | Risograph print | 2 | 2–3 ink palette LUT, static registration offset, sparse grain | measured 99–158 s full render | 4 |
| 5 | Neon glow | 3 | cached half-resolution glow halos with answer-only blur | excessive render cost in full renders | 5 |
| 6 | Vaporwave grid | 3 | perspective grid, sun disc, static gradient, slow parallax | full render cost | 6 |
| 7 | Kinetic typography | 1 | cue-driven word/line transforms and result emphasis | motion interrupts reading | 7 |
| 8 | Pixel art | 1 | low-resolution authored layer, nearest upscale, palette quantization | fonts become too pixelated | 8 |
| 9 | Dithering | 1 | Bayer matrix ordered dither at half resolution | codec noise and banding | 9 |
| 10 | Holographic foil | 2 | cached normal-like color bands + masked moving highlight | gradient shimmer behind text | 10 |
| 11 | Halftone dots | 2 | NumPy dot field from luminance, half-res mask | temporal flicker / output size | 11 |
| 12 | ASCII art | 2 | glyph atlas with tiled luminance mapping; semantic text excluded | expensive glyph placement / illegibility | 12 |
| 13 | Topographic lines | 2 | thresholded value field with precomputed contour paths | dense lines reduce contrast | 13 |
| 14 | Glitch effect | 2 | deterministic band displacement, channel split, cue-only bursts | readability and frame entropy | 14 |
| 15 | Liquid morph | 2 | low-res displacement/noise field, masked blob morphs | CPU cost / cards wobble | 15 |
| 16 | Flow fields | 2 | precomputed streamline/particle paths, short looping animation | particle clutter | 16 |
| 17 | Clay 3D | 2 | 2.5D shaded rounded shapes, ambient shadow, parallax | false 3D looks cheap / blur cost | 17 |
| 18 | Particle swarm | 3 | fixed-budget vectorized particles following deterministic targets | render time and compression noise | 18 |
| 19 | Metaballs | 3 | half-res signed distance/value field, contour threshold | costly full-frame field / muddy text | 19 |
| 20 | Ray-marched fractals | 3 | **safe version:** 360x640 cached animated fractal field, 6–12 steps max, 10 fps loop, upscale beneath content | full-resolution per-frame ray marching is unrealistic on CPU | 20 |

Do not ship a true full-resolution, per-frame ray-marched fractal on GitHub CPU runners. The safe version is an abstract, precomputed low-resolution fractal loop with palette cycling and a strict compute budget. If it cannot meet Tier 3 benchmarks, it becomes a static/slowly drifting background image treatment, not a dynamic renderer.

Recommended initial release set: Bauhaus, glassmorphism, paper cutout, risograph, neon, vaporwave, kinetic type, and pixel art. They create clearly distinct looks with low risk and establish the style contract before simulation-heavy work.

## 6. Shared building blocks

Implement and test these once under `engine/style/` (or an equivalent isolated style subsystem), then compose them in packs:

- deterministic scalar/value/cellular noise fields and loopable noise tiles;
- blur utilities with region masks, half-resolution cache, and premultiplied-alpha correctness;
- palette LUTs, gradient maps, limited-palette quantization, and color-safe palette validation;
- Bayer/ordered-dither matrices and mask-aware application;
- glyph atlas with cached font/raster variants for ASCII and pixel treatments;
- vectorized fixed-budget particle system with seeded emitters, trails, and bounded buffers;
- metaball/SDF field generator at reduced resolution;
- easing, stagger, keyframe interpolation, cue-reactive envelopes, and loop phase functions;
- mask-based compositing: protected content masks, FX exclusion masks, local backplates, and alpha-safe blend modes;
- shared card silhouettes, bevel/shadow profiles, decorative frames, and progress treatments;
- image-quality utilities: luminance, contrast sampler, palette-safe color conversion, and contact-sheet annotations.

Do not make styles call scene internals directly. Styles consume named regions/masks and generic draw helpers; scenes retain semantic layout ownership.

## 7. Test and review strategy

### Automated tests

- **Seed determinism:** same input/theme/style/seed gives byte-identical pre-encode selected PNG frames or stable image hashes; style selection in `auto` is stable by day.
- **Style contract:** every registered style handles all generic scene types, rejects/normalizes invalid parameters, and falls back safely for an unknown style.
- **Legibility:** run the contrast sampler against representative frames, text masks, result lines, answer option rows, and each style's worst overlay phase.
- **Budget behavior:** unit-test cache keys, field dimensions, particle caps, and half-resolution fallback decisions.
- **No semantic regressions:** all existing accuracy, layout, timeline, narration-cue, and plugin tests remain unchanged and pass.
- **Output contract:** no-voice render smoke tests retain H.264/AAC, 720x1280, 30 fps, <=16 MiB, <=75 seconds, and `answer_verified:true`.

### Gallery and benchmark matrix

Render the four agreed representative examples through every shipped style: speed/train, data interpretation, percentage, and time/work. This produces an explicit `4 x 20` gallery, though Tier 3 may start with a short benchmark excerpt before full-video acceptance.

For each style/example render, produce:

- 6–12 frame contact sheet including reveal and result frames;
- legibility report;
- benchmark JSON (prepare/frame/encode/size/memory); and
- video/meta only after output validation passes.

Human review is a required gate for new style packs: compare at phone size against `reference/quality_bar_day10.mp4`, reject cluttered styles, and verify question, working, result, and correct option can be read without pausing. "Different" is not enough; it must be clearer or more memorable while remaining easier to follow.

## 8. Risks

| Risk | Likelihood | Impact | Mitigation |
| --- | --- | --- | --- |
| A style obscures or lowers contrast under text | High | Critical | protected masks, contrast sampling, mandatory backplate fallback |
| Twenty divergent implementations create maintenance debt | High | High | StylePack contract and shared primitives before new packs |
| Noisy effects exceed 16 MiB | High | High | entropy budget, looped/static texture, output repair, size tests |
| Tier 3 misses GitHub CPU target | High | High | benchmark gates; low-res safe variants; exclude from `auto` |
| Style changes narration/reveal sync | Medium | Critical | read-only cue contract; styles cannot alter timeline |
| Animated overlays cause flicker or motion sickness | Medium | High | stable reading window, cue-only bursts, phone review |
| Multiprocessing adds nondeterminism or memory spikes | Medium | High | ordered parent writer, bounded queues, single-process default |
| Palette effects fail accessibility/brand expectations | Medium | Medium | contrast tests, theme-controlled palette, high-contrast fallback |

## 9. Open questions

1. **Which eight styles ship first?** Default: the Tier 1 starter set listed above; defer all Tier 3 styles.
2. **Should `auto` rotate only approved Tier 1 styles or include selected Tier 2 styles?** Default: Tier 1 only until benchmarks are established.
3. **Can a style override the entire video or only individual scenes?** Default: video-wide style with optional per-scene override for title/outro only; calculation scenes stay consistent.
4. **Should styles be chosen only by day, or by topic/category too?** Default: rotate by day to stay deterministic and avoid topic classification in the renderer.
5. **How much render time is acceptable for explicit Tier 3 styles?** Default: same three-minute ceiling; do not create a special slow path.
6. **Do you want style parameters exposed in JSON now?** Default: no; keep them theme-defined until 3–4 packs prove the stable parameter vocabulary.
7. **Should the existing default style remain the bot default while styles are experimental?** Default: yes; `auto` is opt-in until contact-sheet and phone review approval.
8. **What is the approval bar for “clearly better than reference”?** Default: readable at phone size without pausing, no contrast failure, no overflow, and unanimous manual approval of a contact sheet plus one full video.

## Decisions needed before implementation

Approve the Tier 1 starter set, whether `auto` is opt-in, the allowed scope of per-scene overrides, and the hard benchmark ceiling for Tier 3. After those decisions, update `DECISIONS.md` before production implementation.
