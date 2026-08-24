# The v2 cutover

Ephemeral. Dies with the last cutover line on the board.

`rulings.krcg.org` runs **v1.3.0**. `main` carries two landed epics — card tokens carrying the card
id, and archon OAuth login — and one deploy ships both. The switch is **hard and one-way**.

## Why the order is not interchangeable

1. **The data push cannot come early.** v1.3.0 resolves a card token with
   `card_map[token[1:-1]]` (`v1.3.0:src/vtesrulings/utils.py:236`). Against the migrated file that
   raises `KeyError: '101565|rebirth'` (checked). `load_base` runs it over every ruling at startup,
   so once the migrated file is on `main`, **v1 cannot boot** — it survives only on its in-memory
   index until something restarts it.
2. **It cannot come late either.** `load_base` normalises bare tokens in memory, so the first
   approval after v2 deploys serialises all 606 rewritten rulings plus the new headers anyway, as a
   side effect of whatever unrelated proposal it was. And an approval pushing from an index cloned
   before the data push hits a non-fast-forward.
3. Therefore the push goes **after v1 is stopped, before v2 boots** — which is the hard switch the
   schema move requires anyway: v2's `db.init()` drops `category` and appends the archon columns,
   and v1.3.0's positional INSERT then writes into the wrong ones. The two versions must never share
   the database.

## Steps

| # | What | Who |
|---|---|---|
| 0 | ~~krcg 5.11 released, website pinned, every format regex bound to krcg~~ | done |
| 1 | ~~Register the archon OAuth clients, prod and beta~~ | done 2026-08-23 |
| 1b | ~~Deploy archon-vibe with the consent fix, prod and beta~~ | done 2026-08-24 |
| 2 | ~~Ask on Discord: submit any draft you care about~~ | done 2026-08-23 |
| 3 | ~~Drain the in-flight proposals on live v1~~ | done 2026-08-24 |
| 4 | ~~krcg-static to `krcg>=5.10`~~ | done, and never a gate |
| **5** | **Stop v1** | @lip |
| **5b** | **`DELETE FROM users`** — every legacy row is deprecated | @lip |
| **6** | **Push `vtes-rulings` (5 commits)** | agent |
| **7** | **Tag and deploy the website** | @lip |

### 1b — the gate found by testing the login

First login worked; the second looped on archon's consent screen forever. With consent already on
file `GET /oauth/authorize` answered a 302, but the consent page reaches it through `fetch` with a
Bearer token, and a fetch cannot read `Location` off a redirect (`redirect: "manual"` → opaque
response, empty header list), so the page navigated to the empty string and called `/authorize`
again. Fixed in archon-vibe `6197f96` — all three redirects answer `{"redirect_url": …}` like the
approval path already did.

Shipped in `v1.0.8`, tagged 2026-08-24 and deployed to all three hosts, which serve the identical
bundle. Retired 2026-08-24 by a double login from a local dev server against
`archon.krcg.org`: the second one went straight through, no consent screen. That is the deployed
code prod runs, so what it leaves open is prod's *client record*, below.

### 5b — the users

Step 5b is one statement:

```sql
SELECT count(*) FROM proposals;  -- must be 0: step 3 is the drain, and the FK blocks the DELETE
DELETE FROM users;
```

**Every legacy row is deprecated** (decided 2026-08-23). Archon owns identity; a legacy row is worth
keeping only for what hangs off it, and the drain takes that away. `category` is dropped by
`db.init()` and `approver` is archon's answer now.

This replaced a plan to hand-map the eight rows carrying a tier to their VEKN ids so `login_user`
would adopt them — it bought back only their proposals, which the drain removes anyway, and carried
a real hazard: a mistyped id that happens to be another member's real one hands that person the
wrong row. The adoption path itself (`UPDATE … WHERE archon_uid IS NULL AND vekn=%s`) went with it.

Do **not** use `rulings-web resetdb`: that CLI ships with v2, and v2 is not deployed yet at 5b.
The table survives the DELETE, so `db.init()`'s `CREATE UNIQUE INDEX IF NOT EXISTS users_vekn_key`
is what puts the declared UNIQUE on it.

Kept as the record of who held a tier on v1 — no procedure consumes it; recovery, if anyone ever
asks, keys on `uid`:

| handle | row uid | tier | proposals | submitted | VEKN id |
|---|---|---|---|---|---|
| the1andonlime | `30e1b2a3-92f9-487c-9f25-999373a411e7` | RULEMONGER | 4 | 4 | 5360022 |
| Hobbesgoblin | `07c05586-6583-4746-b6b7-6fd993595a35` | RULEMONGER | 3 | 3 | 4720002 |
| squidalot | `964ac13e-1c45-49eb-b738-7a4ab61a40a1` | RULEMONGER | 1 | 0 | 8180022 |
| Ankha | `5c41d803-5499-433d-9bdf-530a4b94f2db` | ADMIN | 1 | 1 | 3200188 |
| kschaefer | `4b3e09ec-25c5-49c8-8365-baa7e7f1811c` | RULEMONGER | 0 | 0 | 1003455 |
| inm8 | `781aad7c-08a9-4a33-9f98-c4da8a23e166` | RULEMONGER | 0 | 0 | — |
| Sergio | `09dfee84-aec4-43e8-b679-98fea840af87` | RULEMONGER | 0 | 0 | 3120101 |
| lip | `fff5b489-f823-4ea1-818c-def524189e30` | ADMIN | 0 | 0 | 3200340 |

Re-measure exposure before the window with the audit query — the `channel_id` predicate is what
separates a submitted proposal from an unsubmitted draft:

