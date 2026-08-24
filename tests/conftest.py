"""Fixtures shared by every suite.

The read caches added in ``backend/core/cache.py`` live at module scope, which is right for
a server process and wrong for a test process: without this, one test's cached companies
page or facets answer is served to the next test, after the tables it was built from have
been truncated.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from backend.core.cache import clear_all


@pytest.fixture(autouse=True)
def _empty_read_caches() -> Iterator[None]:
    clear_all()
    yield
    clear_all()
