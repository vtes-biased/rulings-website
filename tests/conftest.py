import os
import pathlib
import shutil

# Force an isolated DB name *before* importing the app: the session fixture drops and
# recreates this database, so it must never resolve to a developer's real `vtes-rulings`.
os.environ.setdefault("TESTING", "1")
os.environ["DB_NAME"] = "vtes-rulings-test"
# DATABASE_URL (the prod DSN var) would short-circuit DB_NAME in db.CONNINFO and route the
# pool — incl. the truncating teardown — at a real DB while the -test guard still passes.
os.environ.pop("DATABASE_URL", None)

import aiohttp.web
import asgi_lifespan
import git
import httpx
import psycopg
import pytest
import pytest_asyncio

import vtesrulings
from vtesrulings import archon, db, discord, repository

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
async def _client(app, archon, discord_hook):
    """A fresh client (fresh cookie jar) per test, sharing the session-wide app. Truncates the DB
    on teardown so a test's users/proposals never leak into the next, and takes the two fake
    services so no test can reach the real archon or Discord, named or not."""
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            yield client
    finally:
        async with db.POOL.connection() as conn:
            await conn.execute("TRUNCATE proposals, users")


class FakeArchon:
    """Scriptable archon. Tests set `tokens` / `info`, or a non-200 status to refuse or fail with,
    and read back the credentials the app actually spent."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.spent: list[str] = []  # every code / refresh token the app sent to /oauth/token
        self.access: list[str] = []  # every access token it presented to /oauth/userinfo
        self.tokens = {"access_token": "access-1", "refresh_token": "refresh-1"}
        self.info = {"sub": "archon-uid", "vekn_id": "9999999", "roles": ["IC"]}
        self.token_status = 200  # 400 is a refusal (dead chain), anything else an outage
        self.userinfo_status = 200

    async def token(self, request):
        body = await request.json()
        self.spent.append(body.get("refresh_token") or body.get("code"))
        if self.token_status != 200:
            return aiohttp.web.json_response({"detail": "no"}, status=self.token_status)
        return aiohttp.web.json_response(self.tokens)

    async def userinfo(self, request):
        self.access.append(request.headers.get("Authorization", "").removeprefix("Bearer "))
        if self.userinfo_status != 200:
            return aiohttp.web.json_response({"detail": "no"}, status=self.userinfo_status)
        return aiohttp.web.json_response(self.info)


class FakeDiscord:
    """The webhook endpoint, recording what was posted and answering as Discord does."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.posts: list[dict] = []

    async def execute(self, request):
        self.posts.append({"query": dict(request.query), "payload": await request.json()})
        return aiohttp.web.json_response({"id": "1", "channel_id": "42"})


async def _serve(routes) -> tuple[str, aiohttp.web.AppRunner]:
    """An aiohttp app on an ephemeral local port — a real server, so the client code under test
    runs its own transport and status handling rather than being substituted away."""
    web_app = aiohttp.web.Application()
    web_app.add_routes(routes)
    runner = aiohttp.web.AppRunner(web_app)
    await runner.setup()
    await aiohttp.web.TCPSite(runner, "127.0.0.1", 0).start()
    return f"http://127.0.0.1:{runner.addresses[0][1]}", runner


@pytest_asyncio.fixture(name="_archon_server", scope="session")
async def _archon_server():
    fake = FakeArchon()
    url, runner = await _serve(
        [
            aiohttp.web.post("/oauth/token", fake.token),
            aiohttp.web.get("/oauth/userinfo", fake.userinfo),
        ]
    )
    original = archon.ARCHON_URL
    archon.ARCHON_URL = url
    yield fake
    archon.ARCHON_URL = original
    await runner.cleanup()


@pytest_asyncio.fixture(name="_discord_server", scope="session")
async def _discord_server():
    fake = FakeDiscord()
    url, runner = await _serve([aiohttp.web.post("/webhook", fake.execute)])
    original = discord.DISCORD_WEBHOOK
    discord.DISCORD_WEBHOOK = f"{url}/webhook"
    yield fake
    discord.DISCORD_WEBHOOK = original
    await runner.cleanup()


@pytest.fixture(name="archon")
def _archon(_archon_server):
    _archon_server.reset()
    return _archon_server


@pytest.fixture(name="discord_hook")
def _discord_hook(_discord_server):
    _discord_server.reset()
    return _discord_server
