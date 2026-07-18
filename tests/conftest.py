import os
import pathlib
import shutil

# Force an isolated DB name *before* importing the app: the session fixture drops and
# recreates this database, so it must never resolve to a developer's real `vtes-rulings`.
os.environ.setdefault("TESTING", "1")
os.environ["DB_NAME"] = "vtes-rulings-test"

import asgi_lifespan
import git
import httpx
import psycopg
import pytest
import pytest_asyncio

import vtesrulings
from vtesrulings import db, repository

FIXTURES = pathlib.Path(__file__).parent / "fixtures" / "rulings"


@pytest.fixture(name="_test_database", scope="session")
def _test_database():
    """A throwaway Postgres database for the session, dropped afterwards — keeps tests off the
    developer's real DB and guarantees no users/proposals survive between runs."""
    # Belt-and-braces against a future edit weakening the line-8 hard-set: never drop a real DB.
    assert db.DB_NAME.endswith("-test"), db.DB_NAME
    maintenance = f"postgresql://{db.DB_USER}:{db.DB_PWD}@localhost/postgres"
    # psycopg types the query as LiteralString to deter injection; DB_NAME is asserted -test above.
    with psycopg.connect(maintenance, autocommit=True) as conn:
        conn.execute(f'DROP DATABASE IF EXISTS "{db.DB_NAME}" WITH (FORCE)')  # ty: ignore[no-matching-overload]
        conn.execute(f'CREATE DATABASE "{db.DB_NAME}"')  # ty: ignore[no-matching-overload]
    yield
    with psycopg.connect(maintenance, autocommit=True) as conn:
        conn.execute(f'DROP DATABASE IF EXISTS "{db.DB_NAME}" WITH (FORCE)')  # ty: ignore[no-matching-overload]


@pytest.fixture(name="rulings_remote", scope="session")
def _rulings_remote(tmp_path_factory):
    """Serve the vendored rulings snapshot as a local bare git remote so the suite is hermetic —
    no SSH, no live clone, no drift."""
    work = tmp_path_factory.mktemp("rulings-work")
    (work / repository.RULINGS_FILES_PATH).mkdir(parents=True)
    subpath = pathlib.PurePosixPath(repository.RULINGS_FILES_PATH)
    tracked = [str(subpath / n) for n in repository.RULINGS_FILES]
    for name in repository.RULINGS_FILES:
        shutil.copy(FIXTURES / name, work / repository.RULINGS_FILES_PATH / name)
    repo = git.Repo.init(work)
    repo.index.add(tracked)
    author = git.Actor("Test Harness", "test@example.invalid")
    repo.index.commit("Vendored rulings snapshot", author=author, committer=author)
    bare = tmp_path_factory.mktemp("rulings-remote")
    git.Repo.clone_from(str(work), str(bare), bare=True)
    original = repository.RULINGS_GIT
    repository.RULINGS_GIT = str(bare)
    yield str(bare)
    repository.RULINGS_GIT = original


@pytest_asyncio.fixture(name="app", scope="session")
async def _app(_test_database, rulings_remote):
    """Run the ASGI lifespan once per session (clones the fixture repo + loads cards — expensive)."""
    async with asgi_lifespan.LifespanManager(vtesrulings.app, startup_timeout=120) as manager:
        yield manager.app


@pytest_asyncio.fixture(name="client")
async def _client(app):
    """A fresh client (fresh cookie jar) per test, sharing the session-wide app. Truncates the DB
    on teardown so a test's users/proposals never leak into the next."""
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            yield client
    finally:
        async with db.POOL.connection() as conn:
            await conn.execute("TRUNCATE proposals, users")
