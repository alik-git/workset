"""Tests for shared path helpers."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from workset.paths import dated_dir, dated_path_parts

if TYPE_CHECKING:
    from pathlib import Path


def test_dated_path_parts_use_full_month_and_abbreviated_weekday() -> None:
    """Return YYYY/MM-month/DD-ddd path components."""
    value = datetime(2026, 6, 12, 14, 21, tzinfo=ZoneInfo("America/Toronto"))

    assert dated_path_parts(value) == ("2026", "06-june", "12-fri")


def test_dated_dir_joins_path_components(tmp_path: Path) -> None:
    """Build a dated directory under the given root."""
    value = datetime(2026, 6, 15, 1, 27, tzinfo=ZoneInfo("America/Detroit"))

    assert dated_dir(tmp_path, value) == tmp_path / "2026" / "06-june" / "15-mon"
