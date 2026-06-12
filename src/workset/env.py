"""Environment backend detection, setup, and smoke testing."""

from __future__ import annotations

import subprocess
import tomllib
from pathlib import Path


def detect_backend(worktree_path: Path) -> str:
    """Detect the Python environment backend for a worktree.

    Returns ``"veneer"``, ``"uv"``, or ``"none"``.
    Veneer takes priority if ``veneer.toml`` is present.
    If veneer.toml uses ``extends`` (pointer style), still returns ``"veneer"``
    but setup may fail if the stack file does not exist yet.
    """
    if (worktree_path / "veneer.toml").is_file():
        return "veneer"
    if (worktree_path / "pyproject.toml").is_file():
        return "uv"
    return "none"


def setup_env(worktree_path: Path, backend: str) -> tuple[bool, str]:
    """Run environment setup for a worktree.

    Returns (success, message).
    """
    if backend == "veneer":
        return _setup_veneer(worktree_path)
    if backend == "uv":
        return _setup_uv(worktree_path)
    return True, "no env backend detected"


def cross_install_editables(
    worktree_path: Path,
    extra_paths: list[Path],
) -> tuple[bool, str]:
    """Install extra editable packages directly into a veneer-managed venv.

    Calls the venv's Python directly (not through veneer) to bypass veneer's
    protection against ad-hoc editable installs. Uses --no-deps so only the
    source path is added, never pulling in conflicting transitive deps.
    """
    if not extra_paths:
        return True, "no cross-installs needed"

    venv_python = _resolve_venv_python(worktree_path)
    if venv_python is None:
        return False, "could not locate venv python for cross-install"

    args = [str(venv_python), "-m", "pip", "install", "--no-deps"]
    for p in extra_paths:
        args.extend(["-e", str(p)])

    result = subprocess.run(  # noqa: S603
        args,
        cwd=worktree_path,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return False, f"cross-install failed: {result.stderr.strip()}"
    return True, f"cross-installed {len(extra_paths)} package(s)"


def _resolve_venv_python(worktree_path: Path) -> Path | None:
    """Return the venv python path from veneer.toml, or None if not found."""
    veneer_toml = worktree_path / "veneer.toml"
    if not veneer_toml.is_file():
        return None
    try:
        with veneer_toml.open("rb") as f:
            raw = tomllib.load(f)
    except (tomllib.TOMLDecodeError, OSError):
        return None
    venv_str = raw.get("python", {}).get("venv", ".venv")
    venv = (worktree_path / Path(venv_str).expanduser()).resolve()
    python = venv / "bin" / "python"
    return python if python.is_file() else None


def collect_editable_paths(worktree_path: Path, backend: str = "veneer") -> list[Path]:
    """Return the editable package paths for a repo.

    For veneer repos: paths from veneer.toml editables.packages.
    For uv repos: the worktree root itself (install the package).
    Paths resolved relative to the worktree root.
    """
    if backend == "uv":
        return [worktree_path.resolve()]

    veneer_toml = worktree_path / "veneer.toml"
    if not veneer_toml.is_file():
        return []
    try:
        with veneer_toml.open("rb") as f:
            raw = tomllib.load(f)
    except (tomllib.TOMLDecodeError, OSError):
        return []
    packages = raw.get("editables", {}).get("packages", [])
    return [
        (worktree_path / Path(p).expanduser()).resolve()
        for p in packages
        if isinstance(p, str) and p.strip()
    ]


def _setup_veneer(worktree_path: Path) -> tuple[bool, str]:
    """Run ``veneer update-editables`` in the worktree."""
    result = subprocess.run(
        ["veneer", "update-editables"],  # noqa: S607
        cwd=worktree_path,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return False, f"veneer update-editables failed: {result.stderr.strip()}"
    return True, "veneer ok"


def _setup_uv(worktree_path: Path) -> tuple[bool, str]:
    """Run ``uv sync`` in the worktree."""
    result = subprocess.run(
        ["uv", "sync"],  # noqa: S607
        cwd=worktree_path,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return False, f"uv sync failed: {result.stderr.strip()}"
    return True, "uv ok"


def infer_import_name(worktree_path: Path) -> str | None:
    """Infer the importable package name for a worktree.

    Uses the first editable package from ``veneer.toml`` if present,
    then looks for a single directory under ``src/`` or ``source/``.
    Returns None if the import name cannot be determined.
    """
    veneer_toml = worktree_path / "veneer.toml"
    if veneer_toml.is_file():
        name = _import_name_from_veneer_toml(veneer_toml, worktree_path)
        if name:
            return name

    for src_dir in ("src", "source"):
        candidate = worktree_path / src_dir
        if candidate.is_dir():
            name = _single_package_dir(candidate)
            if name:
                return name

    return None


def _import_name_from_veneer_toml(
    veneer_toml: Path,
    worktree_path: Path,
) -> str | None:
    """Extract import name from the first editables.packages entry."""
    try:
        with veneer_toml.open("rb") as f:
            raw = tomllib.load(f)
    except (tomllib.TOMLDecodeError, OSError):
        return None

    packages = raw.get("editables", {}).get("packages", [])
    if not packages:
        return None

    first = packages[0]
    resolved = (worktree_path / Path(first).expanduser()).resolve()
    return resolved.name


def _single_package_dir(src_dir: Path) -> str | None:
    """Return the name of the single Python package directory under src_dir."""
    candidates = [
        d
        for d in src_dir.iterdir()
        if d.is_dir()
        and not d.name.startswith(".")
        and not d.name.endswith(".dist-info")
        and not d.name.endswith(".egg-info")
        and (d / "__init__.py").is_file()
    ]
    if len(candidates) == 1:
        return candidates[0].name
    return None


def run_smoke_test(worktree_path: Path, backend: str) -> bool | None:
    """Try to import the main package to verify the environment works.

    Returns True on success, False on failure, None if import name unknown.
    Never raises — smoke test failures are advisory, not fatal.
    """
    name = infer_import_name(worktree_path)
    if name is None:
        return None

    if backend == "veneer":
        cmd = ["veneer", "python", "-c", f"import {name}"]
    elif backend == "uv":
        cmd = ["uv", "run", "python", "-c", f"import {name}"]
    else:
        return None

    result = subprocess.run(  # noqa: S603
        cmd,
        cwd=worktree_path,
        capture_output=True,
        check=False,
    )
    return result.returncode == 0
