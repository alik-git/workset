"""Workset — create and initialize isolated git worktree worksets."""

from __future__ import annotations

from workset.config import WorksetError
from workset.core import RepoResult, WorksetResult, create_workset

__all__ = ["WorksetError", "RepoResult", "WorksetResult", "create_workset"]

__version__ = "0.1.1"
