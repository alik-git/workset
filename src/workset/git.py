"""Git worktree and submodule operations."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from workset.config import WorksetError

LOGGER = logging.getLogger(__name__)


def get_branch_worktrees(canonical: Path) -> dict[str, Path]:
    """Return a mapping of branch name → worktree path for a canonical repo.

    Only includes worktrees that have a branch checked out (not detached HEAD).
    """
    result = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],  # noqa: S607
        cwd=canonical,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise WorksetError(
            f"git worktree list failed in {canonical}:\n{result.stderr.strip()}",
        )
    return _parse_worktree_list(result.stdout)


def _parse_worktree_list(output: str) -> dict[str, Path]:
    """Parse ``git worktree list --porcelain`` output into {branch: path}."""
    branch_to_path: dict[str, Path] = {}
    current_path: Path | None = None

    for line in output.splitlines():
        if line.startswith("worktree "):
            current_path = Path(line[len("worktree ") :])
        elif line.startswith("branch refs/heads/") and current_path is not None:
            branch = line[len("branch refs/heads/") :]
            branch_to_path[branch] = current_path
            current_path = None
        elif not line and current_path is not None:
            current_path = None

    return branch_to_path


def branch_exists(canonical: Path, branch: str) -> bool:
    """Return True if a local branch exists in the canonical repo."""
    result = subprocess.run(  # noqa: S603
        ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"],  # noqa: S607
        cwd=canonical,
        capture_output=True,
        check=False,
    )
    return result.returncode == 0


def fetch_latest_base(
    canonical: Path, remote: str = "origin", branch: str = "main"
) -> str:
    """Fetch the latest remote base and return the remote-tracking ref."""
    result = subprocess.run(  # noqa: S603
        ["git", "fetch", remote, f"{branch}:refs/remotes/{remote}/{branch}"],  # noqa: S607
        cwd=canonical,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise WorksetError(
            f"git fetch {remote} {branch} failed in {canonical}:\n"
            f"{result.stderr.strip()}",
        )
    return f"{remote}/{branch}"


def worktree_add(
    canonical: Path,
    dest: Path,
    branch: str,
    *,
    fetch_latest: bool = True,
) -> None:
    """Add a git worktree at dest, checking out or creating branch.

    Pre-checks for branch collision and raises WorksetError with a clear
    message instead of letting git fail with a raw fatal. New branches are
    created from the freshly fetched remote main by default so stale canonical
    checkouts do not leak old commits into new worksets.
    """
    checked_out = get_branch_worktrees(canonical)
    if branch in checked_out:
        conflict = checked_out[branch]
        raise WorksetError(
            f"branch {branch!r} is already checked out in:\n"
            f"  {conflict}\n\n"
            f"Check out a different branch, or remove that worktree first:\n"
            f"  git worktree remove {conflict}",
        )

    dest.mkdir(parents=True, exist_ok=True)

    exists = branch_exists(canonical, branch)
    if exists:
        cmd = ["git", "worktree", "add", str(dest), branch]
    else:
        cmd = ["git", "worktree", "add", "-b", branch, str(dest)]
        if fetch_latest:
            cmd.append(fetch_latest_base(canonical))

    result = subprocess.run(  # noqa: S603
        cmd,
        cwd=canonical,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise WorksetError(
            f"git worktree add failed for {branch!r} in {canonical}:\n"
            f"{result.stderr.strip()}",
        )


def submodule_init(worktree_path: Path) -> None:
    """Initialize all submodules in the worktree recursively.

    This may be slow for repos with large binary submodules (e.g. STL files).
    Progress is streamed to stderr so it does not appear hung.
    """
    LOGGER.info("  initializing submodules in %s...", worktree_path.name)
    result = subprocess.run(
        ["git", "submodule", "update", "--init", "--recursive"],  # noqa: S607
        cwd=worktree_path,
        check=False,
    )
    if result.returncode != 0:
        raise WorksetError(
            f"git submodule update failed in {worktree_path}",
        )
