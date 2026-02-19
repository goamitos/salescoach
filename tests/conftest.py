from __future__ import annotations

import pytest


@pytest.fixture
def tmp_data(tmp_path):
    """Temporary data directory for test outputs."""
    d = tmp_path / "data"
    d.mkdir()
    return d
