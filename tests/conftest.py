import quart
import pytest_asyncio
import typing
import quart.testing.app
import quart.typing

import vtesrulings
import vtesrulings.db


@pytest_asyncio.fixture(name="app", scope="session")
async def _app() -> typing.AsyncGenerator[quart.typing.TestClientProtocol, None]:
    app = vtesrulings.app
    quart.testing.app.DEFAULT_TIMEOUT = 15
    async with app.test_app() as test_app:
        # async with app.app_context():
        #     quart.g.user = vtesrulings.db.User(
        #         uid=uuid.uuid4(),
        #         vekn="test_user",
        #         category=vtesrulings.db.UserCategory.ADMIN,
        #     )
        yield test_app
