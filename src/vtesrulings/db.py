import dataclasses
import datetime
import logging
import os
import uuid

import orjson
import psycopg
import psycopg.rows
import psycopg.types.json
import psycopg_pool

logger = logging.getLogger()

DB_USER = os.getenv("DB_USER", "vtes-rulings")
DB_PWD = os.getenv("DB_PWD", "")
DB_NAME = os.getenv("DB_NAME", "vtes-rulings")
# Prod passes a full DSN (unix-socket peer auth); dev/tests keep the DB_* localhost default.
CONNINFO = os.getenv("DATABASE_URL") or f"postgresql://{DB_USER}:{DB_PWD}@localhost/{DB_NAME}"
psycopg.types.json.set_json_dumps(orjson.dumps)
psycopg.types.json.set_json_loads(orjson.loads)


def reconnect_failed(_pool: psycopg_pool.AsyncConnectionPool):
    logger.error("Failed to reconnect to the PostgreSQL database")


#: await POOL.open() before using this module, and POOL.close() when finished
POOL = psycopg_pool.AsyncConnectionPool(
    CONNINFO,
    open=False,
    max_size=10,
    reconnect_failed=reconnect_failed,
)


@dataclasses.dataclass
class User:
    """Mirrors archon: `approver` and `vekn` are copies of what userinfo last said."""

    uid: uuid.UUID
    vekn: str
    archon_uid: str | None = None
    approver: bool = False
    refresh_token: str | None = None
    roles_checked_at: datetime.datetime | None = None


async def init():
    async with POOL.connection() as conn, conn.cursor() as cursor:
        logger.debug("Initialising DB")
        await cursor.execute(
            "CREATE TABLE IF NOT EXISTS users("
            "uid UUID DEFAULT gen_random_uuid() PRIMARY KEY, "
            "vekn TEXT UNIQUE, "
            "archon_uid TEXT UNIQUE, "
            "approver BOOLEAN NOT NULL DEFAULT FALSE, "
            "refresh_token TEXT, "
            "roles_checked_at TIMESTAMPTZ)"
        )
        # No migration tool: an existing table is brought up to that shape here, so every
        # statement must be idempotent. The old `category` is dropped rather than backfilled into
        # `approver` — a backfilled approver has no refresh token to re-check, so it would stay an
        # approver forever. Approvers log in again after the cutover, which they must anyway to
        # seed a refresh token.
        await cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS archon_uid TEXT UNIQUE")
        await cursor.execute(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS approver BOOLEAN NOT NULL DEFAULT FALSE"
        )
        await cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS refresh_token TEXT")
        await cursor.execute(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS roles_checked_at TIMESTAMPTZ"
        )
        await cursor.execute("ALTER TABLE users DROP COLUMN IF EXISTS category")
        # Same name the inline UNIQUE gets, so this is a no-op on a fresh table. It raises on a
        # legacy table that still holds duplicates, deliberately: they must be resolved before boot.
        await cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS users_vekn_key ON users (vekn)")
        await cursor.execute(
            "CREATE TABLE IF NOT EXISTS proposals("
            "uid TEXT PRIMARY KEY, "
            "usr UUID REFERENCES users(uid), "
            "data json)"
        )


def reset():
    with psycopg.connect(CONNINFO) as conn, conn.cursor() as cursor:
        logger.warning("Reset DB")
        cursor.execute("DROP TABLE proposals")
        cursor.execute("DROP TABLE users")


async def login_user(archon_uid: str, vekn: str, approver: bool, refresh_token: str | None) -> User:
    """Resolve an archon login: by archon uid, else adopt the legacy row holding that VEKN id.

    Legacy rows keyed on a vekn.net *username* rather than an id are not adopted — they get a
    fresh row and their in-flight proposals go with the old one. Hand-mapped before the cutover.

    `roles_checked_at` is stamped only when a refresh token comes with it: a row that has never
    been checked (a TESTING mint, a hand-written legacy row) must not read as one whose token
    archon later killed. See `api.get_current_user`.
    """
    checked = datetime.datetime.now(datetime.UTC) if refresh_token else None
    async with (
        POOL.connection() as conn,
        conn.cursor(row_factory=psycopg.rows.class_row(User)) as cursor,
    ):
        ret = await cursor.execute(
            "UPDATE users SET vekn=%s, approver=%s, refresh_token=%s, roles_checked_at=%s "
            "WHERE archon_uid=%s RETURNING *",
            [vekn, approver, refresh_token, checked, archon_uid],
        )
        user = await ret.fetchone()
        if user:
            return user
        ret = await cursor.execute(
            "UPDATE users SET archon_uid=%s, approver=%s, refresh_token=%s, roles_checked_at=%s "
            "WHERE archon_uid IS NULL AND vekn=%s RETURNING *",
            [archon_uid, approver, refresh_token, checked, vekn],
        )
        user = await ret.fetchone()
        if user:
            return user
        # ON CONFLICT rather than a plain INSERT: two first logins of the same account can race
        # here, and the loser must get the row, not a 500. A `vekn` already linked to another
        # archon account still raises — login_callback turns that into a message.
        ret = await cursor.execute(
            "INSERT INTO users (archon_uid, vekn, approver, refresh_token, roles_checked_at) "
            "VALUES (%s, %s, %s, %s, %s) ON CONFLICT (archon_uid) DO UPDATE SET "
            "vekn=EXCLUDED.vekn, approver=EXCLUDED.approver, "
            "refresh_token=EXCLUDED.refresh_token, roles_checked_at=EXCLUDED.roles_checked_at "
            "RETURNING *",
            [archon_uid, vekn, approver, refresh_token, checked],
        )
        user = await ret.fetchone()
        assert user is not None  # INSERT ... RETURNING * always yields a row
        return user


