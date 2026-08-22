# Archon OAuth2 login

## What archon provides (verified in `archon-vibe`, 2026-08-22)

Full RFC 6749 + RFC 7636 (PKCE S256) provider, `backend/src/routes/oauth.py`,
documented in `wiki/access.md`.

- **Entry point is the frontend page `<ARCHON_URL>/consent`**, not the API.
  `frontend/src/routes/consent/+page.svelte` forwards its whole query string
  verbatim to `GET /oauth/authorize` carrying the user's first-party JWT, renders
  the consent screen, POSTs the approval and follows the returned `redirect_url`.
  Logged out, it bounces to `/login?redirect=<current url>` and honours a
  `login_hint` param. Because the query string is forwarded as-is, our redirect
  must already carry `response_type=code` and `code_challenge_method=S256` —
  `GET /oauth/authorize` 400s without them.
- **`POST /oauth/token` takes a JSON body**, not RFC 6749 form encoding. A
  deliberate first-party divergence, called out in the endpoint's own docstring.
  `client_id` + `client_secret` travel in that body: we are a confidential client.
- **`GET /oauth/userinfo`** with scope `profile:read` returns exactly
  `{sub, roles, vekn_id, capabilities}`. No name, no email — which is fine, the
  rulings site never displays a name, only `vekn`. `profile:read` is restricted to
  `/oauth/*`, so userinfo is the only thing that token can read.
- Access token 1h, refresh token 30d, **refresh rotation with chain revocation**.
- Client registration: `POST /oauth/clients` (IC or DEV), or self-serve in
  archon's profile page → Developer section. The secret is shown once.
  `redirect_uri` matching is exact — no prefix match.
- Production nginx proxies `/oauth` (allowlisted prefix), so this works in prod.

## Decisions

**Roles by string, not by capability.** Archon's `CAPABILITIES` matrix holds 28
rows, every one of them archon-domain: member/VEKN administration, tournaments,
leagues, community links, sanctions, promos, oauth clients, admin sync, archival
results. None is rulings-shaped and none is a sensible proxy. Archon's
"no role literal outside the engine" dogma governs archon's own routes; its
`roles` field is already the external contract — the Discord Linked Roles push
consumes it, and PT, PTC, Judge and Judgekin hold *no* capability at all, existing
purely as labels. So the rulings site reads `roles` and matches `IC` /
`Rulemonger` itself, in one function. Adding an `approve_ruling` capability to
archon's engine stays available later; swapping to it would touch that one
predicate and nothing else.

**One approver flag.** Once user management is deleted, nothing distinguishes
ADMIN from RULEMONGER — no code path branches between them. `UserCategory`
collapses to BASIC vs approver. `IC` or `Rulemonger` in `roles` → approver;
a non-null `vekn_id` → may propose; a null `vekn_id` → refused at login with
"claim a VEKN ID on archon first".

**Roles re-checked hourly against a stored refresh token.** Login-only refresh
would leave a demoted Rulemonger approving until their session expired. So the
`users` row keeps the refresh token and a `roles_checked_at`, and a stale row is
refreshed in-band.

## Flow

1. `GET /login` — mint `state` + a PKCE verifier into the session, 302 to
   `<ARCHON_URL>/consent?response_type=code&client_id=…&redirect_uri=…&scope=profile:read&state=…&code_challenge=…&code_challenge_method=S256`.
2. `GET /login/callback` — check `state`, `POST /oauth/token` (JSON body,
   `grant_type=authorization_code`, with the verifier), `GET /oauth/userinfo`
   with the access token, resolve the user, store the refresh token, set
   `session["user_id"]`.
3. The access token is opaque to us: never decode it, never store it.

## Hazards

- **`GET /{page:path}` is the last route in `__init__.py`** and swallows anything
  registered after it. `GET /login/callback` must be declared above it.
- **Refresh rotation revokes the whole chain on reuse**
  (`_handle_refresh_token`: a revoked token's reuse calls
  `revoke_oauth_token_chain`). Two concurrent requests refreshing the same stored
  token means one wins and the other kills the user's session outright. The
  refresh is therefore claimed with a conditional
  `UPDATE … WHERE roles_checked_at IS NOT DISTINCT FROM <the value we read>`:
  exactly one request wins the claim and spends the token, and — unlike the
  `SELECT … FOR UPDATE` this ticket first called for — no row lock or pool
  connection (of ten) is held across archon's HTTP round-trip.
- **Legacy `vekn` values are not VEKN ids.** vekn.net login accepts a username,
  and the dev database holds `lip` alongside `9999999`. Matching a legacy row on
  `vekn == vekn_id` therefore misses everyone who logged in by username: they get
  a fresh row and their **in-flight proposals go invisible**. Approved rulings
  live in git and are untouched. Audit gravelines before the cutover.
