# HyperFrames Skills — Provenance

The HyperFrames-family skills under `.agents/skills/` are vendored from the upstream HyperFrames monorepo:

- **Source**: https://github.com/heygen-com/hyperframes (Apache-2.0)
- **Vendored commit**: `02147b8d` (`fix(core): a clip gets its own inline display back when the runtime shows it (#4498)`, 2026-09-25)
- **Upstream package version at that commit**: `hyperframes@0.8.77`
- **Vendor date**: 2026-09-25
- **Previous vendor**: `3351fb1a` / `v0.7.17` (2026-06-27)
- **Re-sync tool**: `scripts/vendor_hyperframes_skills.py` (copies `skills/*`, converts `docs/prompting/*.mdx` into `hyperframes-prompting/references/`, rewrites the header of this file)

## What's vendored (21 upstream skills + 1 derived skill)

**Core domain skills** (the set the upstream Prompt Guide calls "install all of these"):

| Skill | Role |
|---|---|
| `hyperframes` | Entry point / router. Resumes project state (`BRIEF.md`, `hyperframes.json`, `STORYBOARD.md`), runs the intent interview, routes to the owning workflow, maps domain skills. |
| `hyperframes-core` | The composition contract — `data-*` timing, `class="clip"`, tracks, sub-compositions, variables, framework-owned media playback, determinism, `creator-editing-recipes.md`. |
| `hyperframes-animation` | All motion knowledge — atomic rules, scene blueprints, transitions, techniques, seven runtime adapters (GSAP default, Lottie, Three.js, Anime.js, CSS, WAAPI, TypeGPU). |
| `hyperframes-keyframes` | **New in 0.8.** Seek-safe keyframes across runtimes — punch-in/out, zoom, reframe, Ken Burns, camera moves, FLIP, paths, masks, SVG morph/draw, 3D depth, `hyperframes keyframes` diagnostics. |
| `hyperframes-creative` | Non-animation creative direction — design spec (`frame.md` / `design.md`), palettes, typography, narration, beat planning, audio-reactive visuals. |
| `hyperframes-cli` | Dev loop — `init`, `add`, `lint`, `check`, `validate`, `inspect`, `snapshot`, `preview`, `render`, `publish`, `lambda`, `doctor`, `skills`, `timeline`, `upgrade`. |
| `hyperframes-registry` | Search the catalog before hand-building a look; `hyperframes add` blocks/components; authoring new blocks upstream. |
| `media-use` | Agent Media OS — the single media skill: BGM / SFX / image / icon / logo / voice / grade / LUT resolution, plus the shared audio engine (TTS, transcription, captions, background removal). **Absorbed the former `hyperframes-media` skill in 0.8.** |
| `hyperframes-audio` | **New in 0.8.** Mixing audio already placed in a composition — fades, crossfades, gain, automation, ducking / voiceover carve, effect chains (`data-fx-chain`), submix buses (`<hf-audio-group>`). |
| `hyperframes-studio` | **New in 0.8.** Timeline layout conventions for projects opened in HyperFrames Studio — one caption track, one element kind per track, every scene a sub-composition, safe zones. |
| `general-video` | The general authoring workflow — multi-scene pieces, reels, montages, remixes, companion mode; the fallback when no specialized workflow fits. |

