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

Or with pip:

```bash
python -m pip install workset
```

Or install from source:

```bash
uv tool install --editable path/to/workset
```

## Usage

```bash
workset --help
```

## Configure repos

`workset` resolves specs like `api:feat/refactor` from
`~/.config/workset/repos.toml`. Keep these repo paths pointed at stable
canonical checkouts, not temporary worksets.

```toml
[workset]
root = "~/worksets"
date_prefix = true
timezone = "America/Los_Angeles"

[repos]
api = "~/repos/api"
web = "~/repos/web"
```

With `date_prefix = true`, worksets are created under a dated layout:

```text
<workset-root>/YYYY/MM-month/DD-ddd/<slug>/
```

For example:

```text
~/worksets/2026/06-june/15-mon/my-task/
```

When `timezone` is omitted, `workset` uses UTC for date-prefixed paths.

## First successful workset

Start with one repo alias and one new branch:

```bash
git clone git@github.com:your-org/api.git ~/repos/api
workset new api-refactor api:feat/refactor
```

That creates a new workset directory, adds a git worktree for `api`, initializes
submodules, and prepares the repo environment when it recognizes the tooling.

For a task that spans multiple repos:

```bash
git clone git@github.com:your-org/web.git ~/repos/web
workset new checkout-flow api:feat/checkout-flow web:main
```

You can also pass a repo path directly when you do not want to configure an
alias yet:

```bash
workset new quick-fix ~/repos/api:main
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
