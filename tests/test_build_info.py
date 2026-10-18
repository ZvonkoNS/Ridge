"""Which commit a report names: stamped by a release build, read from git files, or unknown."""

from __future__ import annotations

from pathlib import Path

import pytest

from ridge import build_info
from ridge.build_info import checkout_commit, source_commit
from ridge.case import jobs

SHA = "0123456789abcdef0123456789abcdef01234567"
OTHER = "fedcba9876543210fedcba9876543210fedcba98"


def test_a_plain_clone_on_a_branch(tmp_path: Path) -> None:
    (tmp_path / ".git" / "refs" / "heads" / "topic").mkdir(parents=True)
    (tmp_path / ".git" / "HEAD").write_text("ref: refs/heads/topic/x\n", encoding="utf-8")
    (tmp_path / ".git" / "refs" / "heads" / "topic" / "x").write_text(SHA + "\n", encoding="utf-8")
    assert checkout_commit(tmp_path) == SHA


def test_detached_packed_and_worktree_checkouts(tmp_path: Path) -> None:
    common = tmp_path / "main" / ".git"
    (common / "worktrees" / "wt").mkdir(parents=True)
    (common / "packed-refs").write_text(f"# pack-refs\n{OTHER} refs/heads/wt-branch\n", encoding="utf-8")
    (common / "worktrees" / "wt" / "HEAD").write_text("ref: refs/heads/wt-branch\n", encoding="utf-8")
    (common / "worktrees" / "wt" / "commondir").write_text("../..\n", encoding="utf-8")
    wt = tmp_path / "wt"
    wt.mkdir()
    (wt / ".git").write_text(f"gitdir: {common / 'worktrees' / 'wt'}\n", encoding="utf-8")
    assert checkout_commit(wt) == OTHER
    (common / "worktrees" / "wt" / "HEAD").write_text(SHA + "\n", encoding="utf-8")
    assert checkout_commit(wt) == SHA


@pytest.mark.parametrize("head", ["", "garbage", "ref: refs/heads/../../etc", "ref: refs/heads/missing"])
def test_unknown_when_it_cannot_be_told(tmp_path: Path, head: str) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "HEAD").write_text(head, encoding="utf-8")
    assert checkout_commit(tmp_path) is None
    assert checkout_commit(tmp_path / "nowhere") is None


def test_reports_name_the_commit(monkeypatch: pytest.MonkeyPatch) -> None:
    source_commit.cache_clear()
    monkeypatch.setattr(build_info, "_stamped", lambda: {"commit": SHA, "commit_source": "build"})
    env = jobs.environment()
    assert (env["commit"], env["commit_source"]) == (SHA, "build")
    source_commit.cache_clear()
    monkeypatch.setattr(build_info, "_stamped", lambda: None)
    monkeypatch.setattr(build_info, "checkout_commit", lambda root: None)
    assert source_commit() == {"commit": "unknown", "commit_source": "unknown"}
    source_commit.cache_clear()
