import contextlib
import dataclasses
import enum
import logging
import orjson
import os
import psycopg
import psycopg.rows
import psycopg.types.json
import psycopg_pool
import typing
import uuid

logger = logging.getLogger()

DB_USER = os.getenv("DB_USER", "vtes-rulings")
DB_PWD = os.getenv("DB_PWD", "")
psycopg.types.json.set_json_dumps(orjson.dumps)
psycopg.types.json.set_json_loads(orjson.loads)


def reconnect_failed(_pool: psycopg_pool.AsyncConnectionPool):
    logger.error("Failed to reconnect to the PostgreSQL database")


#: await POOL.open() before using this module, and POOL.close() when finished
POOL = psycopg_pool.AsyncConnectionPool(
    f"postgresql://{DB_USER}:{DB_PWD}@localhost/vtes-rulings",
    open=False,
    max_size=10,
    reconnect_failed=reconnect_failed,
)


class UserCategory(enum.StrEnum):
    BASIC = "BASIC"
    RULEMONGER = "RULEMONGER"
    ADMIN = "ADMIN"


@dataclasses.dataclass
class User:
    uid: uuid.UUID
    vekn: str
    category: UserCategory = UserCategory.BASIC


async def init():
    async with POOL.connection() as conn:
        async with conn.cursor() as cursor:
            logger.debug("Initialising DB")
            await cursor.execute(
                "CREATE TABLE IF NOT EXISTS users("
                "uid UUID DEFAULT gen_random_uuid() PRIMARY KEY, "
                "vekn TEXT UNIQUE, "
                "category TEXT)"
            )
            await cursor.execute(
                "CREATE TABLE IF NOT EXISTS proposals("
                "uid TEXT PRIMARY KEY, "
                "usr UUID REFERENCES users(uid), "
                "data json)"
            )


async def reset():
    async with POOL.connection() as conn:
        async with conn.cursor() as cursor:
            logger.warning("Reset DB")
            await cursor.execute("DROP TABLE proposals")
            await cursor.execute("DROP TABLE users")


async def get_or_create_user(vekn: str) -> User:
    async with POOL.connection() as conn:
        async with conn.cursor(row_factory=psycopg.rows.class_row(User)) as cursor:
            ret = await cursor.execute(
                "SELECT * FROM users WHERE vekn=%s FOR UPDATE", [vekn]
            )
            ret = await ret.fetchone()
            if ret:
                return ret
            ret = await cursor.execute(
                "INSERT INTO users VALUES (DEFAULT, %s, %s) RETURNING *",
                [vekn, UserCategory.BASIC],
            )
            ret = await ret.fetchone()
            return ret


async def get_user(uid: uuid.UUID) -> User | None:
    async with POOL.connection() as conn:
        async with conn.cursor(row_factory=psycopg.rows.class_row(User)) as cursor:
            ret = await cursor.execute("SELECT * FROM users WHERE uid=%s", [uid])
            return await ret.fetchone()


# async def get_proposals() -> list[dict]:
#     """Call once at startup"""
#     async with POOL.connection() as conn:
#         async with conn.cursor() as cursor:
#             ret = await cursor.execute("SELECT data FROM proposals")
#             return [r[0] for r in ret]


async def all_proposal_ids() -> None:
    async with POOL.connection() as conn:
        async with conn.cursor() as cursor:
            ret = await cursor.execute("SELECT uid FROM proposals")
            return {r[0] for r in await ret.fetchall()}


async def insert_proposal(proposal: dict) -> None:
    async with POOL.connection() as conn:
        async with conn.cursor() as cursor:
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


async def get_proposal(proposal_uid: str):
    async with POOL.connection() as connection:
        async with connection.cursor() as cursor:
            ret = await (
                await cursor.execute(
                    "SELECT data FROM proposals WHERE uid=%s", [proposal_uid]
                )
            ).fetchone()
        return ret[0]


async def get_proposal_for_update(
    connection: psycopg.AsyncConnection, proposal_uid: str
):
    async with connection.cursor() as cursor:
        ret = await (
            await cursor.execute(
                "SELECT data FROM proposals WHERE uid=%s FOR UPDATE", [proposal_uid]
            )
        ).fetchone()
    return ret[0]
