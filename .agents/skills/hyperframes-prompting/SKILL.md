---
name: hyperframes-prompting
description: >
  How to prompt an agent (or yourself, or a sub-agent) to author HyperFrames
  video well — vendored from the official HyperFrames Prompt Guide
  (hyperframes.heygen.com/prompting). Use when writing or refining a brief,
  storyboard, per-beat spec, frame-worker dispatch, or user-facing prompt for
  a HyperFrames composition; when a user hands you a HyperFrames prompt to
  execute; when translating taste words ("snappy", "dreamy", "cinematic") into
  framework settings; when a render "feels like a slideshow"; or when
  debugging a composition against the technical rules (timelines, muted video,
  no Math.random, clip attributes, cold-seek visibility). Not the authoring
  contract itself — that is `hyperframes-core`; not the router — that is
  `hyperframes`.
---

# HyperFrames Prompt Guide

HyperFrames is built for AI agents: compositions are plain HTML, the CLI is
non-interactive, and the skills teach the patterns docs alone don't cover.
This skill is the **prompting layer** on top of those skills — the vocabulary
that changes output, the prompt skeleton that removes the decisions agents get
wrong, the iteration patterns that save renders, and the rules that prevent
breakage.

`references/` mirrors the upstream guide page-for-page (34 pages, same slugs
as `https://hyperframes.heygen.com/prompting/<slug>`). Read the index below,
then open only the pages the task needs.

## Where this fits in OpenMontage

- **Rule Zero still applies.** A HyperFrames build inside OpenMontage runs as
  the `compose` (or atelier) stage of a pipeline, with `render_runtime:
  "hyperframes"` locked at proposal. This guide shapes *what you ask for and
  how you describe beats*; it never replaces the pipeline, checkpoints, or
  the canonical artifacts (`script`, `scene_plan`, `edit_decisions`).
- **Who is prompting whom.** Three cases use this skill:
  1. The **user brings a prompt** in the upstream style
     (`/motion-graphics 6-second 1920x1080 …`). Map the slash-command route to
     an OpenMontage pipeline (table below), then honour the spec, beats,
     copy, technique, and negatives verbatim.
  2. **You write the brief** for an atelier build or a `storyboard.html`
     review — use the six-part skeleton and the beat formula so the plan is
     unambiguous before any HTML exists.
  3. **You dispatch a sub-agent** (one frame per worker, as `music-to-video`
     and `general-video` do) — the dispatch text *is* a prompt; write it with
     the same skeleton and the shared motion preamble from `examples.md`.
- **Route mapping** (upstream slash command → OpenMontage entry):

  | Upstream route | OpenMontage pipeline / skill |
  | --- | --- |
  | `/product-launch-video`, `/faceless-explainer`, `/general-video` | `animated-explainer` or `animation` pipeline, HyperFrames runtime; workflow skill read at compose |
  | `/motion-graphics` | `animation` pipeline (short unnarrated unit) + `.agents/skills/motion-graphics` |
  | `/music-to-video` | `animation` pipeline, beats-driven; `.agents/skills/music-to-video` |
  | `/embedded-captions`, `/talking-head-recut` | `talking-head` pipeline; overlay/caption skills at compose |
  | `/pr-to-video` | `screen-demo` or `animated-explainer` pipeline; `.agents/skills/pr-to-video` |
  | `/slideshow` | not a rendered video — deliverable is a navigable deck; confirm with the user first |
  | `/remotion-to-hyperframes` | explicit port only; `.agents/skills/remotion-to-hyperframes` |

## The essentials (read before writing any HyperFrames prompt)

**Two prompt shapes.** *Cold start* describes the video from scratch — always
state duration, aspect ratio (default 1920x1080 @ 30fps), mood/style, and key
elements. *Warm start* hands the agent something to synthesize (URL, doc, CSV,
transcript, PR) — richer output because the copy is grounded in something
specific.

**The six-part skeleton** (`anatomy.md`) — every one-shot prompt that works:

```text
[route]      /motion-graphics
[spec]       8-second 1920x1080 video.
[beats]      Beat 1 (0-4s): ...  Beat 2 (4-5s): ...  Beat 3 (5-8s): ...
[copy]       the exact on-screen text, quoted ("/" for line breaks)
[technique]  Adapt the `code-typing` and `vfx-shatter` registry blocks.
[negatives]  No narration, no image or media files.
```

Inside each beat, the **beat formula**: element · motion · layout · style ·
timing — one sentence per element. Beat-timestamped prompting is
HyperFrames' native language: every beat maps to a timed clip, so per-beat
descriptions translate losslessly.

**The specification dial** (`specification-dial.md`). Spec density controls
how far the result drifts from what you imagined, not whether it works. Pin a
technique (a registry block by exact catalog name) wherever the default choice
can fail; leave taste to the agent where you trust it.

