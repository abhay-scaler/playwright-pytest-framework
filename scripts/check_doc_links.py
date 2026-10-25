"""Check that every documentation link - and every heading fragment - resolves.

Stage 0 of [docs/documentation-split-plan.md]: 81 relative links hold this
documentation together and 31 of them carry a `#fragment`, and nothing checks
either. Five of those fragments point into `DESIGN.md`/`README.md`, the two
documents the split divides, so they are the ones a careless heading edit will
break - silently, because a link whose file exists and whose anchor does not
renders as a link that quietly scrolls nowhere.

    python scripts/check_doc_links.py [--root DIR]

Exit status is 0 when everything resolves and 1 otherwise; every failure prints
the source file, the line, the target and the reason. The counts are printed on
success too, in the plan's own taxonomy, so a drift in them is visible in a
diff rather than only when something breaks.

Standard library only, deliberately: this runs in the Lint job's environment,
which installs `requirements.txt` and nothing else, and a link checker is not
worth a dependency.

Three decisions worth knowing about, because they are what a naive checker gets
wrong:

- **Fenced blocks and inline code spans are not documentation.** Prose that
  quotes link syntax or shows an example path is an example, not a link. The
  split plan's own "counting method" section trips a checker without this rule.
- **Heading fragments follow GitHub's slug algorithm**, including its duplicate
  suffixes (`-1`, `-2`, ...), and headings inside fenced blocks are not
  headings - a `# comment` in a shell example must not become an anchor.
- **Four-space-indented lines are left alone.** Markdown would read them as
  code blocks at the top level, but in these documents they are continuation
  lines of list items, which do contain real links.
"""

from __future__ import annotations

import argparse
import re
import sys
import unicodedata
import urllib.parse
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# The documentation set, matching the scope the split plan measures.
DOC_GLOBS = ("*.md", "docs/**/*.md", "ai_testing/**/*.md")

# Targets that are somebody else's problem.
EXTERNAL_SCHEMES = ("http://", "https://", "mailto:", "ftp://")

FENCE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
HEADING = re.compile(r"^\s{0,3}(#{1,6})\s+(.*?)\s*#*\s*$")
# Inline links: [text](target). The text may contain brackets one level deep
# (`[`foo`](bar)` and `[a [b] c](d)` both occur in the wild); the target runs to
# the first unescaped closing parenthesis, and an optional "title" is dropped.
LINK = re.compile(r"\[(?:[^\[\]]|\[[^\[\]]*\])*\]\(([^()\s]*(?:\([^()]*\))?[^()\s]*)[^()]*\)")
INLINE_CODE = re.compile(r"(`+)(?:.*?)\1", re.DOTALL)


@dataclass(frozen=True)
class Finding:
    """One unresolved link, phrased so it can be acted on without re-deriving it."""

    source: Path
    line: int
    target: str
    reason: str

    def render(self, root: Path) -> str:
        where = self.source.relative_to(root).as_posix()
        return f"{where}:{self.line}  {self.target}\n      {self.reason}"


@dataclass
class Counts:
    """The plan's taxonomy: three link classes that fail in different ways."""

    file: int = 0
    file_anchor: int = 0
    in_page: int = 0

    @property
    def relative(self) -> int:
        return self.file + self.file_anchor

    @property
    def fragments(self) -> int:
        return self.file_anchor + self.in_page

    def render(self) -> str:
        return (
            f"{self.relative} relative links ({self.file} file, "
            f"{self.file_anchor} file+anchor), {self.in_page} in-page anchors, "
            f"{self.fragments} fragments"
        )


def strip_code(text: str) -> list[str]:
    """The document's lines with code blanked out, line numbering preserved.

    Blanking rather than deleting is what keeps the line numbers in diagnostics
    honest. Inline spans are replaced by spaces of the same width so a link
    later on the same line still reports a sensible position.
    """
    lines = text.splitlines()
    out: list[str] = []
    fence: str | None = None
    for line in lines:
        opening = FENCE.match(line)
        if fence is None and opening:
            fence = opening.group(1)[0]
            out.append("")
            continue
        if fence is not None:
            closing = FENCE.match(line)
            if closing and closing.group(1)[0] == fence:
                fence = None
            out.append("")
            continue
        out.append(INLINE_CODE.sub(lambda m: " " * len(m.group(0)), line))
    return out


