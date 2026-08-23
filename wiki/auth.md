# Login, users and approvers

No VEKN password ever reaches this app. Login is OAuth2 authorization-code + PKCE against **archon**
(`archon.py`), which owns identity, the VEKN id and roles.

## The flow

1. `GET /login` — mint a `state` and a PKCE verifier into the session, 302 to
   `<ARCHON_URL>/consent?response_type=code&client_id=…&redirect_uri=…&scope=profile:read&state=…&code_challenge=…&code_challenge_method=S256`.
2. `GET /login/callback` — check `state`, `POST /oauth/token` (**JSON body**, archon's deliberate
   divergence from RFC 6749 form encoding), `GET /oauth/userinfo` for
   `{sub, roles, vekn_id, capabilities}`, resolve the user, store the refresh token, set
   `session["user_id"]`.
3. The access token is opaque to us: never decoded, never stored.

**The entry point is archon's frontend `/consent` page, not its API.** That page forwards its whole
query string verbatim to `GET /oauth/authorize`, so our redirect must already carry `response_type`
and `code_challenge_method` — `/oauth/authorize` 400s without them.

Archon gives an access token good for 1h and a refresh token good for 30d, with **refresh rotation
and chain revocation**. `redirect_uri` matching is exact, no prefix match. `profile:read` is
restricted to `/oauth/*`, so userinfo is all that token can read — no name, no email, which is fine:
the site displays only the VEKN id.

## The user row

`users`: `uid`, `vekn`, `archon_uid` (unique), `approver`, `refresh_token`, `roles_checked_at`.
Keyed on `archon_uid`; `login_user` is a single upsert — match `archon_uid`, else INSERT ON CONFLICT.
`vekn` and `approver` are copies of what userinfo last said, rewritten on every login.

- **A user with no `vekn_id` is refused** at login: "claim a VEKN ID on archon first".
- **`IC` or `Rulemonger` in `roles` → `approver`** — the single privilege left. It gates approval and
  seeing other people's proposals. We match role strings rather than an archon capability: none of
  archon's 28 capabilities is rulings-shaped, and `roles` is already archon's external contract
  (Discord Linked Roles consumes it). Adding an `approve_ruling` capability to archon later would
  touch this one predicate.
- **`vekn` is UNIQUE**, mirroring archon's own unique index on `vekn_id`. Since every row comes from
  archon and a VEKN id is never reassigned, a collision is unreachable — no login path guards against
  one, and a loud 500 is the failure we would want if archon's invariant ever broke.

`db.init()` is the only migration path. Every statement in it must be idempotent — including the
retrofitted `CREATE UNIQUE INDEX IF NOT EXISTS users_vekn_key`, because `CREATE TABLE IF NOT EXISTS`
never adds a constraint to a table that already exists.

## Roles are re-checked hourly

Login-only refresh would leave a demoted Rulemonger approving until their session expired. So
`api.get_current_user` re-checks through the stored refresh token once an hour.

**Rotation revokes the chain on reuse**, so exactly one request may spend the stored token. The check
is claimed with a conditional `UPDATE … WHERE roles_checked_at IS NOT DISTINCT FROM <what we read>` —
one winner, and deliberately no row lock and no pool connection held across archon's HTTP round-trip.

Archon refusing with a 400 is final: strip the flag and the token, which ends *every* session of that
user. `refresh_token` NULL with `roles_checked_at` set is the dead-chain marker; both NULL just means
never checked. Any other failure keeps the roles and defers the retry an hour.

## Traps

- **`GET /{page:path}` is the last route in `__init__.py`** and swallows anything registered after
  it. `GET /login/callback` must be declared above it.
- **`POST /login` survives as a `TESTING=1`-only session mint**, taking an `approver` flag. It is the
  only seam for testing approval, and the only way into a dev server with no registered archon
  client.
- **`next` is honoured only as a site-local path** (`local_next`). It rides a link anyone can
  craft and `/login` is a plain GET, so an absolute or protocol-relative value would walk the
  user through a genuine archon consent and land them offsite; anything else falls back to
  `/index.html`.
- Registering an OAuth client is per-archon-deployment; see [deploy.md](deploy.md).
