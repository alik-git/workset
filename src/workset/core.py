"""Core workset creation logic and result types."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from workset.config import RepoSpec, WorksetConfig, WorksetError, load_config
from workset.env import detect_backend, run_smoke_test, setup_env
from workset.git import submodule_init, worktree_add

if TYPE_CHECKING:
    from pathlib import Path

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class RepoResult:
    """Result for one repo in a workset."""

    name: str
    path: Path
    branch: str
    env_backend: str
    env_ok: bool
    env_message: str
    smoke_passed: bool | None


@dataclass(frozen=True)
class WorksetResult:
    """Result of a workset creation."""

    path: Path
    repos: tuple[RepoResult, ...]

    @property
    def ok(self) -> bool:
        """Return True if all repos were set up without errors."""
        return all(r.env_ok for r in self.repos)


def create_workset(
    slug: str,
    repo_specs: list[str],
    dest: Path | None = None,
    *,
    no_env: bool = False,
    no_smoke: bool = False,
    config: WorksetConfig | None = None,
) -> WorksetResult:
    """Create a workset: one worktree per repo-spec, env set up, smoke tested.

    Args:
        slug: Short identifier used in the path and worklog.
        repo_specs: List of ``name:branch`` or ``/path:branch`` strings.
        dest: Override destination path. Uses config default when None.
        no_env: Skip environment setup.
        no_smoke: Skip smoke tests.
        config: Override config. Loaded from disk when None.

    Returns:
        WorksetResult with per-repo status.

    Raises:
        WorksetError: On unrecoverable errors (branch collision, missing repo).
    """
    cfg = config or load_config()
    workset_path = cfg.resolve_dest(slug, dest)

    specs = [cfg.resolve_spec(s) for s in repo_specs]
    _check_name_collisions(specs)

    LOGGER.info("Creating workset at %s", workset_path)

    results: list[RepoResult] = []
    for spec in specs:
        result = _setup_repo(spec, workset_path, no_env=no_env, no_smoke=no_smoke)
        results.append(result)

    return WorksetResult(path=workset_path, repos=tuple(results))


def _setup_repo(
    spec: RepoSpec,
    workset_path: Path,
    *,
    no_env: bool,
    no_smoke: bool,
) -> RepoResult:
    """Set up a single repo worktree and return its result."""
    worktree_path = workset_path / spec.name
    LOGGER.info("  %s: %s → %s", spec.name, spec.canonical.name, spec.branch)

    worktree_add(spec.canonical, worktree_path, spec.branch)
    submodule_init(worktree_path)

    backend = detect_backend(worktree_path)
    env_ok = True
    env_message = "env skipped"

    if not no_env and backend != "none":
        env_ok, env_message = setup_env(worktree_path, backend)
        if not env_ok:
            LOGGER.warning("    %s", env_message)

    smoke_passed: bool | None = None
    if not no_smoke and env_ok and backend != "none":
        smoke_passed = run_smoke_test(worktree_path, backend)

    return RepoResult(
        name=spec.name,
        path=worktree_path,
        branch=spec.branch,
        env_backend=backend,
        env_ok=env_ok,
        env_message=env_message,
        smoke_passed=smoke_passed,
    )


def _check_name_collisions(specs: list[RepoSpec]) -> None:
    """Raise WorksetError if two specs would produce the same worktree name."""
    seen: dict[str, RepoSpec] = {}
    for spec in specs:
        if spec.name in seen:
            raise WorksetError(
                f"two repo specs resolve to the same name {spec.name!r}: "
                f"{seen[spec.name].canonical} and {spec.canonical}",
            )
        seen[spec.name] = spec
