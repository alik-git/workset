"""Configuration loading and repo-spec resolution for workset."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from datetime import UTC, datetime, tzinfo
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from workset.paths import dated_dir


class WorksetError(Exception):
    """User-facing workset error."""


@dataclass(frozen=True)
class RepoSpec:
    """A resolved repo specification."""

    canonical: Path
    branch: str
    name: str


@dataclass(frozen=True)
class WorksetConfig:
    """Loaded workset configuration."""

    workset_root: Path
    date_prefix: bool
    timezone: tzinfo
    repos: dict[str, Path]

    def resolve_dest(self, slug: str, dest_override: Path | None = None) -> Path:
        """Resolve the workset destination path for a given slug."""
        if dest_override is not None:
            return dest_override
        if self.date_prefix:
            today = datetime.now(tz=UTC).astimezone(self.timezone).date()
            return dated_dir(self.workset_root, today) / slug
        return self.workset_root / slug

    def resolve_spec(self, spec: str) -> RepoSpec:
        """Resolve a repo-spec string to a canonical path and branch.

        Accepts ``name:branch`` (looked up in config) or ``/path/to/repo:branch``.
        """
        if ":" not in spec:
            raise WorksetError(
                f"invalid repo spec {spec!r}: expected <name>:<branch> or <path>:<branch>",  # noqa: E501
            )
        repo_part, branch = spec.rsplit(":", 1)
        if not branch.strip():
            raise WorksetError(f"invalid repo spec {spec!r}: branch cannot be empty")

        canonical, name = self._resolve_canonical(repo_part)
        _require_git_repo(canonical)
        return RepoSpec(canonical=canonical, branch=branch.strip(), name=name)

    def _resolve_canonical(self, repo_part: str) -> tuple[Path, str]:
        """Return (canonical_path, short_name) for a repo identifier."""
        candidate = Path(repo_part).expanduser()
        if candidate.is_absolute():
            return candidate.resolve(), candidate.name

        if repo_part in self.repos:
            return self.repos[repo_part], repo_part

        repos_dir = os.environ.get("WORKSET_REPOS_DIR")
        if repos_dir:
            via_env = Path(repos_dir).expanduser() / repo_part
            if via_env.is_dir():
                return via_env.resolve(), repo_part

        tried: list[str] = ["~/.config/workset/repos.toml [repos]"]
        if repos_dir:
            tried.append(f"$WORKSET_REPOS_DIR/{repo_part}")
        raise WorksetError(
            f"repo {repo_part!r} not found. Tried:\n"
            + "\n".join(f"  {t}" for t in tried)
            + "\nAdd it to [repos] in ~/.config/workset/repos.toml or use a full path.",
        )


_DEFAULT_CONFIG = Path.home() / ".config" / "workset" / "repos.toml"


def load_config(config_path: Path | None = None) -> WorksetConfig:
    """Load workset configuration, returning defaults if no config file exists."""
    path = config_path or _DEFAULT_CONFIG

    if not path.is_file():
        return WorksetConfig(
            workset_root=Path.home() / "Projects" / "worksets",
            date_prefix=False,
            timezone=UTC,
            repos={},
        )

    try:
        with path.open("rb") as f:
            raw: dict[str, Any] = tomllib.load(f)
    except tomllib.TOMLDecodeError as exc:
        raise WorksetError(f"invalid repos.toml at {path}: {exc}") from exc

    ws = raw.get("workset", {})
    workset_root = (
        Path(str(ws.get("root", "~/Projects/worksets"))).expanduser().resolve()
    )
    date_prefix = bool(ws.get("date_prefix", False))
    timezone = _resolve_timezone(ws.get("timezone"))

    repos = {
        name: Path(str(p)).expanduser().resolve()
        for name, p in raw.get("repos", {}).items()
    }
    return WorksetConfig(
        workset_root=workset_root,
        date_prefix=date_prefix,
        timezone=timezone,
        repos=repos,
    )


def _resolve_timezone(value: Any) -> tzinfo:
    """Resolve an optional timezone config value."""
    if value is None:
        return UTC
    if not isinstance(value, str):
        raise WorksetError("config field 'timezone' must be a string")
    try:
        return ZoneInfo(value)
    except ZoneInfoNotFoundError as exc:
        raise WorksetError(f"unknown timezone {value!r}") from exc


def _require_git_repo(path: Path) -> None:
    """Raise WorksetError if path is not an existing git repository."""
    if not path.is_dir():
        raise WorksetError(f"canonical repo path does not exist: {path}")
    if not (path / ".git").exists():
        raise WorksetError(f"not a git repository: {path}")
