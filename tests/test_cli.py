"""Tests for the workset command-line interface."""

from __future__ import annotations

from typing import TYPE_CHECKING

from workset import cli as cli_module
from workset.core import WorksetResult

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_cmd_new_fetches_latest_by_default(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Pass fetch_latest=True unless the user opts out."""
    calls: list[dict[str, object]] = []

    def fake_create_workset(**kwargs: object) -> WorksetResult:
        calls.append(kwargs)
        return WorksetResult(path=tmp_path, repos=())

    monkeypatch.setattr(cli_module, "create_workset", fake_create_workset)

    exit_code = cli_module._cmd_new(["task", "--no-env", "repo:feat/task"])

    assert exit_code == 0
    assert calls[0]["fetch_latest"] is True


def test_cmd_new_supports_no_fetch_latest(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Pass fetch_latest=False for explicit local/offline workset creation."""
    calls: list[dict[str, object]] = []

    def fake_create_workset(**kwargs: object) -> WorksetResult:
        calls.append(kwargs)
        return WorksetResult(path=tmp_path, repos=())

    monkeypatch.setattr(cli_module, "create_workset", fake_create_workset)

    exit_code = cli_module._cmd_new(
        ["task", "--no-env", "--no-fetch-latest", "repo:feat/task"]
    )

    assert exit_code == 0
    assert calls[0]["fetch_latest"] is False
