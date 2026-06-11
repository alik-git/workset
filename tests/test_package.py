"""Basic smoke tests for workset."""

from __future__ import annotations

import workset


def test_import() -> None:
    """Workset can be imported and exports the public API."""
    assert workset.create_workset is not None
    assert workset.WorksetResult is not None
    assert workset.RepoResult is not None
    assert workset.WorksetError is not None
