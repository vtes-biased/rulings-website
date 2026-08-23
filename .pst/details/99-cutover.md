# The v2 cutover, in order

The website release is the **last** step, and the `vtes-rulings` push is pinned to it —
immediately before it, inside the same window. Everything else is a prerequisite.

## Why the order is not interchangeable

1. **The data push cannot come early.** v1.3.0 — what runs on gravelines today — resolves a card
   token with `card_map[token[1:-1]]` (`v1.3.0:src/vtesrulings/utils.py:236`). Against the migrated
   file that raises `KeyError: '101565|rebirth'` (checked). `load_base` runs it over every ruling at
   startup, so once the migrated file is on `main`, **v1 cannot boot**. It survives on its in-memory
   index until something restarts it.
2. **It cannot come late either.** `load_base` normalizes bare tokens in memory, so the first
   approval after v2 deploys serializes all 606 rewritten rulings plus the new header anyway, as a
   side effect of whatever unrelated proposal it was (#79). And an approval pushing from an index
   cloned before the data push hits a non-fast-forward.
3. Therefore the push goes **after v1 is stopped, before v2 boots** — the hard switch #93 requires
   anyway (the two versions must never share the database).

## Steps

| # | What | Who | Ticket |
|---|---|---|---|
| 0 | ~~krcg 5.11 + bind the last regex~~ | done | #97 #98 |
| 1 | Confirm the prod archon client; register the beta one for dev | you | #81 |
| 2 | Apply the eight rulemonger VEKN ids by hand; ask people to submit drafts | you | #86 |
| 3 | Drain the in-flight proposals on live v1 | you | #76 |
| 4 | ~~krcg-static to `krcg>=5.10`~~ | done | #89 |
| 5 | Stop v1 | you | #93 |
| 6 | Push `vtes-rulings` (4 commits) | me | #79 |
| 7 | Tag and deploy the website | you/me | #2 |

**0 — done.** krcg 5.11 is released (`bd18770`, on PyPI); the website pins `krcg>=5.11` and every
format regex now binds krcg's (`4e268eb`). Not a gate for anything below — recorded so nobody
re-derives it.

**1 — mostly done, one confirmation open.** Two archon deployments, separate databases, therefore
two client registrations: **`archon.vekn.net` is prod**, `archon.krcg.org` is beta. `ARCHON_URL` now
points prod at vekn.net and the code default stays beta for dev (`362f551`). The pair in `vars.yml` +
vault is wired and internally consistent, and `authorization_url` emits exactly
`https://rulings.krcg.org/login/callback`, scope `profile:read`, S256. What no local check can reach
is archon's own client record — `GET /oauth/authorize` resolves the user before validating
`redirect_uri`, so only a logged-in look proves the registration. **Confirm before step 5**: that the
prod pair lives on vekn.net and lists that redirect verbatim. A typo surfaces as a 400 on the consent
page and nobody could log in — with v1 already stopped. The beta client for dev is separate and
blocks only local testing.

**2 — #86.** `UPDATE users SET vekn = '<vekn-id>' WHERE uid = '<row-uid>'` for the eight rows in the
detail file's table. It only rewrites `vekn`, so it **must run on the current schema**, before those
people's first archon login (afterwards they hold a fresh row and the fix is the move-proposals
recipe instead). Key on `uid`, never on `vekn` — the table has duplicate handles.

**3 — the drain.** A proposal is an overlay keyed on the uid a ruling had when it was edited, and
the base it merges against reloads renumbered: 606 of 2302 rulings change uid. Approve or discard
what is open first. Same ask as the drafts in step 2, so do them together.

**4 — done, and it was never a gate.** krcg-static's floor is `krcg>=5.10` and its CLAUDE.md says
so (`d52c2035`, on `main`). The ordering claim behind this step was wrong: `uv.lock` is *gitignored*
there and has never been tracked, so CI's plain `uv sync` resolves fresh every run and has been
installing 5.11 since its release. 5.11 also reads the current un-migrated file without complaint
(`load_online` attaches 5414 rulings, bare `{Name}` tokens intact, checked), so the 6-hourly cron is
safe either side of step 6. Step 6 waits on step 5 alone.

**6 — the push.** `vtes-rulings` is 4 commits ahead of `origin/main`: the migration (`68d5a6c`), the
krcg-3 script deletion (`1c8dd7d`), the reference-source check (`b316272`), the symbol list
(`ad7b0b5`). Re-verify before pushing: a fresh serializer pass over the tree must be a byte-for-byte
no-op, and `check_rulings` (offline half) must report 0 warnings.

**7 — the release.** `just release` bumps the version, tags and pushes; CI deploys the tag to
gravelines. The app boots, clones the migrated file and serves it.

## State of the unpushed work (as of this writing)

- **krcg** — pushed and released, 5.11. Nothing pending.
- **vtes-rulings** — 4 commits ahead of `origin/main`, listed above. Nothing else.
- **rulings-website** — 28 commits ahead of `origin/main`, carrying **both** epics interleaved: the
  card-token change (#76) and the archon login switch (#80). One deploy ships both. That is why the
  auth prerequisites gate a release whose headline feature is the token change.
- **krcg-static** — done and pushed (`d52c2035`), step 4 off the critical path.

## Rollback

Steps 1–4 are reversible on their own terms. From step 5 the switch is one-way in practice: v1
cannot read the migrated data, so a rollback to v1 means reverting the `vtes-rulings` push as well
(`git revert` the four commits and push, then restart v1). The legacy `users` rows survive the
cutover unreachable rather than deleted, so user recovery is never time-critical (#86).