**Vocabulary that maps to settings** (`vocabulary.md`) — say the word, get
the ease:

| Say | Ease | Feels like |
| --- | --- | --- |
| smooth | `power2.out` | natural deceleration |
| snappy | `power4.out` | quick and decisive |
| bouncy | `back.out` | overshoots then settles |
| springy | `elastic.out` | oscillates into place |
| dramatic | `expo.out` | fast start, long glide |
| dreamy | `sine.inOut` | slow, symmetrical |

Timing shorthand: fast 0.2s = energy · medium 0.4s = professional · slow 0.6s
= luxury · very slow 1–2s = cinematic. The page also maps camera language,
caption tone, transition energy, audio, and voice adjectives.

**Motion that reads premium** (`motion.md`, eight rules): nothing stops (an
ambient idle instead of a frozen final frame), the camera acts (one continuous
non-settling move), action overlaps (stagger offsets shorter than the
animations they offset), overshoot on transforms only, three depth layers with
parallax, one focal element at display scale, one named **spectacle beat** per
piece, and imperfection that stays reproducible (seeded, never
`Math.random()`). This is what separates "video" from "slideshow".

**Iterate like an editor** (`iterating.md`): small targeted edits beat
re-specification; calibrate with absolute targets ("title at y=180px, 64px",
not "a bit higher"); `lint` + `check` gate every render — they can't tell you
it's good, only that it's not broken.

**Technical rules that keep renders correct** (`rules-and-anti-patterns.md`):

1. Register every timeline on `window.__timelines`.
2. `<video>` must be `muted`; audio lives in separate `<audio>` elements.
3. No `Math.random()` — seeded PRNG only; quantize stop-motion holds on the
   integer frame index.
4. Synchronous timeline construction — no `async`/`fetch` while building.
5. Timed elements need `class="clip"` + `data-start`, `data-duration`,
   `data-track-index`.
6. Entrance animation on every scene. 7. Transitions between scenes.

Plus the cold-seek hazards: reveal the destination (`opacity: 1` in the `to`
vars), hide initial state outside the timeline, never stack relative tweens on
a property another writer animates, never measure DOM geometry inside a
timeline callback, never combine CSS `translate(-50%,-50%)` centering with GSAP
`x`/`y`.

## Reference index (upstream level ladder)

| Level | Pages |
| --- | --- |
| **Overview** | `overview.md` — setup, the two prompt shapes, the interview → `BRIEF.md`, recommended loop |
| **1 — Your first video** (workflow warm starts) | `product-launch.md`, `explainers.md`, `code-and-prs.md`, `captions-and-talking-heads.md`, `music-and-slideshows.md`, `motion-graphics.md` |
| **2 — Control** | `anatomy.md`, `specification-dial.md`, `vocabulary.md`, `visual-specs.md`, `examples.md` (verified prompts + the shared motion preamble) |
| **3 — Life** | `motion.md`, `transitions.md` |
| **4 — Substance** | `code-blocks.md`, `data-and-maps.md`, `overlays-and-lower-thirds.md`, `captions-catalog.md`, `generated-artwork.md`, `color-grading.md`, `vfx-and-liquid-glass.md`, `runtimes-and-3d.md` |
| **5 — Voice and sound** | `media-and-audio.md`, `audio-effects.md` |
| **6 — Scale** | `design-systems.md`, `variables-and-templating.md`, `storyboards.md`, `editing-existing-videos.md`, `iterating.md`, `recreating-references.md`, `rendering-and-output.md`, `remotion-migration.md` |
| **7 — Capstone** | `capstone.md` — one prompt, every technique, a 62-second film |
| **Appendix** | `rules-and-anti-patterns.md` — the lookup table for lint rules and prompt friction |

Pages link to each other with relative `.md` links; links into the rest of
the HyperFrames docs (catalog, guides, concepts) are absolute URLs to
`hyperframes.heygen.com`. Embedded demo videos are kept as links to the
upstream MP4s — open one when a page's claim needs a visual check.

## Related skills

- `hyperframes` — router; `hyperframes-core` — composition contract;
  `hyperframes-animation` / `hyperframes-keyframes` — motion mechanics;
  `hyperframes-creative` — palette, type, narration, beat planning;
  `hyperframes-registry` — search the catalog before hand-building a look;
  `media-use` / `hyperframes-audio` — assets and mixing; `hyperframes-cli` —
  `lint`, `check`, `preview`, `render`.
- OpenMontage Layer 2: `skills/core/hyperframes.md` (runtime bridge),
  `skills/meta/bespoke-composition.md` (atelier sequencing),
  `skills/meta/taste-direction.md` (taste dials that the vocabulary page
  turns into words).
