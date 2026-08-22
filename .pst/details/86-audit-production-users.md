# Normalizing production users before the archon cutover

## The problem

`vekn.net/api/vekn/login` accepts a **username** as well as a VEKN id, so
`users.vekn` holds both shapes — the dev database has `lip` next to `9999999`.
The adoption path in `db.login_user` matches `archon_uid IS NULL AND vekn = <the
userinfo vekn_id>`, so a row keyed on a username is never adopted: that person
gets a fresh row on their first archon login and their **in-flight proposals go
with the old one**, invisible to them. Approved rulings live in git and are
unaffected.

## The plan: fix `vekn`, not `archon_uid`

The ticket first said to write `archon_uid` onto the legacy row by hand. Setting
`vekn` to the person's real VEKN id instead is strictly better:

- it needs only the VEKN id — no archon uid lookup, no archon database access;
- `db.login_user`'s existing adoption then does the work automatically, with no
  hand-written archon uid to get wrong;
- it touches only columns the **currently deployed** app already has, so it runs
  *before* the cutover rather than in the window after it — and the boot of the
  new app is one-way (see #93).

## 1. Audit (read-only)

On gravelines (`152.228.170.51`, user `deploy`, passwordless sudo):

```shell
sudo -u postgres psql -d vtes-rulings -c "
SELECT u.uid, u.vekn, u.category,
       count(p.uid)                                                   AS proposals,
       count(p.uid) FILTER (WHERE coalesce(p.data->>'channel_id','') <> '') AS submitted
  FROM users u LEFT JOIN proposals p ON p.usr = u.uid
 GROUP BY u.uid, u.vekn, u.category
 ORDER BY u.vekn ~ '^[0-9]+\$', count(p.uid) DESC;"
```

Non-numeric `vekn` rows sort first. Only those **owning proposals** need work;
a username row with no proposal costs its owner nothing but a new row.

## 2. Map each one

For every non-numeric `vekn` that still owns a proposal, identify the person and
their VEKN id (that is the human step — the database cannot tell you).

No row holds that id yet:

```sql
UPDATE users SET vekn = '<vekn-id>' WHERE vekn = '<username>';
```

A row already holds it (they logged in both ways at different times) — move the
proposals over and drop the duplicate:

```sql
UPDATE proposals SET usr = '<numeric-row-uid>' WHERE usr = '<legacy-row-uid>';
DELETE FROM users WHERE uid = '<legacy-row-uid>';
```

## 3. Verify

```shell
sudo -u postgres psql -d vtes-rulings -c "
SELECT u.vekn, count(p.uid) FROM users u JOIN proposals p ON p.usr = u.uid
 WHERE u.vekn !~ '^[0-9]+\$' GROUP BY u.vekn;"
```

Empty means every in-flight proposal survives the cutover.

## Fallback

If the list is long enough that hand-mapping is silly, ask people to submit their
drafts before the cutover instead — a submitted proposal lives in the approver's
queue and no longer depends on its owner's row being found.
