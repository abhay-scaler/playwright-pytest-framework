"""The documentation link checker: what it resolves, and what it refuses to.

`scripts/check_doc_links.py` is the only thing standing between a renamed
heading and a link that silently scrolls nowhere, so the cases that matter are
the ones a naive checker gets wrong: code examples that look like links,
GitHub's slug rules, duplicate headings, percent-encoded fragments, and
headings inside shell examples.

Each case builds a throwaway documentation set under `tmp_path` and runs the
checker against it with `--root`, so nothing here depends on this repository's
own documents - except the last test, which deliberately does.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "check_doc_links.py"


def _load_checker() -> Any:
    """scripts/ is not a package, so the checker is loaded by path.

    It is registered in `sys.modules` first: its `@dataclass` definitions look
    their own module up by name while being created, and fail with an opaque
    `AttributeError` if it is not there.
    """
    spec = importlib.util.spec_from_file_location("check_doc_links", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


checker = _load_checker()


def _docs(tmp_path: Path, **files: str) -> Path:
    """A documentation set: names map to content, `/` creates subdirectories."""
    for name, content in files.items():
        path = tmp_path / name.replace("__", "/")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return tmp_path


def _check(root: Path):
    return checker.check_documentation(root)


# --------------------------------------------------------------------------- #
# Parsing: what counts as a link
# --------------------------------------------------------------------------- #


def test_a_relative_link_is_found_and_counted(tmp_path):
    root = _docs(
        tmp_path,
        **{"README.md": "see [the design](DESIGN.md)\n", "DESIGN.md": "# Design\n"},
    )

    findings, counts, scanned = _check(root)

    assert not findings
    assert (counts.file, counts.file_anchor, counts.in_page) == (1, 0, 0)
    assert counts.relative == 1
    assert scanned == 2


def test_links_inside_a_fenced_block_are_examples_not_links(tmp_path):
    root = _docs(
        tmp_path,
        **{
            "README.md": (
                "real [ok](DESIGN.md)\n"
                "```markdown\n"
                "[not a link](does-not-exist.md)\n"
                "[nor this](#nowhere)\n"
                "```\n"
                "~~~\n"
                "[tilde fence](also-missing.md)\n"
                "~~~\n"
            ),
            "DESIGN.md": "# Design\n",
        },
    )

    findings, counts, _ = _check(root)

    assert not findings, [f.render(root) for f in findings]
    assert counts.relative == 1


def test_links_inside_inline_code_are_examples_not_links(tmp_path):
    root = _docs(
        tmp_path,
        **{
            "README.md": (
                "the pattern is `[text](target)` and ``[also](this)`` is prose\n"
                "but [this one](DESIGN.md) is real\n"
            ),
            "DESIGN.md": "# Design\n",
        },
    )

    findings, counts, _ = _check(root)

    assert not findings, [f.render(root) for f in findings]
    assert counts.relative == 1


def test_a_link_with_bracketed_text_is_still_parsed(tmp_path):
    root = _docs(
        tmp_path,
        **{"README.md": "see [`code` and [brackets]](DESIGN.md)\n", "DESIGN.md": "# D\n"},
    )

    findings, counts, _ = _check(root)

    assert not findings
    assert counts.relative == 1


def test_an_external_link_is_left_to_its_owner(tmp_path):
    root = _docs(tmp_path, **{"README.md": "[site](https://example.test/a.md#frag)\n"})

    findings, counts, _ = _check(root)

    assert not findings
    assert (counts.relative, counts.in_page) == (0, 0)


# --------------------------------------------------------------------------- #
# Path resolution
# --------------------------------------------------------------------------- #


def test_a_missing_target_is_reported_with_file_line_and_reason(tmp_path):
    root = _docs(tmp_path, **{"docs__guide.md": "line one\nsee [gone](../nowhere.md)\n"})

    findings, _, _ = _check(root)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.source == root / "docs" / "guide.md"
    assert finding.line == 2
    assert finding.target == "../nowhere.md"
    assert "no such file" in finding.reason
    rendered = finding.render(root)
    assert rendered.startswith("docs/guide.md:2  ../nowhere.md")


def test_a_relative_path_resolves_from_the_linking_document(tmp_path):
    root = _docs(
        tmp_path,
        **{
            "docs__ai-testing__workflow.md": "[up two](../../README.md)\n[up one](../plan.md)\n",
            "README.md": "# R\n",
            "docs__plan.md": "# P\n",
        },
    )

    findings, counts, _ = _check(root)

    assert not findings, [f.render(root) for f in findings]
    assert counts.file == 2


def test_a_percent_encoded_path_is_decoded(tmp_path):
    root = _docs(tmp_path, **{"README.md": "[spaced](my%20doc.md)\n", "my doc.md": "# M\n"})

    findings, _, _ = _check(root)

    assert not findings, [f.render(root) for f in findings]


# --------------------------------------------------------------------------- #
# Fragment resolution
# --------------------------------------------------------------------------- #


def test_github_slug_rules_are_applied(tmp_path):
    root = _docs(
        tmp_path,
        **{
            "README.md": (
                "[a](DESIGN.md#8-cicd-flow)\n"
                "[b](DESIGN.md#test-data--configuration-approach)\n"
                "[c](DESIGN.md#the-appname-marker)\n"
            ),
            "DESIGN.md": (
                "## 8. CI/CD Flow\n\n## Test Data & Configuration Approach\n\n"
                "## The `app(name)` marker\n"
            ),
        },
    )

    findings, counts, _ = _check(root)

    assert not findings, [f.render(root) for f in findings]
    assert counts.file_anchor == 3
    assert counts.fragments == 3


def test_a_missing_fragment_is_reported_even_though_the_file_exists(tmp_path):
    root = _docs(
        tmp_path,
        **{"README.md": "[gone](DESIGN.md#renamed-away)\n", "DESIGN.md": "## Still here\n"},
    )

    findings, counts, _ = _check(root)

    assert len(findings) == 1
    assert findings[0].target == "DESIGN.md#renamed-away"
    assert "'renamed-away'" in findings[0].reason
    assert "DESIGN.md" in findings[0].reason
    assert counts.file_anchor == 1


def test_duplicate_headings_get_githubs_numeric_suffixes(tmp_path):
    root = _docs(
        tmp_path,
        **{
            "README.md": (
                "[first](DESIGN.md#validation)\n"
                "[second](DESIGN.md#validation-1)\n"
                "[third](DESIGN.md#validation-2)\n"
            ),
            "DESIGN.md": "## Validation\n\n## Validation\n\n## Validation\n",
        },
    )

    findings, _, _ = _check(root)

    assert not findings, [f.render(root) for f in findings]


def test_a_suffix_beyond_the_duplicates_is_still_reported(tmp_path):
    root = _docs(
        tmp_path,
        **{
            "README.md": "[fourth](DESIGN.md#validation-3)\n",
            "DESIGN.md": "## Validation\n\n## Validation\n",
        },
    )

    findings, _, _ = _check(root)

    assert len(findings) == 1
    assert "'validation-3'" in findings[0].reason


def test_an_in_page_anchor_resolves_against_its_own_document(tmp_path):
    root = _docs(
        tmp_path,
        **{
            "README.md": (
                "- [Running Tests](#running-tests)\n"
                "- [Nope](#not-a-heading)\n"
                "\n## Running Tests\n"
            )
        },
    )

    findings, counts, _ = _check(root)

    assert counts.in_page == 2
    assert len(findings) == 1
    assert findings[0].target == "#not-a-heading"
    assert "this document" in findings[0].reason


def test_a_percent_encoded_fragment_is_decoded(tmp_path):
    root = _docs(
        tmp_path,
        **{
            "README.md": "[encoded](DESIGN.md#caf%C3%A9-section)\n",
            "DESIGN.md": "## Café section\n",
        },
    )

    findings, _, _ = _check(root)

    assert not findings, [f.render(root) for f in findings]


def test_headings_inside_a_fenced_block_are_not_anchors(tmp_path):
    root = _docs(
        tmp_path,
        **{
            "README.md": "[shell comment](DESIGN.md#install-dependencies)\n",
            "DESIGN.md": (
                "## Real heading\n\n```bash\n# install dependencies\npip install -e .\n```\n"
            ),
        },
    )

    findings, _, _ = _check(root)

    assert len(findings) == 1
    assert "'install-dependencies'" in findings[0].reason


def test_a_fragment_on_a_non_markdown_target_is_reported_not_ignored(tmp_path):
    root = _docs(
        tmp_path,
        **{"README.md": "[config](settings.json#keys)\n", "settings.json": "{}\n"},
    )

    findings, _, _ = _check(root)

    assert len(findings) == 1
    assert "non-Markdown" in findings[0].reason


def test_an_empty_target_is_reported(tmp_path):
    root = _docs(tmp_path, **{"README.md": "a [dangling]() link\n"})

    findings, _, _ = _check(root)

    assert len(findings) == 1
    assert findings[0].reason == "link has no target"


# --------------------------------------------------------------------------- #
# Exit status and this repository's own documentation
# --------------------------------------------------------------------------- #


def test_main_exits_zero_when_everything_resolves(tmp_path, capsys):
    root = _docs(tmp_path, **{"README.md": "[d](DESIGN.md)\n", "DESIGN.md": "# D\n"})

    assert checker.main(["--root", str(root)]) == 0
    assert "all links and fragments resolve" in capsys.readouterr().out


def test_main_exits_one_and_prints_the_findings(tmp_path, capsys):
    root = _docs(tmp_path, **{"README.md": "[broken](missing.md)\n[bad](#nowhere)\n"})

    assert checker.main(["--root", str(root)]) == 1
    out = capsys.readouterr().out
    assert "2 unresolved" in out
    assert "README.md:1  missing.md" in out
    assert "README.md:2  #nowhere" in out


def test_this_repositorys_documentation_resolves(capsys):
    """This repository's own documentation, whatever it currently is.

    No count floors: the framework ships a README and no `docs/` pages by
    design, so a lower bound on links would assert a documentation shape rather
    than its correctness. The consumer project this was extracted from asserts
    its own, larger set the same way. What is pinned is that at least one
    document is scanned - an empty scan must not pass as "everything
    resolves" - and that the counts stay internally consistent.
    """
    findings, counts, scanned = _check(REPO_ROOT)

    assert not findings, "\n".join(f.render(REPO_ROOT) for f in findings)
    assert scanned >= 1, scanned
    assert counts.relative == counts.file + counts.file_anchor
    assert counts.fragments == counts.file_anchor + counts.in_page


def test_the_checker_is_runnable_as_a_script():
    """It is invoked as `python scripts/check_doc_links.py`, so it must stay
    executable that way rather than becoming an importable module only."""
    source = SCRIPT.read_text(encoding="utf-8")

    assert 'if __name__ == "__main__":' in source
    assert "sys.exit(main())" in source


@pytest.mark.parametrize(
    ("heading", "expected"),
    [
        ("Simple Heading", "simple-heading"),
        ("8. CI/CD Flow", "8-cicd-flow"),
        ("Test Data & Configuration", "test-data--configuration"),
        ("`code` in a heading", "code-in-a-heading"),
        ("**bold** and *italic*", "bold-and-italic"),
        ("trailing punctuation!", "trailing-punctuation"),
        ("snake_case stays", "snake_case-stays"),
        ("[a link](target.md) in a heading", "a-link-in-a-heading"),
    ],
)
def test_slug_matches_githubs_rules(heading, expected):
    assert checker.slug(heading) == expected
