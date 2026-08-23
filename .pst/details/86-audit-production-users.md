# Production users at the archon cutover

## The audit (run 2026-08-22, 42 rows)

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

So `db.login_user`'s adoption path (`archon_uid IS NULL AND vekn = <the userinfo
vekn_id>`) fires for **nobody** in production. It stays in the code because it is
correct and cheap, not because it will do any work here.

Handle → VEKN id cannot be automated either: vekn.net's member API exposes id,
name and city, and archon's own member sync (`vekn_api.py`, `vekn_push.py`) keys
on exactly those. Nothing anywhere stores the login handle. Mapping a handle to a
person is human recognition.

## What is actually at risk

| | rows | proposals |
|---|---|---|
| own something | 11 | 17 |
| of which **submitted** | 4 | 9 |
| of which **unsubmitted drafts** | 7 | 8 |

A submitted proposal is in the approver queue — `db.get_submitted_proposals`
filters on `channel_id`, not on owner, and `api.proposal_update` lets an approver
edit someone else's — so all 9 stay fully actionable after the cutover. Their
authors lose only their own handle on them.

That leaves **8 drafts across 7 people**: `Oracle.kid` (2), plus one each for
`trydeflectingthisgrapple`, `squidalot`, `zavierazo`, `Gr33n`, `dvorax` and
`marciohiroyuki`.

## Therefore: no pre-cutover hand-mapping

Mapping 42 handles by hand to save 8 drafts is not worth it, and mapping is not
time-critical anyway: **the legacy rows and their proposals are not destroyed by
the cutover**, they are merely unreachable by their author. Recovery works just as
well a month later.

1. Before the switch, ask people to **submit** any draft they care about. That is
   one click and it moves the proposal into the queue, where ownership stops
   mattering.
2. After the switch, recover on demand. The person logs in through archon, which
   gives them a fresh row; then move the old row's proposals onto it:

```sql
-- both uids come from the audit query above; never key this on vekn, see below
UPDATE proposals SET usr = '<fresh-row-uid>' WHERE usr = '<legacy-row-uid>';
DELETE FROM users WHERE uid = '<legacy-row-uid>';
```

Note this moves the proposals rather than writing `archon_uid` onto the legacy
row: by then the fresh row already holds that uid, and `archon_uid` is UNIQUE.

## Matching the rulemongers by hand

The eight rows carrying a tier today. Their VEKN ids were supplied by hand on
2026-08-23 — nothing in the data can derive them. Seven of eight: `inm8`'s id is
not known and will not be looked for, which costs nothing (0 proposals).

| handle | row uid | tier | proposals | submitted | VEKN id |
|---|---|---|---|---|---|
| the1andonlime | `30e1b2a3-92f9-487c-9f25-999373a411e7` | RULEMONGER | 4 | 4 | 5360022 |
| Hobbesgoblin | `07c05586-6583-4746-b6b7-6fd993595a35` | RULEMONGER | 3 | 3 | 4720002 |
| squidalot | `964ac13e-1c45-49eb-b738-7a4ab61a40a1` | RULEMONGER | 1 | 0 | 8180022 |
| Ankha | `5c41d803-5499-433d-9bdf-530a4b94f2db` | ADMIN | 1 | 1 | 3200188 |
| kschaefer | `4b3e09ec-25c5-49c8-8365-baa7e7f1811c` | RULEMONGER | 0 | 0 | 1003455 |
| inm8 | `781aad7c-08a9-4a33-9f98-c4da8a23e166` | RULEMONGER | 0 | 0 | — *not supplied* |
| Sergio | `09dfee84-aec4-43e8-b679-98fea840af87` | RULEMONGER | 0 | 0 | 3120101 |
| lip | `fff5b489-f823-4ea1-818c-def524189e30` | ADMIN | 0 | 0 | 3200340 |

### When it runs — inside the cutover window

Decided 2026-08-23: **between stopping v1 and booting v2** (#99 step 5→7), not
before. The statement only rewrites `vekn`, and `db.init()` leaves that column
alone — it adds `archon_uid`/`approver`/`refresh_token`/`roles_checked_at` and
drops `category` (`db.py:66-74`) — so it is schema-agnostic and runs identically
either side of the migration. The only real deadline is **before that person's
first archon login on v2**; afterwards they hold a fresh row and the fix is the
move-proposals recipe above. The window is the cleanest slot because nothing else
can write `users` while both engines are down.

No collision risk: every existing `vekn` is a handle, so a numeric id can never
duplicate one — and `db.init()` does not retrofit the `vekn UNIQUE` the current
table lacks anyway.

### The script

Run on gravelines as one transaction. Every statement keys on `uid`; **never** on
`vekn` (the duplicate `Hobbesgoblin` below). `inm8` is deliberately absent — id
unknown, 0 proposals, so it forfeits row continuity and nothing else.

```sql
-- sudo -u postgres psql -d vtes-rulings -1 -f match_vekn_ids.sql
BEGIN;
UPDATE users SET vekn = '5360022' WHERE uid = '30e1b2a3-92f9-487c-9f25-999373a411e7';  -- the1andonlime
UPDATE users SET vekn = '4720002' WHERE uid = '07c05586-6583-4746-b6b7-6fd993595a35';  -- Hobbesgoblin
UPDATE users SET vekn = '8180022' WHERE uid = '964ac13e-1c45-49eb-b738-7a4ab61a40a1';  -- squidalot
UPDATE users SET vekn = '3200188' WHERE uid = '5c41d803-5499-433d-9bdf-530a4b94f2db';  -- Ankha
UPDATE users SET vekn = '1003455' WHERE uid = '4b3e09ec-25c5-49c8-8365-baa7e7f1811c';  -- kschaefer
UPDATE users SET vekn = '3120101' WHERE uid = '09dfee84-aec4-43e8-b679-98fea840af87';  -- Sergio
UPDATE users SET vekn = '3200340' WHERE uid = 'fff5b489-f823-4ea1-818c-def524189e30';  -- lip
COMMIT;
```

Read back before booting v2 — seven rows, each `vekn` the id below:

```sql
SELECT uid, vekn FROM users WHERE uid IN (
  '30e1b2a3-92f9-487c-9f25-999373a411e7',
  '07c05586-6583-4746-b6b7-6fd993595a35',
  '964ac13e-1c45-49eb-b738-7a4ab61a40a1',
  '5c41d803-5499-433d-9bdf-530a4b94f2db',
  '4b3e09ec-25c5-49c8-8365-baa7e7f1811c',
  '09dfee84-aec4-43e8-b679-98fea840af87',
  'fff5b489-f823-4ea1-818c-def524189e30');