**Workflow skills** (upstream's input-matched routes; `/hyperframes` routes to whichever is installed):

| Skill | Input → output |
|---|---|
| `product-launch-video` | Product / marketing URL, script, or brief → launch or promo video, or a site tour. **Absorbed the former `website-to-video` skill** (site tours / showcases now route here). |
| `faceless-explainer` | Arbitrary text (no URL, no footage) → faceless explainer with invented visuals. |
| `pr-to-video` | GitHub PR → code-change explainer. |
| `embedded-captions` | Existing talking-head video → same footage with captions (35-style catalog, local transcription + matting). |
| `talking-head-recut` | Existing talking-head / interview / podcast → footage packaged with transcript-synced graphic overlays. |
| `motion-graphics` | Logo / stat / tweet / brief → short unnarrated motion graphic, MP4 or transparent overlay. |
| `music-to-video` | Music track (file, video audio, or generated from a mood brief) → beat-synced video. |
| `slideshow` | Deck outline → navigable presentation with presenter mode (not a rendered MP4). |
| `remotion-to-hyperframes` | Explicit port of a Remotion (React) composition → HyperFrames HTML. One-way, Remotion-only. |
| `figma` | Figma file / frame / URL → imported assets, brand tokens, reconstructed motion. |

**Derived skill (built from upstream docs, not an upstream skill):**

| Skill | Source |
|---|---|
| `hyperframes-prompting` | `docs/prompting/*.mdx` — the official Prompt Guide (https://hyperframes.heygen.com/prompting/overview), 34 pages converted to plain Markdown under `references/`, plus an OpenMontage-authored `SKILL.md` that indexes them and maps upstream slash-command routes to OpenMontage pipelines. |

## Removed in this vendor (renamed / merged upstream)

- `hyperframes-media` → content lives in `media-use` (audio engine, TTS, transcription, captions, background removal) and `hyperframes-audio` (placed-track mixing).
- `website-to-video` → content lives in `product-launch-video` (site tours and showcases) and `general-video`.

## OpenMontage-local modifications

Keep these when re-vendoring (the re-sync script re-applies the first one; check the second by hand):

1. `media-use/audio/references/tts.md` — section **"Expressive narration contract (OpenMontage addition)"** inserted before `## Speed`. Ported from the former `hyperframes-media/references/tts.md` patch; it ties HyperFrames narration to `skills/meta/voice-performance-director.md`.
2. `embedded-captions/scripts/fixtures/heroless/transcript.json` — upstream force-tracks this fixture despite its own `.gitignore` rule (`transcript.json`). It is force-added here too (`git add -f`); a plain `git add` after re-copying will silently drop it.

Everything else is byte-identical to upstream at the vendored commit (verified with `diff -rq` against the checkout).

## Why the workflow skills are vendored now (previously "intentionally NOT vendored")

The 0.7 vendor left out `embedded-captions`, `faceless-explainer`, `general-video`, `pr-to-video`, `product-launch-video`, `slideshow`, `talking-head-recut` because they compete with OpenMontage's pipeline routing. In 0.8 the `hyperframes` router and the domain skills refer to them constantly (`/general-video` owns companion mode and every creator-edit recipe; `website-to-video` was folded into `product-launch-video`), so leaving them out left dangling routes. They are vendored as **Layer 3 knowledge** only:

- OpenMontage's Rule Zero, pipeline manifests, and checkpoints remain the orchestration authority. A workflow skill is read inside the `compose` / atelier stage once `render_runtime: "hyperframes"` is locked — never as a replacement for the pipeline.
- The route mapping (upstream slash command → OpenMontage pipeline) lives in `hyperframes-prompting/SKILL.md`.
- The upstream skills' "keep this skill fresh — run `npx hyperframes skills update <name>`" preambles refer to the upstream installer. In OpenMontage the vendored copy is the source of truth; do not run the updater inside the repo (it would write into `.agents/skills/` outside this provenance).

## Re-sync instructions

```bash
git clone --depth 1 https://github.com/heygen-com/hyperframes /path/to/hyperframes
python scripts/vendor_hyperframes_skills.py --hf /path/to/hyperframes
git add -f .agents/skills/embedded-captions/scripts/fixtures/heroless/transcript.json
python -m pytest tests/contracts/test_agent_skill_pointers.py -q
```

Then review the diff of `skills/core/hyperframes.md`, `skills/INDEX.md`, and `skills/meta/animation-runtime-selector.md` for renamed skills, and update the header of this file (the script rewrites commit / version / date lines only).
