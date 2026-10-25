"""Resolving the *consumer project's* root, and the paths derived from it.

The framework used to take its own location as the project root::

    BASE_DIR = Path(__file__).resolve().parent.parent

which is correct only while the framework lives at the root of the repository
that uses it. Installed as a package, that expression points at site-packages:
artifacts would be written beside the installed code and `apps/` would be looked
for there too. Nothing here may depend on where the framework itself happens to
be installed.

A project root is resolved in this order, and the first one that applies wins:

1. **An explicit root from the caller** - `pwpf-validate-catalog --root`,
   or any code calling `set_project_root(..., source="caller")`. The caller is
   being deliberate, so this outranks everything.
2. **The active pytest session's rootdir** - the plugin passes
   `config.rootpath` here in its `pytest_configure`, which is pytest's own
   authoritative answer and already accounts for `-c`, `--rootdir` and ini
   discovery.
3. **`PWPF_ROOT`** - for code that runs outside pytest and cannot pass a root.
4. **The nearest `pytest.ini` at or above the current working directory** - the
   same upward search pytest performs, so running from a nested directory of a
   consumer project works.

If none applies, `ProjectRootError` says how to supply one. The framework's own
directory is never a fallback: guessing it is exactly the bug this module
exists to prevent.
"""

from __future__ import annotations

import os
from pathlib import Path

#: What marks a directory as a consumer project root. pytest's own rootdir
#: algorithm considers several files; this framework configures itself through
#: pytest.ini, so that is the marker it looks for.
PROJECT_MARKER = "pytest.ini"

#: Environment override, for entry points that are neither pytest nor able to
#: pass an explicit root.
ROOT_ENV_VAR = "PWPF_ROOT"

_caller_root: Path | None = None
_pytest_root: Path | None = None


class ProjectRootError(RuntimeError):
    """Raised when no consumer project root can be resolved, or when one that
    was supplied explicitly is not usable."""


def _validate(path: str | Path, source: str, *, require_marker: bool) -> Path:
    candidate = Path(path).expanduser()
    try:
        candidate = candidate.resolve(strict=True)
    except OSError:
        raise ProjectRootError(
            f"{source} points at {path!r}, which does not exist. Give a path to the "
            "root of the project whose apps/ and tests/ should be used."
        ) from None
    if not candidate.is_dir():
        raise ProjectRootError(f"{source} points at {candidate}, which is not a directory.")
    if require_marker and not (candidate / PROJECT_MARKER).is_file():
        raise ProjectRootError(
            f"{source} points at {candidate}, which has no {PROJECT_MARKER}. That file is "
            "what marks a project root; without it this is probably not the directory you "
            "meant, and silently accepting it would put artifacts somewhere surprising."
        )
    return candidate


def set_project_root(path: str | Path, *, source: str = "caller") -> Path:
    """Pin the project root. `source="pytest"` records it as the session's
    rootdir, which an explicit caller root still outranks."""
    global _caller_root, _pytest_root
    if source == "pytest":
        # pytest's rootpath is authoritative for the session and is not
        # second-guessed here: it already accounts for -c, --rootdir and ini
        # discovery, and a project may legitimately run pytest from a rootdir
        # configured some other way.
        _pytest_root = _validate(path, "the pytest session rootdir", require_marker=False)
        return _pytest_root
    _caller_root = _validate(path, f"The {source}-supplied project root", require_marker=False)
    return _caller_root


def clear_project_root(*, caller: bool = True, pytest_session: bool = True) -> None:
    """Forget pinned roots. Used by tests; harmless elsewhere."""
    global _caller_root, _pytest_root
    if caller:
        _caller_root = None
    if pytest_session:
        _pytest_root = None


def find_project_root(start: str | Path | None = None) -> Path | None:
    """The nearest directory at or above `start` containing the project marker."""
    current = Path(start or Path.cwd()).expanduser().resolve()
    for candidate in (current, *current.parents):
        if (candidate / PROJECT_MARKER).is_file():
            return candidate
    return None


def project_root() -> Path:
    """The consumer project's root, by the precedence documented above."""
    if _caller_root is not None:
        return _caller_root
    if _pytest_root is not None:
        return _pytest_root

    override = os.environ.get(ROOT_ENV_VAR)
    if override:
        return _validate(override, f"${ROOT_ENV_VAR}", require_marker=True)

    discovered = find_project_root()
    if discovered is not None:
        return discovered

    raise ProjectRootError(
        "No project root could be resolved. The framework does not fall back to its own "
        "installation directory, because that would put artifacts and application lookups "
        f"inside the installed package. Either set {ROOT_ENV_VAR} to the project root, pass "
        "--root where a command supports it, or run from a directory at or below one "
        f"containing {PROJECT_MARKER}."
    )
