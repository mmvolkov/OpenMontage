#!/usr/bin/env python3
"""Re-vendor the HyperFrames Layer 3 skills from an upstream checkout.

What it does:

1. Replaces every ``.agents/skills/<name>`` that exists in ``<hf>/skills/``
   (and removes the skills that upstream renamed away, listed in
   ``RETIRED``), keeping ``.agents/skills/hyperframes/PROVENANCE.md``.
2. Converts ``<hf>/docs/prompting/*.mdx`` (the official Prompt Guide) into
   plain Markdown under ``.agents/skills/hyperframes-prompting/references/``.
   The hand-written ``SKILL.md`` next to it is left untouched.
3. Re-applies the OpenMontage-local patches listed in PROVENANCE.md.
4. Rewrites the commit / version / date header lines of PROVENANCE.md.

Usage::

    git clone --depth 1 https://github.com/heygen-com/hyperframes /tmp/hf
    python scripts/vendor_hyperframes_skills.py --hf /tmp/hf

Then ``git add -f`` the force-tracked fixture named in PROVENANCE.md and run
``tests/contracts/test_agent_skill_pointers.py``.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = REPO_ROOT / ".agents" / "skills"
PROMPTING_SKILL = SKILLS_ROOT / "hyperframes-prompting"
PROVENANCE = SKILLS_ROOT / "hyperframes" / "PROVENANCE.md"
SITE = "https://hyperframes.heygen.com"

# Skills upstream renamed or merged away. Removed if still present locally.
RETIRED = ["hyperframes-media", "website-to-video"]

NARRATION_PATCH = """## Expressive narration contract (OpenMontage addition)

Before generating narration, write a compact voice-performance plan
(see `skills/meta/voice-performance-director.md`):

- `performance_intent` - who the narrator is and how they should feel
- `pacing_profile` - contemplative, conversational, energetic, technical, or custom
- `energy_curve` - how the read changes across the piece
- `pause_policy` - where silence should happen and why
- section-level cues - `pace`, `energy`, `emphasis_words`, `pause_before_seconds`,
  `pause_after_seconds`, and optional provider-ready text

Do not rely on a vague instruction like "make it natural." Put the direction in
the text or provider settings:

- Use short sentences and purposeful punctuation.
- Use `<break time="0.4s"/>` to `<break time="1.0s"/>` for important pauses when
  the chosen provider supports SSML-style break tags.
- Generate a sample from the most performance-sensitive section before batching.
- If the sample sounds monotone, rushed, or ignores pauses, revise the plan or
  provider settings before generating the rest.