async def get_user(uid: uuid.UUID) -> User | None:
    async with (
        POOL.connection() as conn,
        conn.cursor(row_factory=psycopg.rows.class_row(User)) as cursor,
    ):
        ret = await cursor.execute("SELECT * FROM users WHERE uid=%s", [uid])
        return await ret.fetchone()


async def claim_roles_check(user: User) -> bool:
    """Stamp the row as checked *before* asking archon, and report whether we got the claim.

    Archon revokes the whole refresh-token chain when a rotated token is reused, so exactly one
    request may spend the stored token. Claiming with a conditional UPDATE rather than holding
    the row locked keeps a pool connection (of ten) out of an HTTP round-trip. The stamp lands
    either way, so a failed check retries in an hour rather than on the next request.
    """
    async with POOL.connection() as conn, conn.cursor() as cursor:
        ret = await cursor.execute(
            "UPDATE users SET roles_checked_at=now() "
            "WHERE uid=%s AND roles_checked_at IS NOT DISTINCT FROM %s",
            [user.uid, user.roles_checked_at],
        )
        return ret.rowcount > 0


async def set_user_roles(
    uid: uuid.UUID, vekn: str, approver: bool, refresh_token: str | None
) -> User | None:
    async with (
        POOL.connection() as conn,
        conn.cursor(row_factory=psycopg.rows.class_row(User)) as cursor,
    ):
        ret = await cursor.execute(
            "UPDATE users SET vekn=%s, approver=%s, refresh_token=%s, roles_checked_at=now() "
            "WHERE uid=%s RETURNING *",
            [vekn, approver, refresh_token, uid],
        )
        return await ret.fetchone()


async def all_proposal_ids() -> set[str]:
    async with POOL.connection() as conn, conn.cursor() as cursor:
        ret = await cursor.execute("SELECT uid FROM proposals")
        return {r[0] for r in await ret.fetchall()}


async def insert_proposal(proposal: dict) -> None:
    async with POOL.connection() as conn, conn.cursor() as cursor:
        await cursor.execute(
            "INSERT INTO proposals VALUES (%s, %s, %s) ",
            [proposal["uid"], proposal["usr"], psycopg.types.json.Json(proposal)],
        )


async def update_proposal(connection: psycopg.AsyncConnection, proposal: dict) -> None:
    """
    Use `async with proposal_connection(uid):`
    to properly lock the proposal for update before doIng anything
    """
    async with connection.cursor() as cursor:
        await cursor.execute(
            "UPDATE proposals SET data=%s WHERE uid=%s",
            [psycopg.types.json.Json(proposal), proposal["uid"]],
        )


async def delete_proposal(connection: psycopg.AsyncConnection, proposal: dict) -> None:
    """
    Use `async with proposal_connection(uid):`
    to properly lock the proposal for update before doIng anything
    """
    async with connection.cursor() as cursor:
        await cursor.execute(
            "DELETE FROM proposals WHERE uid=%s",
            [proposal["uid"]],
        )


async def get_proposal(proposal_uid: str):
    async with POOL.connection() as connection:
        async with connection.cursor() as cursor:
            ret = await (
                await cursor.execute("SELECT data FROM proposals WHERE uid=%s", [proposal_uid])
            ).fetchone()
        if ret:
            return ret[0]
        return None


async def get_user_proposals(user_id: uuid.UUID, limit: int = 100):
    async with POOL.connection() as connection:
        async with connection.cursor() as cursor:
            ret = await (
                await cursor.execute(
                    "SELECT data FROM proposals WHERE usr=%s LIMIT %s", [user_id, limit]
                )
            ).fetchall()
        if ret:
            return [r[0] for r in ret]
        return []


async def get_submitted_proposals(limit: int = 100):
    """Proposals already sent to Discord (channel_id set) — the approver's queue."""
    async with POOL.connection() as connection:
        async with connection.cursor() as cursor:
            ret = await (
                await cursor.execute(
                    "SELECT data FROM proposals WHERE data->>'channel_id' <> '' LIMIT %s", [limit]
                )
            ).fetchall()
        return [r[0] for r in ret] if ret else []


async def get_proposal_for_update(connection: psycopg.AsyncConnection, proposal_uid: str):
    async with connection.cursor() as cursor:
        ret = await (
            await cursor.execute(
                "SELECT data FROM proposals WHERE uid=%s FOR UPDATE", [proposal_uid]
            )
        ).fetchone()
    return ret[0] if ret else None
