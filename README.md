# workset

Create and initialize isolated git worktree worksets in one command.

A workset is a directory containing one or more git worktrees for related
repos, each on their own branch, with submodules initialized and the Python
environment ready to go. `workset` automates the setup so you can go from
"I have a task" to a working environment without the manual back-and-forth.

## Installation

```bash
uv tool install workset
```

Or install from source:

```bash
uv tool install --editable path/to/workset
```

## Usage

```bash
workset --help
```

## Development

```bash
uv sync --extra dev
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pytest
```

## Publishing

Releases are published to PyPI automatically when a GitHub Release is created.
