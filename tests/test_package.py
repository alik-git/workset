"""Basic smoke tests for workset."""

from __future__ import annotations

import workset


def test_import() -> None:
    """Workset can be imported."""
    assert workset is not None
