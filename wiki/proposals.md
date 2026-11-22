# Proposals — the overlay model

## Three data sources, deliberately separated

1. **Card data** — loaded from `krcg` (VEKN CSV) into `app.state.cards_map` / `cards_search` at
   startup. Never edited, only referenced.
2. **Rulings base** — the `vtes-rulings` YAML, cloned at startup and parsed into an in-memory
   `models.Index` (`app.state.rulings_index`). See [rulings-format.md](rulings-format.md).
3. **PostgreSQL** — `users` and `proposals`, nothing else. A proposal's payload is one JSON blob.

## A proposal is an overlay, not a copy

`proposal.Proposal` holds only what the proposal changed. `proposal.Manager` merges base + overlay
and presents a unified view to the API; `Manager.merge()` collapses them into a fresh `Index` at
approval. Every item — ruling, group, reference, card-in-group — carries a `models.State`:
`ORIGINAL`, `NEW`, `MODIFIED` or `DELETED`. The `get_*` / `all_*` methods reconcile the two layers
and compute the effective state.

This is why every action is trivially revertible: reverting means dropping the overlay entry, and an
edit that lands back on the base value drops itself.

## Request lifecycle

The active proposal id comes from the `X-Proposal` request header (stateless API callers) or the
session (`request.session["proposal"]`, browser sessions), with the header taking precedence. Two
FastAPI dependencies in `api.py`:

- **`proposal_update`** — a yield-dependency: loads the proposal `FOR UPDATE`, yields a
  `ProposalCtx`, persists after the endpoint returns. A path-operation error is re-raised at the
  `yield`, so the persist is skipped and the connection rolls back.
- **`proposal_readonly`** — returns a `Manager` over the base plus the active proposal, if any.

For API inspection and Discord discussion (all require authentication; non-approvers are scoped to
their own proposals, approvers also see submitted proposals from others):

- **`GET /api/proposal`** — lists proposals with metadata and change counts (`groups`, `rulings`,
  `references`).
- **`GET /api/proposal/{uid}`** — returns the full proposal overlay plus its computed `diff`.
- **`GET /api/proposal/{uid}/comments`** — reads the proposal's Discord thread via
  `DISCORD_BOT_TOKEN`, returned oldest-first. Requires a submitted proposal (`channel_id` set).
- **`POST /api/proposal/{uid}/comments`** — posts a plain-text comment (`{"content": …}`, max 2000
  chars) into the proposal's Discord thread via `DISCORD_WEBHOOK`. Requires a submitted proposal.

## Approval

`api.approve_proposal` → `Manager.merge()` → `repository.commit_index()`: regenerate all three YAML
files, run `yamlfix`, commit, push as the GitHub App. Then reload `rulings_index` from the repo,
post to the Discord thread, and fire the `krcg-static` rebuild dispatch (best-effort — logged, never
raised).

**`COMMIT_LOCK` serialises approvals.** Pending `P…` group ids are renumbered to stable `G…` ids
during serialisation; two concurrent runs would collide.

**Single worker is mandatory.** The index is in-process and mutated in place on approval; a second
worker would serve a stale one.

## Hazards

- **Renumbering strands overlays.** A proposal is keyed on the uid a ruling had when it was edited,
  and `Manager.update_ruling` looks up `self.base.rulings[target_uid][uid]`. Anything that changes
  ruling uids or group ids in the base — a format migration, a group renumber — leaves `MODIFIED`
  and `DELETED` overlay entries with nothing to resolve against. **Drain the in-flight proposals
  before deploying such a change**: proposals are transient by design, so draining is the fix, not
  migrating payloads.
- **A proposal outlives the session that made it.** It is only removed by approval or explicit
  delete.
- Proposals reference `users(uid)` by foreign key: deleting a user row requires its proposals to be
  gone first.
