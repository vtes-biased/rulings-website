import asgi_lifespan
import httpx
import pytest_asyncio

import vtesrulings


@pytest_asyncio.fixture(name="app", scope="session")
async def _app():
    """Run the ASGI lifespan once per session (clones the repo + loads cards — expensive)."""
    async with asgi_lifespan.LifespanManager(vtesrulings.app, startup_timeout=120) as manager:
        yield manager.app


@pytest_asyncio.fixture(name="client")
async def _client(app):
    """A fresh client (fresh cookie jar) per test, sharing the session-wide app."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
