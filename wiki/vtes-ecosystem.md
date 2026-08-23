# The VTES ecosystem

Standing knowledge of the environment this product lives in, scoped to our footprint. Every claim
names its source.

## The game and its authority

**VTES** — *Vampire: The Eternal Struggle*, a collectible card game. The **VEKN** (Vampire Elder
Kindred Network) is the volunteer body that runs organised play and, through its **Inner Circle
(IC)** and **Rules Director**, issues official rules answers. A **ruling** is one such answer: a
short statement resolving a question about a card, carrying a reference to where it was given.

Rulings have been issued for three decades across newsgroups, forums and blogs by a succession of
Rules Directors. `krcg.rulings.RULING_AUTHORS` holds each source prefix with the date window that
person held the office — `utils.check_reference` rejects a reference dated outside its author's
window. (Source: `src/vtesrulings/utils.py:94`.)

## Roles

Archon owns roles; we never define our own. `IC` and `Rulemonger` are the two that reach us — either
one makes an **approver**. `PT`, `PTC`, `Judge` and `Judgekin` exist on archon as pure labels with no
capability attached. Archon's 28-row `CAPABILITIES` matrix is entirely archon-domain (member
administration, tournaments, leagues, sanctions, promos) and holds nothing rulings-shaped, which is
why we match role strings rather than a capability. (Source: `archon-vibe` audit, 2026-08-22.)

## The repositories and services

| | what it owns | how we touch it |
|---|---|---|
| **`vtes-biased/vtes-rulings`** | the rulings YAML — the durable source of truth | cloned anonymously over HTTPS at startup; pushed as a GitHub App on approval |
| **archon** (`archon-vibe`) | player identity: archon uid, VEKN id, roles | OAuth2 authorization-code + PKCE; `/oauth/userinfo` |
| **`krcg`** (python lib) | the VTES card database (VEKN CSV) and the rulings text format | `load_local` at startup; `ANKHA_SYMBOLS` and every format regex are krcg's |
| **`krcg-static`** | the static site players actually read rulings on | `repository_dispatch` (`rulings-updated`) after each approval |
| **vekn.net** | the member registry behind the VEKN id | never called by us any more (v1 proxied its login; v2 does not) |
| **Discord** | where proposals are discussed | webhook: submit opens a thread, approve posts into it |

**Two archon deployments, two separate databases, therefore two OAuth client registrations**:
`archon.vekn.net` is production, `archon.krcg.org` is beta and is what dev uses (`archon.py`'s
default). A client registered on one is unknown to the other. (Confirmed 2026-08-23; the registration
procedure is in [deploy.md](deploy.md).)

**krcg-static reads rulings live** — `krcg.rulings.load_online` against `vtes-rulings`, not the
snapshot baked into the installed krcg — so an approved ruling reaches players on the next rebuild
rather than the next krcg release. `raw.githubusercontent.com` caches for ~5 minutes, so a rebuild
fired immediately after a push may fetch a just-stale file.

## The VEKN id

A numeric member id issued by the VEKN, unique per person and never reassigned. Archon enforces
uniqueness on it (`idx_objects_user_vekn_id`, a unique index on `full->>'vekn_id'`). A user with no
VEKN id on archon is refused at login here — the rulings site identifies people by VEKN id and by
nothing else (it stores no name and no email).

Caution for anything reading historical data: **a VEKN id is not a vekn.net login handle.** v1 of
this site stored the handle the user typed into a password form, and nothing anywhere maps a handle
back to an id — vekn.net's member API exposes id, name and city only. (Source: production audit of
42 rows, 2026-08-22.)
