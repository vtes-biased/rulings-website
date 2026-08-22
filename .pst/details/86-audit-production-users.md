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
-- <handle> is the vekn.net login handle; <vekn-id> the archon-reported VEKN id
UPDATE proposals SET usr = (SELECT uid FROM users WHERE vekn = '<vekn-id>')
 WHERE usr = (SELECT uid FROM users WHERE vekn = '<handle>');
DELETE FROM users WHERE vekn = '<handle>';
```

Note this moves the proposals rather than writing `archon_uid` onto the legacy
row: by then the fresh row already holds that uid, and `archon_uid` is UNIQUE.

## Housekeeping seen in the dump

Four people already hold two rows apiece from case-variant logins — `Hobbesgoblin`
twice, `Artemis`/`artemis`, `Oracle.kid`/`oracle.kid`,
`Trydeflectingthisgrapple`/`trydeflectingthisgrapple`. They lose a proposal to a
mistyped capital today, which is the same failure the cutover generalizes, and the
same two statements above fix it.