```shell
sudo -u postgres psql -d vtes-rulings -c "
SELECT u.uid, u.vekn, u.category,
       count(p.uid)                                                        AS proposals,
       count(p.uid) FILTER (WHERE coalesce(p.data->>'channel_id','') <> '') AS submitted
  FROM users u LEFT JOIN proposals p ON p.usr = u.uid
 GROUP BY u.uid, u.vekn, u.category
 ORDER BY u.vekn ~ '^[0-9]+\$', count(p.uid) DESC;"
```

The audit (42 rows, 2026-08-22) found **not one numeric VEKN id** — every row holds a vekn.net login
handle, because v1.3.0 stored `params["username"]` verbatim. 11 rows owned 17 proposals, 9 of them
submitted. Four people held two rows apiece (`Artemis`/`artemis`, `Oracle.kid`/`oracle.kid`,
`Trydeflectingthisgrapple`/`trydeflectingthisgrapple`, and `Hobbesgoblin` twice over), which proves
the production table never enforced the `vekn UNIQUE` its `CREATE TABLE` declares.

### 3 — the drain

Drained 2026-08-24. It had to happen because a proposal is an overlay keyed on the uid a ruling had
when it was edited, and the base it merges against reloads renumbered: **651 of 2302 ruling texts
change, carrying 622 distinct uids** across the five commits. Re-check `SELECT count(*) FROM proposals` is still 0 at the window — the FK
blocks 5b's `DELETE FROM users` otherwise, and the site stays open until step 5 stops it.

### 6 — the push

`vtes-rulings` is 5 commits ahead of `origin/main`: the card-token migration (`68d5a6c`), the
krcg-3 script deletion (`1c8dd7d`), the reference-source check (`b316272`), the symbol list
(`ad7b0b5`), and the newsgroup reference migration (`ea000ff`). The card-token migration rewrote 831
token occurrences / 395 distinct tokens across 606 rulings, produced through `commit_index` so it is
byte-identical with what an approval writes.

`ea000ff` re-pointed 894 references from Google Groups to `usenet.krcg.org` and renamed 28 keys, so
55 further rulings change uid. Unlike `68d5a6c` it was written by hand, and the serializer pass is
what caught the cost: the eight header lines it added to `references.yaml` were absent from
`REFERENCES_COMMENT`, so the next approval would have deleted them. Folded in, together with
`usenet.krcg.org` in `RULING_DOMAINS` — without that, `check_reference` rejects all 894 and no one
can add or fix a newsgroup reference. Neither gates the push; **both must be in the release that
ships at step 7.**

Re-verify before pushing: a fresh serializer pass over the tree must be a **byte-for-byte no-op**,
and `check_rulings` (offline half) must report **0 warnings**. Verified 2026-08-24 against `ea000ff`:
all three files serialise identical, `check_consistency` clean, no unused and no duplicate
references.

**It is no longer a fast-forward.** Live v1 approved four rulings on 2026-08-24 between 14:07 and
15:11 UTC (`1924e2a`…`ba9dd01`, `rulings-bot`), so `origin/main` is 4 ahead of where the five local
commits branch from, and every hour v1 stays up can add another. A trial rebase of the five onto
`origin/main` conflicts in two hunks of `rulings.yaml` — mechanical. What is not mechanical is that
the bot wrote them in the **pre-migration format**: bare `{Crypt's Sons}` card tokens, and two new
Google Groups references (`LSJ 20061211`, `LSJ 20061213`, both in thread `h3onVZ1NqpQ`, which the
archive holds). So the tree lands mixed, and the serializer no-op above then fails on exactly those
rulings.

The card tokens self-heal — `load_base` normalises them in memory and the first v2 approval writes
them out — so they cost a no-op verify, not correctness. The two references do not: they must be
re-pointed at `usenet.krcg.org` by hand, and that thread carries 355 messages with a dozen LSJ posts
on each cited day, so it goes through the migration's resolve/brief path rather than a guess.

Which makes the order tighter than step 6 reads: **rebase after step 5, not before**. Rebasing while
v1 still approves just invites another divergence, and every approval after the rebase is one more
ruling in the old format. Sequence at the window: stop v1 → rebase the five onto `origin/main` →
re-point the two references → re-run both verifies → push.

### 7 — the release

`just release` bumps the version, tags and pushes; CI builds the wheel and attaches it to a GitHub
Release. **Deploy is then manual** — `cd ansible && just deploy`. The app boots, clones the migrated
file and serves it.

## State of the other repos (re-checked 2026-08-24)

- **rulings-website** — `main` is 7 commits ahead of `origin/main`, all of them board and cutover
  bookkeeping. `just release` at step 7 pushes them; nothing here needs a push of its own.
- **krcg** — released as 5.11, on PyPI. Nothing pending.
- **krcg-static** — done and pushed (`d52c2035`), off the critical path.
- **vtes-rulings** — 5 commits ahead and, since v1 kept approving today, **4 behind**. Both
  listed under step 6.
- **archon-vibe** — `v1.0.8` deployed prod and beta; `main` carries 17 further unpushed commits,
  none of them a gate here.

## Rollback

Steps 1–4 are reversible on their own terms. From step 5 it is one-way in practice: v1 cannot read
the migrated data, so a rollback means reverting the five `vtes-rulings` commits and pushing that
before restarting v1.

## Residual risk

No local check can reach archon's client record — `GET /oauth/authorize` resolves the user before
validating `redirect_uri` — so a redirect-URI typo in prod's registration would surface as a 400 on
the consent page with v1 already stopped. **Nothing retires this before the window**: prod's client
points at `https://rulings.krcg.org/login/callback`, and no such route exists until v2 is the thing
serving that domain. Step 7's first login is the test, and a mistyped URI is fixed in archon's client
record, not by rolling back.