```

Only `07c05586…` carries the `Hobbesgoblin` proposals; the second row of that name
(`5b00b1b0…`, no proposals) must be left alone.

**A wrong id is worse than a missing one, on four rows.** Adoption matches
`archon_uid IS NULL AND vekn = <the id archon reports>` (`db.py:113-116`), so a
typo that happens to be some *other* member's real id hands that person the
legacy row and its proposals at their first login. That only bites where the row
owns something — `the1andonlime` (4), `Hobbesgoblin` (3), `squidalot` (1),
`Ankha` (1). On the empty rows a typo just parks an unreachable blank row. The
ids were transcribed by hand and nothing here can check them against vekn.net
(its member API needs `VEKN_API_USERNAME`/`PASSWORD`, which we do not hold), so
re-read those four against archon's member records before running the block.

## Duplicate rows — why the recipe keys on uid

Four people already hold two rows apiece: `Artemis`/`artemis`,
`Oracle.kid`/`oracle.kid`, `Trydeflectingthisgrapple`/`trydeflectingthisgrapple`
— and **`Hobbesgoblin` twice over, the two indistinguishable in the dump**
(`07c05586…`, 3 proposals, and `5b00b1b0…`, none). They lose a proposal to a
mistyped capital today, the same failure the cutover generalizes.

The identical pair means the production table does not enforce the `vekn UNIQUE`
that v1.3.0's `CREATE TABLE` declares — `CREATE TABLE IF NOT EXISTS` never
retrofits a constraint onto a table an older version created — or that one value
carries invisible whitespace. Either way, **never key a recovery statement on
`vekn`**: the subquery form errors on two rows and the DELETE takes both. Use the
uids the audit prints.

Nothing in the new code depends on that constraint here, since the adoption path
fires for nobody in production; and `login_callback` already turns the unique
violation an adopted duplicate would raise into a message rather than a 500.
