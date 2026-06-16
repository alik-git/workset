"""Tests for git worktree and submodule operations."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from workset.config import WorksetError
from workset.git import (
    _parse_worktree_list,
    branch_exists,
    fetch_latest_base,
    get_branch_worktrees,
    submodule_init,
    worktree_add,
)

_PORCELAIN_OUTPUT = """\
worktree /home/dev/repos/api
HEAD abcdef1234567890abcdef1234567890abcdef12
branch refs/heads/main

worktree /home/dev/worksets/api-refactor/api
HEAD deadbeef12345678deadbeef12345678deadbeef
branch refs/heads/feat/api-refactor

worktree /home/dev/worksets/other/api
HEAD cafebabe12345678cafebabe12345678cafebabe
detached

"""


def test_parse_worktree_list_finds_branches() -> None:
    """Parse porcelain output into branch → path mapping."""
    result = _parse_worktree_list(_PORCELAIN_OUTPUT)

    assert result["main"] == Path("/home/dev/repos/api")
    assert result["feat/api-refactor"] == Path(
        "/home/dev/worksets/api-refactor/api",
    )


def test_parse_worktree_list_skips_detached() -> None:
    """Detached HEAD worktrees are not included."""
    result = _parse_worktree_list(_PORCELAIN_OUTPUT)
    assert len(result) == 2


def test_parse_worktree_list_empty_output() -> None:
    """Empty output returns empty dict."""
    assert _parse_worktree_list("") == {}


def test_get_branch_worktrees_calls_git(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Call git worktree list --porcelain with correct cwd."""
    calls: list[list[str]] = []

    def fake_run(  # type: ignore[misc]
        args: list[str], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, stdout=_PORCELAIN_OUTPUT, stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = get_branch_worktrees(tmp_path)

    assert calls == [["git", "worktree", "list", "--porcelain"]]
    assert "main" in result


def test_get_branch_worktrees_raises_on_git_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Raise WorksetError when git fails."""
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **_kw: subprocess.CompletedProcess(
            a[0], 128, stdout="", stderr="fatal"
        ),
    )
    with pytest.raises(WorksetError, match="git worktree list failed"):
        get_branch_worktrees(tmp_path)


def test_branch_exists_returns_true_when_zero(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Return True when show-ref exits 0."""
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **_kw: subprocess.CompletedProcess(a[0], 0),
    )
    assert branch_exists(tmp_path, "feat/x") is True


def test_branch_exists_returns_false_when_nonzero(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Return False when show-ref exits nonzero."""
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **_kw: subprocess.CompletedProcess(a[0], 1),
    )
    assert branch_exists(tmp_path, "feat/x") is False


def test_fetch_latest_base_fetches_origin_main(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fetch origin/main and return the remote-tracking base ref."""
    calls: list[list[str]] = []

    def fake_run(  # type: ignore[misc]
        args: list[str], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert fetch_latest_base(tmp_path) == "origin/main"
    assert calls == [["git", "fetch", "origin", "main:refs/remotes/origin/main"]]


def test_fetch_latest_base_raises_on_fetch_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Raise WorksetError when the remote base cannot be fetched."""
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **_kw: subprocess.CompletedProcess(
            a[0], 128, stdout="", stderr="fatal"
        ),
    )

    with pytest.raises(WorksetError, match="git fetch origin main failed"):
        fetch_latest_base(tmp_path)


def test_worktree_add_raises_on_collision(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Raise WorksetError with clear message when branch is already checked out."""
    monkeypatch.setattr(
        "workset.git.get_branch_worktrees",
        lambda _: {"feat/x": Path("/some/other/worktree")},
    )

    with pytest.raises(WorksetError, match="already checked out"):
        worktree_add(tmp_path, tmp_path / "new", "feat/x")


def test_worktree_add_creates_new_branch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Use ``-b`` flag when the branch does not yet exist."""
    calls: list[list[str]] = []
    dest = tmp_path / "new_wt"

    monkeypatch.setattr("workset.git.get_branch_worktrees", lambda _: {})
    monkeypatch.setattr("workset.git.branch_exists", lambda _p, _b: False)

    def fake_run(  # type: ignore[misc]
        args: list[str], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        dest.mkdir(parents=True, exist_ok=True)
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    worktree_add(tmp_path, dest, "feat/new-branch")

    assert calls == [
        ["git", "fetch", "origin", "main:refs/remotes/origin/main"],
        [
            "git",
            "worktree",
            "add",
            "-b",
            "feat/new-branch",
            str(dest),
            "origin/main",
        ],
    ]


def test_worktree_add_can_skip_fetching_latest_base(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Use old HEAD-based branch creation when fetch_latest is disabled."""
    calls: list[list[str]] = []
    dest = tmp_path / "new_wt"

    monkeypatch.setattr("workset.git.get_branch_worktrees", lambda _: {})
    monkeypatch.setattr("workset.git.branch_exists", lambda _p, _b: False)

    def fake_run(  # type: ignore[misc]
        args: list[str], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        dest.mkdir(parents=True, exist_ok=True)
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    worktree_add(tmp_path, dest, "feat/new-branch", fetch_latest=False)

    assert calls == [["git", "worktree", "add", "-b", "feat/new-branch", str(dest)]]


def test_worktree_add_checks_out_existing_branch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No ``-b`` flag when the branch already exists."""
    calls: list[list[str]] = []
    dest = tmp_path / "new_wt"

    monkeypatch.setattr("workset.git.get_branch_worktrees", lambda _: {})
    monkeypatch.setattr("workset.git.branch_exists", lambda _p, _b: True)

    def fake_run(  # type: ignore[misc]
        args: list[str], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        dest.mkdir(parents=True, exist_ok=True)
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    worktree_add(tmp_path, dest, "main")

    assert calls == [["git", "worktree", "add", str(dest), "main"]]


def test_worktree_add_raises_on_git_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Raise WorksetError when git worktree add fails."""
    dest = tmp_path / "new_wt"
    dest.mkdir()

    monkeypatch.setattr("workset.git.get_branch_worktrees", lambda _: {})
    monkeypatch.setattr("workset.git.branch_exists", lambda _p, _b: False)
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **_kw: subprocess.CompletedProcess(
            a[0], 128, stdout="", stderr="fatal: something went wrong"
        ),
    )

    with pytest.raises(WorksetError, match="git worktree add failed"):
        worktree_add(tmp_path, dest, "feat/x", fetch_latest=False)


def test_submodule_init_calls_git(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Call git submodule update --init --recursive with correct cwd."""
    calls: list[list[str]] = []

    def fake_run(  # type: ignore[misc]
        args: list[str], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    submodule_init(tmp_path)

    assert calls == [["git", "submodule", "update", "--init", "--recursive"]]


def test_submodule_init_raises_on_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Raise WorksetError when submodule init fails."""
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **_kw: subprocess.CompletedProcess(a[0], 1),
    )
    with pytest.raises(WorksetError, match="git submodule update failed"):
        submodule_init(tmp_path)
