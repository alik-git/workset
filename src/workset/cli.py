"""Command-line interface for workset."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

from workset.config import WorksetError
from workset.core import WorksetResult, create_workset

if TYPE_CHECKING:
    from collections.abc import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    """Run the workset command-line interface."""
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        return _main(args)
    except WorksetError as exc:
        print(f"workset: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130


def _main(args: list[str]) -> int:
    if not args or args[0] in {"-h", "--help"}:
        _print_help()
        return 0

    command = args[0]

    if command == "new":
        return _cmd_new(args[1:])

    print(f"workset: unknown command {command!r}", file=sys.stderr)
    _print_help()
    return 2


def _cmd_new(args: list[str]) -> int:
    """Handle ``workset new``."""
    if not args or args[0] in {"-h", "--help"}:
        _print_new_help()
        return 0

    slug = args[0]
    rest = args[1:]

    dest: Path | None = None
    no_env = False
    no_smoke = False
    repo_specs: list[str] = []

    i = 0
    while i < len(rest):
        arg = rest[i]
        if arg in {"--dest", "-d"}:
            if i + 1 >= len(rest):
                print("workset: --dest requires a path", file=sys.stderr)
                return 2
            dest = Path(rest[i + 1]).expanduser()
            i += 2
        elif arg == "--no-env":
            no_env = True
            i += 1
        elif arg == "--no-smoke":
            no_smoke = True
            i += 1
        elif arg.startswith("-"):
            print(f"workset: unknown option {arg!r}", file=sys.stderr)
            return 2
        else:
            repo_specs.append(arg)
            i += 1

    if not repo_specs:
        print("workset: at least one repo spec required", file=sys.stderr)
        _print_new_help()
        return 2

    result = create_workset(
        slug=slug,
        repo_specs=repo_specs,
        dest=dest,
        no_env=no_env,
        no_smoke=no_smoke,
    )
    _print_result(result)
    return 0 if result.ok else 1


def _print_result(result: WorksetResult) -> None:
    """Print a human-readable summary of the workset result."""
    print(f"\nworkset ready: {result.path}")
    for repo in result.repos:
        smoke = _smoke_symbol(repo.smoke_passed)
        env_label = (
            f"[{repo.env_backend}]" if repo.env_backend != "none" else "[no env]"
        )
        print(f"  {smoke} {repo.name}  {env_label}  {repo.branch}")
        if not repo.env_ok:
            print(f"    ! {repo.env_message}")


def _smoke_symbol(smoke_passed: bool | None) -> str:
    """Return a status symbol for the smoke test result."""
    if smoke_passed is True:
        return "✓"
    if smoke_passed is False:
        return "✗"
    return "~"


def _print_help() -> None:
    print(
        "usage: workset <command> [args]\n"
        "\nCommands:\n"
        "  new    Create a new workset\n"
        "\nRun 'workset new --help' for details.",
    )


def _print_new_help() -> None:
    print(
        "usage: workset new <slug> [--dest <path>] [--no-env] [--no-smoke]"
        " <repo>:<branch> ...\n"
        "\nArguments:\n"
        "  slug             Short identifier for this workset\n"
        "  repo:branch      Repo name (from config or path) and branch\n"
        "\nOptions:\n"
        "  --dest <path>    Override destination path\n"
        "  --no-env         Skip environment setup\n"
        "  --no-smoke       Skip smoke tests\n"
        "\nExamples:\n"
        "  workset new improve-viewer minerva_mujoco_viewer:feat/improve-viewer\n"
        "  workset new leansim2sim minerva_lab:feat/leansim2sim"
        " motion_data_processing:main\n"
        "  workset new quick-fix --dest /tmp/quick minerva_lab:main",
    )
