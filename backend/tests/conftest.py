"""Pytest configuration and fixtures."""

import pytest_asyncio
from app.database import engine


@pytest_asyncio.fixture(autouse=True)
async def cleanup_db_connections():
    """Ensure database engine connections are disposed between tests."""
    yield
    await engine.dispose()

