"""Tests for environment backend detection and smoke tests."""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

from workset.env import (
    detect_backend,
    infer_import_name,
    run_smoke_test,
    setup_env,
)

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_detect_backend_veneer(tmp_path: Path) -> None:
    """Detect veneer when veneer.toml is present."""
    (tmp_path / "veneer.toml").write_text("[python]\n", encoding="utf-8")
    assert detect_backend(tmp_path) == "veneer"


def test_detect_backend_uv(tmp_path: Path) -> None:
    """Detect uv when only pyproject.toml is present."""
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    assert detect_backend(tmp_path) == "uv"


def test_detect_backend_veneer_takes_priority(tmp_path: Path) -> None:
    """Veneer takes priority over uv when both files exist."""
    (tmp_path / "veneer.toml").write_text("[python]\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    assert detect_backend(tmp_path) == "veneer"


def test_detect_backend_none(tmp_path: Path) -> None:
    """Return none when no config files are present."""
    assert detect_backend(tmp_path) == "none"


def test_infer_import_name_from_veneer_editables(tmp_path: Path) -> None:
    """Infer import name from veneer.toml editables packages."""
    lines = (
        '[python]\nbase_conda_env = "x"\n'
        '[editables]\npackages = ["source/minerva_lab"]\n'
    )
    (tmp_path / "veneer.toml").write_text(lines, encoding="utf-8")
    (tmp_path / "source" / "minerva_lab").mkdir(parents=True)
    assert infer_import_name(tmp_path) == "minerva_lab"


def test_infer_import_name_from_src_dir(tmp_path: Path) -> None:
    """Infer import name from a single src/ package directory."""
    pkg = tmp_path / "src" / "mypackage"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    assert infer_import_name(tmp_path) == "mypackage"


def test_infer_import_name_skips_ambiguous_src(tmp_path: Path) -> None:
    """Return None when src/ has multiple packages (ambiguous)."""
    for name in ("pkg_a", "pkg_b"):
        d = tmp_path / "src" / name
        d.mkdir(parents=True)
        (d / "__init__.py").write_text("", encoding="utf-8")
    assert infer_import_name(tmp_path) is None


def test_infer_import_name_returns_none_when_unknown(tmp_path: Path) -> None:
    """Return None when no import name can be determined."""
    assert infer_import_name(tmp_path) is None


def test_setup_env_veneer_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Return (True, 'veneer ok') on successful veneer update-editables."""
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **_kw: subprocess.CompletedProcess(a[0], 0, stdout="", stderr=""),
    )
    ok, msg = setup_env(tmp_path, "veneer")
    assert ok is True
    assert "veneer ok" in msg


def test_setup_env_uv_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Return (True, 'uv ok') on successful uv sync."""
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **_kw: subprocess.CompletedProcess(a[0], 0, stdout="", stderr=""),
    )
    ok, msg = setup_env(tmp_path, "uv")
    assert ok is True
    assert "uv ok" in msg


def test_setup_env_none_skips(tmp_path: Path) -> None:
    """Return (True, skip message) for no-env backend."""
    ok, msg = setup_env(tmp_path, "none")
    assert ok is True
    assert "detected" in msg or "skip" in msg


def test_run_smoke_test_passes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Return True when import command exits 0."""
    pkg = tmp_path / "src" / "mypackage"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **_kw: subprocess.CompletedProcess(a[0], 0),
    )

    assert run_smoke_test(tmp_path, "uv") is True


def test_run_smoke_test_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Return False when import command exits nonzero."""
    pkg = tmp_path / "src" / "mypackage"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **_kw: subprocess.CompletedProcess(a[0], 1),
    )

    assert run_smoke_test(tmp_path, "uv") is False


def test_run_smoke_test_returns_none_when_name_unknown(tmp_path: Path) -> None:
    """Return None when import name cannot be inferred."""
    assert run_smoke_test(tmp_path, "uv") is None