def slug(heading: str) -> str:
    """GitHub's heading slug: the anchor it generates for a heading's text.

    Lowercase, drop everything that is not a word character, space or hyphen,
    then **each** remaining whitespace character becomes one hyphen. Formatting
    markers (backticks, asterisks, link syntax) disappear with the punctuation,
    which is why `## **Bold** heading` and `## Bold heading` produce the same
    anchor.

    Whitespace is deliberately not collapsed: GitHub removes the punctuation and
    leaves the spaces around it, so `## Test Data & Configuration` anchors as
    `test-data--configuration` with two hyphens. A checker that collapses them
    rejects a link that works, which is worse than one that misses a link that
    does not.
    """
    text = unicodedata.normalize("NFKC", heading)
    # A heading may itself contain a link; GitHub anchors the visible text.
    text = re.sub(r"\[([^\[\]]*)\]\([^()]*\)", r"\1", text)
    text = text.strip().lower()
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"\s", "-", text)


def anchors(path: Path) -> set[str]:
    """Every fragment that resolves inside one document.

    Duplicate headings get GitHub's numeric suffixes: the second "Validation"
    is `#validation-1`. Headings inside fenced blocks are skipped, so a
    `# install dependencies` comment in a shell example is not an anchor.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return set()
    seen: dict[str, int] = {}
    found: set[str] = set()
    for line in strip_code_keeping_headings(text):
        match = HEADING.match(line)
        if not match:
            continue
        base = slug(match.group(2))
        if not base:
            continue
        count = seen.get(base, 0)
        found.add(base if count == 0 else f"{base}-{count}")
        seen[base] = count + 1
    return found


def strip_code_keeping_headings(text: str) -> list[str]:
    """Lines with fenced blocks blanked, inline spans left intact.

    Heading text keeps its backticks: `## The `app(name)` marker` is a real
    heading whose slug comes from the whole line, so blanking inline code here
    would invent the wrong anchor.
    """
    out: list[str] = []
    fence: str | None = None
    for line in text.splitlines():
        opening = FENCE.match(line)
        if fence is None and opening:
            fence = opening.group(1)[0]
            out.append("")
            continue
        if fence is not None:
            closing = FENCE.match(line)
            if closing and closing.group(1)[0] == fence:
                fence = None
            out.append("")
            continue
        out.append(line)
    return out


def documents(root: Path) -> list[Path]:
    found: set[Path] = set()
    for pattern in DOC_GLOBS:
        found.update(p for p in root.glob(pattern) if p.is_file())
    return sorted(found)


def check_document(path: Path, root: Path, counts: Counts) -> list[Finding]:
    findings: list[Finding] = []
    for number, line in enumerate(strip_code(path.read_text(encoding="utf-8")), 1):
        for target in LINK.findall(line):
            target = target.strip()
            if not target or target.startswith(EXTERNAL_SCHEMES):
                if not target:
                    findings.append(Finding(path, number, "(empty)", "link has no target"))
                continue

            raw_path, _, raw_fragment = target.partition("#")
            fragment = urllib.parse.unquote(raw_fragment)

            if not raw_path:
                counts.in_page += 1
                if fragment not in anchors(path):
                    findings.append(
                        Finding(
                            path,
                            number,
                            target,
                            f"no heading in this document produces the anchor {fragment!r}",
                        )
                    )
                continue

            resolved = (path.parent / urllib.parse.unquote(raw_path)).resolve()
            if raw_fragment:
                counts.file_anchor += 1
            else:
                counts.file += 1

            if not resolved.exists():
                findings.append(Finding(path, number, target, f"no such file: {resolved}"))
                continue
            if not raw_fragment:
                continue
            if resolved.suffix.lower() != ".md":
                findings.append(
                    Finding(
                        path,
                        number,
                        target,
                        f"fragment on a non-Markdown target ({resolved.name}); it cannot be "
                        "resolved, so either drop the fragment or link to a document",
                    )
                )
                continue
            if fragment not in anchors(resolved):
                where = (
                    resolved.relative_to(root).as_posix() if root in resolved.parents else resolved
                )
                findings.append(
                    Finding(
                        path,
                        number,
                        target,
                        f"no heading in {where} produces the anchor {fragment!r}",
                    )
                )
    return findings


def check_documentation(root: Path) -> tuple[list[Finding], Counts, int]:
    counts = Counts()
    findings: list[Finding] = []
    files = documents(root)
    for path in files:
        findings.extend(check_document(path, root, counts))
    return findings, counts, len(files)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=REPO_ROOT,
        help="project root to check (default: this repository)",
    )
    args = parser.parse_args(argv)
    root = args.root.resolve()

    findings, counts, scanned = check_documentation(root)
    print(f"{scanned} documents: {counts.render()}")
    if not findings:
        print("all links and fragments resolve")
        return 0
    print(f"\n{len(findings)} unresolved:")
    for finding in findings:
        print(f"  {finding.render(root)}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
