"""Shared pytest fixtures."""

from __future__ import annotations

import pytest

# pytest-asyncio: use the auto mode declared in pyproject.toml so plain
# `async def test_*` functions are picked up without per-test decorators.


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
