"""Tests for workset config loading and spec resolution."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from workset import config as config_module
from workset.config import WorksetConfig, WorksetError, load_config


def make_git_repo(path: Path) -> Path:
    """Create a minimal fake git repo for tests."""
    path.mkdir(parents=True, exist_ok=True)
    (path / ".git").mkdir()
    return path


def make_config(
    tmp_path: Path,
    *,
    repos: dict[str, Path] | None = None,
    date_prefix: bool = False,
    timezone: object = UTC,
) -> WorksetConfig:
    """Build a test config with repos pointing at tmp_path subdirs."""
    return WorksetConfig(
        workset_root=tmp_path / "worksets",
        date_prefix=date_prefix,
        timezone=timezone,
        repos=repos or {},
    )


def test_load_config_returns_defaults_when_missing(tmp_path: Path) -> None:
    """Return sensible defaults when no config file exists."""
    cfg = load_config(tmp_path / "nonexistent.toml")
    assert cfg.workset_root == Path.home() / "Projects" / "worksets"
    assert cfg.date_prefix is False
    assert cfg.timezone is UTC
    assert cfg.repos == {}


def test_load_config_parses_repos_and_root(tmp_path: Path) -> None:
    """Load repos and workset root from a valid toml file."""
    config_file = tmp_path / "repos.toml"
    repo_dir = make_git_repo(tmp_path / "my_repo")
    config_file.write_text(
        f"""
[workset]
root = "{tmp_path / "worksets"}"
date_prefix = true
timezone = "America/Los_Angeles"

[repos]
my_repo = "{repo_dir}"
""",
        encoding="utf-8",
    )

    cfg = load_config(config_file)

    assert cfg.workset_root == tmp_path / "worksets"
    assert cfg.date_prefix is True
    assert cfg.timezone == ZoneInfo("America/Los_Angeles")
    assert cfg.repos["my_repo"] == repo_dir


def test_load_config_raises_on_unknown_timezone(tmp_path: Path) -> None:
    """Fail clearly when timezone is not a known zoneinfo name."""
    config_file = tmp_path / "repos.toml"
    config_file.write_text(
        """
[workset]
timezone = "Mars/Olympus_Mons"
""",
        encoding="utf-8",
    )
    with pytest.raises(WorksetError, match="unknown timezone"):
        load_config(config_file)


def test_load_config_raises_on_non_string_timezone(tmp_path: Path) -> None:
    """Fail clearly when timezone has the wrong TOML type."""
    config_file = tmp_path / "repos.toml"
    config_file.write_text(
        """
[workset]
timezone = 123
""",
        encoding="utf-8",
    )
    with pytest.raises(WorksetError, match="timezone"):
        load_config(config_file)


def test_load_config_raises_on_bad_toml(tmp_path: Path) -> None:
    """Fail clearly on malformed TOML."""
    config_file = tmp_path / "repos.toml"
    config_file.write_text("not valid toml ][", encoding="utf-8")
    with pytest.raises(WorksetError, match="invalid repos.toml"):
        load_config(config_file)


def test_resolve_spec_named_repo(tmp_path: Path) -> None:
    """Resolve a name:branch spec via the repos config."""
    repo = make_git_repo(tmp_path / "my_repo")
    cfg = make_config(tmp_path, repos={"my_repo": repo})

    spec = cfg.resolve_spec("my_repo:feat/x")

    assert spec.canonical == repo
    assert spec.branch == "feat/x"
    assert spec.name == "my_repo"


def test_resolve_spec_absolute_path(tmp_path: Path) -> None:
    """Resolve an absolute path:branch spec."""
    repo = make_git_repo(tmp_path / "my_repo")
    cfg = make_config(tmp_path)

    spec = cfg.resolve_spec(f"{repo}:main")

    assert spec.canonical == repo
    assert spec.branch == "main"
    assert spec.name == "my_repo"


def test_resolve_spec_raises_on_missing_name(tmp_path: Path) -> None:
    """Fail clearly when a named repo is not in config."""
    cfg = make_config(tmp_path)
    with pytest.raises(WorksetError, match="not found"):
        cfg.resolve_spec("unknown_repo:main")


def test_resolve_spec_raises_on_missing_colon(tmp_path: Path) -> None:
    """Fail clearly on malformed spec."""
    cfg = make_config(tmp_path)
    with pytest.raises(WorksetError, match="expected <name>:<branch>"):
        cfg.resolve_spec("no_colon_here")


def test_resolve_spec_raises_on_empty_branch(tmp_path: Path) -> None:
    """Fail on an empty branch name."""
    repo = make_git_repo(tmp_path / "my_repo")
    cfg = make_config(tmp_path, repos={"my_repo": repo})
    with pytest.raises(WorksetError, match="branch cannot be empty"):
        cfg.resolve_spec("my_repo:")


def test_resolve_spec_raises_on_nonexistent_path(tmp_path: Path) -> None:
    """Fail when the absolute path does not exist."""
    cfg = make_config(tmp_path)
    with pytest.raises(WorksetError, match="does not exist"):
        cfg.resolve_spec(f"{tmp_path / 'nowhere'}:main")


def test_resolve_spec_raises_on_non_git_dir(tmp_path: Path) -> None:
    """Fail when the path exists but is not a git repo."""
    plain_dir = tmp_path / "not_git"
    plain_dir.mkdir()
    cfg = make_config(tmp_path)
    with pytest.raises(WorksetError, match="not a git repository"):
        cfg.resolve_spec(f"{plain_dir}:main")


def test_resolve_dest_no_date_prefix(tmp_path: Path) -> None:
    """Use root/slug when date_prefix is off."""
    cfg = make_config(tmp_path, date_prefix=False)
    dest = cfg.resolve_dest("my-task")
    assert dest == tmp_path / "worksets" / "my-task"


def test_resolve_dest_with_override(tmp_path: Path) -> None:
    """Honor explicit dest override."""
    cfg = make_config(tmp_path)
    override = tmp_path / "custom"
    assert cfg.resolve_dest("slug", override) == override


def test_resolve_dest_date_prefix_has_human_readable_format(tmp_path: Path) -> None:
    """Date-prefixed path uses YYYY/MM-month/DD-ddd format."""
    cfg = make_config(tmp_path, date_prefix=True)
    dest = cfg.resolve_dest("my-task")
    parts = dest.parts
    slug_idx = parts.index("my-task")
    year_part, month_part, day_part = parts[slug_idx - 3 : slug_idx]
    assert len(year_part) == 4
    assert "-" in month_part  # e.g. "06-june"
    assert "-" in day_part  # e.g. "14-sun"
    assert month_part[2] == "-"
    assert day_part[2] == "-"
    assert len(day_part) == len("14-sun")


def test_resolve_dest_date_prefix_uses_config_timezone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Date-prefixed path uses the configured local date, not the UTC date."""

    class FixedDatetime:
        @classmethod
        def now(cls, tz: object = None) -> object:
            assert tz is UTC
            return datetime(2026, 6, 15, 6, 30, tzinfo=UTC)

    monkeypatch.setattr(config_module, "datetime", FixedDatetime)
    cfg = make_config(
        tmp_path,
        date_prefix=True,
        timezone=ZoneInfo("America/Los_Angeles"),
    )

    dest = cfg.resolve_dest("my-task")

    assert dest == tmp_path / "worksets" / "2026" / "06-june" / "14-sun" / "my-task"
