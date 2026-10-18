"""Which source a running Ridge comes from (PRD FR-34: version and commit in every job report).

Release builds of the sidecar carry ``ridge/_build.json`` (``{"commit": ..., "dirty": ...}``),
written by ``tools/build_sidecar.py`` from the checkout it builds. A development checkout is read
from its git metadata files; no git process is run, and uncommitted changes cannot be ruled out,
which ``commit_source: "checkout"`` says. Anything else is ``unknown``. The result never changes
output pixels; it lets a reviewer find the exact source of a report.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from importlib import resources
from pathlib import Path

_SHA = re.compile(r"[0-9a-f]{40}")
_MAX = 64 * 1024  # git metadata files read here are tiny; never read more


def _read(path: Path) -> str | None:
    try:
        with path.open("rb") as fh:
            return fh.read(_MAX).decode("utf-8", "replace")
    except OSError:
        return None


def _git_dirs(root: Path) -> tuple[Path, Path] | None:
    """Return the checkout's git dir and the common dir holding shared refs (clones and worktrees)."""
    dot_git = root / ".git"
    if dot_git.is_dir():
        return dot_git, dot_git
    text = _read(dot_git)  # a worktree: ".git" is a file naming its git dir
    if not text or not text.startswith("gitdir:"):
        return None
    git_dir = (root / text.removeprefix("gitdir:").strip()).resolve()
    common = _read(git_dir / "commondir")
    return git_dir, (git_dir / common.strip()).resolve() if common else git_dir


def _resolve(ref: str, git_dir: Path, common: Path) -> str | None:
    for base in (git_dir, common):
        text = _read(base / ref)
        if text and _SHA.fullmatch(text.strip()):
            return text.strip()
    packed = _read(common / "packed-refs") or ""
    for line in packed.splitlines():
        sha, _, name = line.partition(" ")
        if name.strip() == ref and _SHA.fullmatch(sha):
            return sha
    return None


def checkout_commit(root: Path) -> str | None:
    """Return the commit checked out at `root`, from git's files only (None when it cannot be told)."""
    dirs = _git_dirs(root)
    if dirs is None:
        return None
    head = (_read(dirs[0] / "HEAD") or "").strip()
    if _SHA.fullmatch(head):
        return head  # detached HEAD
    if head.startswith("ref: refs/") and ".." not in head:
        return _resolve(head.removeprefix("ref: "), *dirs)
    return None


def _stamped() -> dict[str, str] | None:
    try:
        doc = json.loads(resources.files("ridge").joinpath("_build.json").read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    commit = doc.get("commit") if isinstance(doc, dict) else None
    if not isinstance(commit, str) or not _SHA.fullmatch(commit):
        return None
    return {"commit": commit, "commit_source": "build, uncommitted changes" if doc.get("dirty") else "build"}


@lru_cache(maxsize=1)
def source_commit() -> dict[str, str]:
    """Return the commit this Ridge was built or checked out from, and how that is known."""
    stamped = _stamped()
    if stamped is not None:
        return stamped
    commit = checkout_commit(Path(__file__).resolve().parents[2])
    if commit is not None:
        return {"commit": commit, "commit_source": "checkout"}
    return {"commit": "unknown", "commit_source": "unknown"}
