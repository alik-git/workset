"""Shared path helpers for Ali workflow tools."""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


def dated_path_parts(value: date | datetime) -> tuple[str, str, str]:
    """Return ``YYYY``, ``MM-month``, and ``DD-ddd`` path components."""
    day = value.date() if isinstance(value, datetime) else value
    return (
        str(day.year),
        day.strftime("%m-%B").lower(),
        day.strftime("%d-%a").lower(),
    )


def dated_dir(root: Path, value: date | datetime) -> Path:
    """Return ``root/YYYY/MM-month/DD-ddd`` for a date-like value."""
    year, month, day = dated_path_parts(value)
    return root / year / month / day