"""


# --------------------------------------------------------------------------- #
# Step 1 — copy skills
# --------------------------------------------------------------------------- #
def copy_skills(hf: Path) -> list[str]:
    src_root = hf / "skills"
    names = sorted(p.name for p in src_root.iterdir() if p.is_dir())
    provenance_backup = PROVENANCE.read_text(encoding="utf-8") if PROVENANCE.exists() else None
    for name in names + RETIRED:
        target = SKILLS_ROOT / name
        if target.exists():
            shutil.rmtree(target)
    for name in names:
        shutil.copytree(
            src_root / name,
            SKILLS_ROOT / name,
            ignore=shutil.ignore_patterns(".DS_Store", "node_modules", "__pycache__"),
        )
    if provenance_backup is not None:
        PROVENANCE.write_text(provenance_backup, encoding="utf-8")
    return names


# --------------------------------------------------------------------------- #
# Step 2 — convert docs/prompting/*.mdx
# --------------------------------------------------------------------------- #
def _frontmatter(text: str) -> tuple[dict[str, str], str]:
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    meta: dict[str, str] = {}
    if not m:
        return meta, text
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip().strip('"')
    return meta, text[m.end():]


def _attr(tag: str, name: str) -> str | None:
    m = re.search(rf'\b{name}=(?:"([^"]*)"|\{{`([^`]*)`\}}|\'([^\']*)\')', tag)
    if not m:
        return None
    return next(g for g in m.groups() if g is not None)


def _media_link(icon: str, default_label: str):
    def repl(m: re.Match) -> str:
        tag = m.group(0)
        src = (_attr(tag, "src") or "").split("#")[0]
        label = _attr(tag, "title") or _attr(tag, "aria-label") or default_label
        return f"[{icon} {label}]({src})"

    return repl


def convert_mdx(text: str) -> str:
    text = re.sub(r"^import .*?;\n", "", text, flags=re.M)
    text = re.sub(r"<DocsVideo\b[^>]*?/>", _media_link("▶", "video"), text, flags=re.S)
    text = re.sub(r"<video\b[^>]*?(?:/>|>\s*</video>)", _media_link("▶", "video"), text, flags=re.S)
    text = re.sub(r"<audio\b[^>]*?(?:/>|>\s*</audio>)", _media_link("🔊", "audio"), text, flags=re.S)
    text = re.sub(
        r"<img\b[^>]*?/?>",
        lambda m: f"![{_attr(m.group(0), 'alt') or 'image'}]({_attr(m.group(0), 'src') or ''})",
        text,
        flags=re.S,
    )
    text = re.sub(
        r"<figcaption\b[^>]*>(.*?)</figcaption>",
        lambda m: "\n*" + re.sub(r"\s+", " ", m.group(1)).strip() + "*\n",
        text,
        flags=re.S,
    )
    text = re.sub(r"</?(?:figure|div|canvas)\b[^>]*>", "", text)

    def callout(m: re.Match) -> str:
        kind, body = m.group(1), m.group(2).strip("\n")
        lines = [line.strip() for line in body.splitlines()]
        quoted = "\n".join(f"> {line}" if line else ">" for line in lines)
        return f"> **{kind}:**\n{quoted}"

    text = re.sub(r"<(Note|Tip|Warning)>\n?(.*?)</\1>", callout, text, flags=re.S)

    def accordion(m: re.Match) -> str:
        title = _attr(m.group(1), "title") or "Details"
        body = m.group(2).strip("\n")
        body = "\n".join(line[2:] if line.startswith("  ") else line for line in body.splitlines())
        return f"**{title}**\n\n{body}\n"

    text = re.sub(r"<Accordion(\b[^>]*)>\n?(.*?)</Accordion>", accordion, text, flags=re.S)
    text = re.sub(r"</?AccordionGroup\b[^>]*>\n?", "", text)

    def card(m: re.Match) -> str:
        title = _attr(m.group(1), "title") or "Link"
        href = _attr(m.group(1), "href") or ""
        body = re.sub(r"\s+", " ", m.group(2)).strip()
        return f"- [{title}]({href}) — {body}" if body else f"- [{title}]({href})"

    text = re.sub(r"<Card(\b[^>]*)>(.*?)</Card>", card, text, flags=re.S)
    text = re.sub(r"<Card(\b[^>]*)/>", lambda m: card(re.match(r"(.*)()", m.group(1))), text)
    text = re.sub(r"</?CardGroup\b[^>]*>\n?", "", text)
    text = re.sub(r"<code>(.*?)</code>", r"`\1`", text, flags=re.S)

    text = re.sub(r"\]\(/prompting/overview(#[^)]*)?\)", r"](overview.md\1)", text)
    text = re.sub(r"\]\(/prompting/([a-z0-9-]+)(#[^)]*)?\)", r"](\1.md\2)", text)
    text = re.sub(r"\]\((/[a-z][^)\s]*)\)", rf"]({SITE}\1)", text)

    # de-indent prose that sat inside removed wrappers; drop whitespace-only lines
    text = "\n".join(
        line.strip()
        if line.startswith("  ") and not line.strip().startswith(("-", "|", "```"))
        else line
        for line in text.splitlines()
    )
    text = re.sub(r"\n[ \t]+\n", "\n\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"


def convert_prompting_docs(hf: Path) -> int:
    src = hf / "docs" / "prompting"
    dst = PROMPTING_SKILL / "references"
    if dst.exists():
        shutil.rmtree(dst)
    dst.mkdir(parents=True)
    count = 0
    for mdx in sorted(src.glob("*.mdx")):
        meta, body = _frontmatter(mdx.read_text(encoding="utf-8"))
        slug = mdx.stem
        title = meta.get("title", slug)
        desc = meta.get("description", "")
        header = f"# {title}\n\n"
        if desc:
            header += f"_{desc}_\n\n"
        header += (
            f"<!-- Vendored from heygen-com/hyperframes docs/prompting/{slug}.mdx "
            f"— canonical: {SITE}/prompting/{slug} -->\n\n"
        )
        (dst / f"{slug}.md").write_text(header + convert_mdx(body), encoding="utf-8")
        count += 1
    leftover = {
        f.name: sorted(set(re.findall(r"<[A-Z][A-Za-z]*", f.read_text(encoding="utf-8"))))
        for f in dst.glob("*.md")
    }
    leftover = {k: v for k, v in leftover.items() if v and v != ["<Composition"]}
    if leftover:
        print("WARNING: unconverted JSX components:", json.dumps(leftover, indent=2), file=sys.stderr)
    return count


# --------------------------------------------------------------------------- #
# Step 3 — local patches
# --------------------------------------------------------------------------- #
def apply_local_patches() -> None:
    tts = SKILLS_ROOT / "media-use" / "audio" / "references" / "tts.md"
    if tts.exists():
        text = tts.read_text(encoding="utf-8")
        if "Expressive narration contract" not in text:
            if "## Speed\n" in text:
                text = text.replace("## Speed\n", NARRATION_PATCH + "## Speed\n", 1)
            else:
                text = text.rstrip("\n") + "\n\n" + NARRATION_PATCH
            tts.write_text(text, encoding="utf-8")
            print("patched", tts.relative_to(REPO_ROOT))
    else:
        print("WARNING: media-use tts.md not found; narration patch not applied", file=sys.stderr)


# --------------------------------------------------------------------------- #
# Step 4 — provenance header
# --------------------------------------------------------------------------- #
def _git(hf: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(hf), *args], text=True).strip()


def update_provenance(hf: Path) -> None:
    if not PROVENANCE.exists():
        return
    sha = _git(hf, "rev-parse", "HEAD")
    subject = _git(hf, "log", "-1", "--format=%s")
    date = _git(hf, "log", "-1", "--format=%cd", "--date=short")
    version = "unknown"
    pkg = hf / "packages" / "cli" / "package.json"
    if pkg.exists():
        version = json.loads(pkg.read_text(encoding="utf-8")).get("version", version)
    text = PROVENANCE.read_text(encoding="utf-8")
    text = re.sub(
        r"^- \*\*Vendored commit\*\*: .*$",
        f"- **Vendored commit**: `{sha[:8]}` (`{subject}`, {date})",
        text,
        flags=re.M,
    )
    text = re.sub(
        r"^- \*\*Upstream package version at that commit\*\*: .*$",
        f"- **Upstream package version at that commit**: `hyperframes@{version}`",
        text,
        flags=re.M,
    )
    text = re.sub(r"^- \*\*Vendor date\*\*: .*$", f"- **Vendor date**: {date}", text, flags=re.M)
    PROVENANCE.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--hf", required=True, type=Path, help="path to a heygen-com/hyperframes checkout")
    parser.add_argument("--skip-docs", action="store_true", help="do not regenerate hyperframes-prompting/references")
    args = parser.parse_args()
    hf: Path = args.hf.resolve()
    if not (hf / "skills").is_dir():
        parser.error(f"{hf} does not look like a hyperframes checkout (no skills/ dir)")

    names = copy_skills(hf)
    print(f"copied {len(names)} skills: {', '.join(names)}")
    if not args.skip_docs:
        n = convert_prompting_docs(hf)
        print(f"converted {n} prompting pages into {PROMPTING_SKILL.relative_to(REPO_ROOT)}/references")
    apply_local_patches()
    update_provenance(hf)
    print("done — review PROVENANCE.md, git add -f the force-tracked fixture, run the contract tests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
