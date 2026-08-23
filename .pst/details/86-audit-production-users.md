# Production users at the archon cutover

## Decision (2026-08-23): deprecate every legacy row

Archon owns identity. Only an archon member holding a `vekn_id` may log in, and
everything on our row — the VEKN id, the approver flag — is archon's answer,
rewritten on every login. So a legacy row is worth keeping only for what hangs
off it, and the drain (#99 step 3) takes that away: every in-flight proposal is
approved or discarded before the window, because a proposal is an overlay keyed
on ruling uids and 606 of 2302 change at the migration. `category` is dropped by
`db.init()` and `approver` comes from archon's roles.

Nothing is left. So the whole table goes, at **#99 step 5b**, between stopping v1
and booting v2:

```sql
SELECT count(*) FROM proposals;  -- must be 0: the drain is step 3, and the FK would block the DELETE
DELETE FROM users;
```

`rulings-web resetdb` would do it too, but that CLI ships with v2 and v2 is not
deployed yet at 5b — hence plain SQL. The table survives, so `db.init()`'s
`CREATE UNIQUE INDEX IF NOT EXISTS users_vekn_key` is what puts the declared
UNIQUE on it; a `DROP TABLE` would get it from `CREATE TABLE` instead. Either
works.

**What this replaced.** An earlier plan hand-mapped the eight rows carrying a
tier to their VEKN ids so `login_user` would adopt them at first archon login.
That bought back only their proposals, which the drain removes anyway, and it
carried a real hazard: a mistyped id that happens to be another member's real one
hands that person the wrong row. Dropped, along with the adoption path itself
(`UPDATE … WHERE archon_uid IS NULL AND vekn=%s`) — with no legacy rows left it
was dead code. `login_user` is now: match on `archon_uid`, else insert.

The ids were collected by hand. No procedure consumes them any more — recovery,
if anyone ever asks, keys on `uid` — so the table below is kept as the record of
who held a tier on v1, nothing more.

| handle | row uid | tier | proposals | submitted | VEKN id |
|---|---|---|---|---|---|
| the1andonlime | `30e1b2a3-92f9-487c-9f25-999373a411e7` | RULEMONGER | 4 | 4 | 5360022 |
| Hobbesgoblin | `07c05586-6583-4746-b6b7-6fd993595a35` | RULEMONGER | 3 | 3 | 4720002 |
| squidalot | `964ac13e-1c45-49eb-b738-7a4ab61a40a1` | RULEMONGER | 1 | 0 | 8180022 |
| Ankha | `5c41d803-5499-433d-9bdf-530a4b94f2db` | ADMIN | 1 | 1 | 3200188 |
| kschaefer | `4b3e09ec-25c5-49c8-8365-baa7e7f1811c` | RULEMONGER | 0 | 0 | 1003455 |
| inm8 | `781aad7c-08a9-4a33-9f98-c4da8a23e166` | RULEMONGER | 0 | 0 | — not supplied |
| Sergio | `09dfee84-aec4-43e8-b679-98fea840af87` | RULEMONGER | 0 | 0 | 3120101 |
| lip | `fff5b489-f823-4ea1-818c-def524189e30` | ADMIN | 0 | 0 | 3200340 |

## The audit behind it (run 2026-08-22, 42 rows)

```shell
sudo -u postgres psql -d vtes-rulings -c "
SELECT u.uid, u.vekn, u.category,
       count(p.uid)                                                        AS proposals,
       count(p.uid) FILTER (WHERE coalesce(p.data->>'channel_id','') <> '') AS submitted
  FROM users u LEFT JOIN proposals p ON p.usr = u.uid
 GROUP BY u.uid, u.vekn, u.category
 ORDER BY u.vekn ~ '^[0-9]+\$', count(p.uid) DESC;"
```

**Not one of the 42 rows holds a numeric VEKN id — every one is a vekn.net login
handle** (`the1andonlime`, `Hobbesgoblin`, `Ankha`, …). v1.3.0 stored
`params["username"]` verbatim (`__init__.py:262`): vekn.net was asked to check the
password and never asked for the member id. The `9999999` row in the dev database
was simply someone typing their id into the login box.

Handle → VEKN id cannot be automated: vekn.net's member API exposes id, name and
city, and archon's own member sync (`vekn_api.py`, `vekn_push.py`) keys on exactly
those. Nothing anywhere stores the login handle. Mapping a handle to a person is
human recognition — which is why the eight above were supplied by hand.

What the rows carried at audit time:

| | rows | proposals |
|---|---|---|
| own something | 11 | 17 |
| of which **submitted** | 4 | 9 |
| of which **unsubmitted drafts** | 7 | 8 |

The 8 drafts sat with `Oracle.kid` (2), plus one each for
`trydeflectingthisgrapple`, `squidalot`, `zavierazo`, `Gr33n`, `dvorax` and
`marciohiroyuki`. Hence step 2 of the runbook: ask on Discord that anyone submit
a draft they care about, so it reaches the queue and gets approved on its merits
during the drain rather than discarded with its owner's row.

## Why `vekn` is UNIQUE and why that is now inert

`db.init()` enforces `vekn` UNIQUE globally. It mirrors an invariant archon
already owns — `idx_objects_user_vekn_id` in `archon-vibe/backend/src/schema.sql`
is a unique index on `full->>'vekn_id'` over user objects, and a VEKN id is never
moved between archon accounts. So once every row's `vekn` comes from archon, no
two rows can collide and no login path can raise a unique violation. That is why
neither `login_callback` nor `recheck_roles` carries a handler for one: the state
is unreachable, and if archon's invariant were ever broken a loud 500 is the
failure we would want.

It was *not* inert before this decision: the legacy rows held vekn.net handles
and hand-typed ids, values archon never issued, and those could collide with a
real one. Wiping them is what makes the constraint a faithful mirror.

Four people held two rows apiece — `Artemis`/`artemis`, `Oracle.kid`/`oracle.kid`,
`Trydeflectingthisgrapple`/`trydeflectingthisgrapple` and `Hobbesgoblin` twice
over, the last pair indistinguishable in the dump. That last one proves the
production table never enforced the `vekn UNIQUE` its `CREATE TABLE` declares
(`CREATE TABLE IF NOT EXISTS` never retrofits a constraint). The `DELETE` takes
them all, so none of it needs resolving by hand.
