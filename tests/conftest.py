import pytest_asyncio
import quart.testing.app

import vtesrulings


@pytest_asyncio.fixture(name="app", scope="session")
async def _app():
    app = vtesrulings.app
    quart.testing.app.DEFAULT_TIMEOUT = 15
    async with app.test_app() as test_app:
        yield test_app
