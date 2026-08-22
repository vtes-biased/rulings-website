"""Archon OAuth2 client: authorization code + PKCE, then userinfo.

Archon is the authority on who a user is (its uid), whether they are a member (a `vekn_id`)
and what they may do (`roles`). We ask once at login and never hold their credentials.
"""

import base64
import hashlib
import logging
import os
import urllib.parse

import aiohttp

logger = logging.getLogger()
ARCHON_URL = os.getenv("ARCHON_URL", "https://archon.krcg.org").rstrip("/")
CLIENT_ID = os.getenv("ARCHON_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("ARCHON_CLIENT_SECRET", "")
SITE_URL_BASE = os.getenv("SITE_URL_BASE", "http://127.0.0.1:5000").rstrip("/")
#: Archon matches this exactly — no prefix match — so it must be registered verbatim.
REDIRECT_URI = f"{SITE_URL_BASE}/login/callback"
SCOPE = "profile:read"


class Error(Exception):
    """Anything that stops us getting an answer: a refusal, an outage, a proxy's HTML error page."""


def authorization_url(state: str, verifier: str) -> str:
    """Aimed at archon's *frontend* consent page, not the API.

    That page hands its query string to `GET /oauth/authorize` verbatim, and the endpoint 400s
    without `response_type` and `code_challenge_method` — so they belong here, not on a call
    of our own. Logged out, the page bounces through archon's own login and comes back.
    """
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPE,
        "state": state,
        "code_challenge": base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii"),
        "code_challenge_method": "S256",
    }
    return f"{ARCHON_URL}/consent?{urllib.parse.urlencode(params)}"


async def exchange_code(code: str, verifier: str) -> dict:
    """Archon's /oauth/token takes a JSON body, not RFC 6749 form encoding."""
    return await _request(
        "post",
        f"{ARCHON_URL}/oauth/token",
        json={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "code_verifier": verifier,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        },
    )


async def userinfo(access_token: str) -> dict:
    """`{sub, roles, vekn_id, capabilities}` — no name, no email: profile:read sees nothing else."""
    return await _request(
        "get",
        f"{ARCHON_URL}/oauth/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
    )


async def _request(method: str, url: str, **kwargs) -> dict:
    try:
        async with (
            aiohttp.ClientSession() as session,
            session.request(method, url, **kwargs) as response,
        ):
            # content_type=None: a proxy erroring in HTML must land here, not as a ContentTypeError.
            data = await response.json(content_type=None)
            if response.status != 200:
                detail = data.get("detail") if isinstance(data, dict) else None
                raise Error(f"{url}: {detail or response.status}")
            return data
    except (aiohttp.ClientError, ValueError) as exc:  # unreachable, or an unparseable body
        raise Error(f"{url}: {exc}") from exc
