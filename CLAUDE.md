# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A web app for curating official rulings for **VTES** (Vampire: The Eternal Struggle). Authenticated players draft **proposals** to add/edit rulings, groups, and references; proposals are discussed on Discord; a rulemonger/admin **approves** them, at which point the change is serialized to YAML and git-pushed to a **separate** repository (`git@github.com:vtes-biased/vtes-rulings.git`), which is the durable source of truth.

The app is a FastAPI server rendering Jinja templates plus a JSON API, with a Svelte editor island (TypeScript) and Tailwind CSS, built by Vite. (The `v2` branch completed the stack rework — Quart→FastAPI, Parcel→Vite, the Svelte editor island replacing the old `layout.ts`, and Bootstrap→Tailwind; see `.pst/tickets` and `.pst/details/`. It's being merged to `main` and deployed to replace the live Quart app.)

## Principles (enforced)

**Data.** The `vtes-biased/vtes-rulings` YAML files are the reference/base data. Nothing permanent lives outside them. The DB holds only in-flight proposals; approving one serializes to YAML and drops it from the DB. Keep the YAML simple and human-readable.

**Edit UX.** Edit mode is live: direct editing + continuous save, every action trivially revertible. No confirmation modals, no submit/save buttons, no multi-step commit flows. Ergonomy through simplicity and directness.

**Code.** Tight, local, KISS. No patterns/abstractions/indirection for elegance's sake — they must earn their keep. Don't write for a human reader's comfort; keep it terse for agentic workers. Comments never narrate code; a comment is justified only for a non-obvious consideration that isn't visible in the code itself.

**Workflow.** Don't postpone work or fixes that can be done now. The amount of code needing a rewrite is never a reason to defer — the coding loop is agentic and rewrites fast. After any non-trivial change, invoke the `reviewer` subagent before committing and address its findings.

**Commits.** Never reference pst ticket numbers in git commit messages or PR titles/bodies (hard rule): pst numbers are line positions, not stable ids, and `#N` would be read as a GitHub issue ref. Describe the change itself; track pst tickets via the `pst` CLI, not the commit log. **GitHub** issue numbers are the exception — when a commit fixes a known GitHub issue, close it from the commit with a `Fixes #N` line just above the trailers.

## Commands

Tooling is `just` + `uv` (npm for the frontend). **Note the README is stale** — it references `make update`/`make serve`, but the Makefile is gone; use `just`.

- `just update` — install/refresh deps (`npm install` + `uv sync --group dev`)
- `just serve` — run Vite build watcher (via pm2) + the hypercorn ASGI dev server with `--reload --workers 1`; sources `.env`
- `just stop` — stop the pm2 frontend process
- `just lint` / `just fmt` — ruff check + format (line length 100, target py313)
- `just test` — `TESTING=1 uv run pytest` (excludes the `discord` marker)
- `just clean` — remove build artifacts and caches
- `just release [minor|major]` — bump version, build wheel, tag, push, create GitHub release (versioning is `major.minor` only)

Run a single test: `TESTING=1 uv run pytest tests/test_api.py::test_get_card`
Frontend build only: `npm run build` (or `npm run front` to watch).

## Runtime prerequisites

- **PostgreSQL** running locally: database `vtes-rulings`, user `vtes-rulings` (see `db.py` `CONNINFO`, override the name with `DB_NAME`, creds with `DB_USER`/`DB_PWD`, or the whole DSN with `DATABASE_URL` — prod passes a unix-socket peer-auth DSN).
- **Rulings repo push**: the read path (startup clone) is anonymous HTTPS on the public `RULINGS_GIT` repo; the *push* on approval authenticates as a **GitHub App** — `repository.py` mints a short-lived installation token from `RULINGS_GITHUB_APP_ID` (App ID or Client ID) + `RULINGS_GITHUB_INSTALLATION_ID` + `RULINGS_GITHUB_PRIVATE_KEY` (PEM path) and pushes over HTTPS as `rulings-bot[bot]`. Unset → plain `git push` (tests, local file remotes). No `id_rsa` on the host.
- Network access: on startup the app clones the rulings repo to a temp dir and loads the full VEKN card database via `krcg` (`load_local`).
- **Tests are hermetic** (no SSH/network): `conftest.py` serves a vendored rulings snapshot (`tests/fixtures/rulings/`, pinned commit in `SOURCE`) as a local bare git remote via `RULINGS_GIT`, and runs against a throwaway `vtes-rulings-test` database it creates/drops per session — so the role needs `CREATEDB` and access to the `postgres` maintenance DB. Card data is pinned by the locked `krcg` version (`load_local` reads krcg-packaged CSVs, no network).

Key env vars (`.env`): `DISCORD_WEBHOOK`, `DISCORD_SERVER_ID`. Also read: `SESSION_SECRET_KEY`, `SITE_URL_BASE`, `DATABASE_URL`, `RULINGS_GIT`, `RULINGS_GITHUB_{APP_ID,INSTALLATION_ID,PRIVATE_KEY}`, `KRCG_STATIC_{REPO,INSTALLATION_ID}` (approval→krcg-static rebuild dispatch), `GIT_AUTHOR_{NAME,EMAIL}` (bot identity), and `GIT_SSH_COMMAND` (only if `RULINGS_GIT` is an ssh remote). Vars are read directly via `os.getenv` — notably `TESTING=1` bypasses real VEKN login validation. Deploy to gravelines lives in `ansible/` (see `ansible/README.md`).

## Architecture

### Three data sources, deliberately separated
1. **Card data** — loaded from `krcg` (VEKN CSV) into `app.cards_map` / `app.cards_search` at startup. Cards are never edited here, only referenced.
2. **Rulings base** — the `rulings/` YAML files (`references.yaml`, `groups.yaml`, `rulings.yaml`) in the *external* git repo, cloned at startup and parsed into an in-memory `models.Index` (`app.rulings_index`). See `repository.py` for load/serialize and the long design-note comments explaining the YAML-as-forever-format philosophy.
3. **PostgreSQL** — stores only `users` and `proposals` (proposal payload is a JSON blob). Everything else lives in git.

### The proposal overlay model (the core concept)
A `Proposal` (`proposal.py`) is an **overlay** on top of the base `Index`, not a copy. The `proposal.Manager` class merges base + overlay to present a unified view to the API. Every item (ruling/group/reference/card-in-group) carries a `models.State`: `ORIGINAL`, `NEW`, `MODIFIED`, or `DELETED`. The manager's `get_*`/`all_*` methods reconcile the two layers and compute effective state; `Manager.merge()` collapses them into a fresh `Index` at approval time.

Request lifecycle for edits: `api.py` FastAPI dependencies `proposal_update` (a yield-dependency: loads proposal `FOR UPDATE`, yields a `ProposalCtx`, persists after the endpoint returns — path-operation errors are re-raised at the `yield` so the persist is skipped and the connection rolls back) and `proposal_readonly` (returns a `Manager`). The current proposal is tracked in the session (`request.session["proposal"]`).

### Approval flow
`api.approve_proposal` → `Manager.merge()` → `repository.commit_index()` regenerates all three YAML files, runs `yamlfix`, commits and pushes. A module-level `COMMIT_LOCK` serializes approvals because pending groups (`P…` ids) get renumbered to stable `G…` ids during serialization and concurrent runs would collide. After a successful commit the in-memory `rulings_index` is reloaded from the repo. After the push, `dispatch_krcg_static_rebuild()` fires a `repository_dispatch` (`rulings-updated`) at the `krcg-static` repo so approved rulings reach players immediately instead of waiting on its 6h cron — best-effort (logged, not raised). It uses the same GitHub App as the push but a **separate installation** (`KRCG_STATIC_INSTALLATION_ID`, `KRCG_STATIC_REPO`); krcg-static's build fetches rulings live from vtes-rulings (`krcg.rulings.load_online`) rather than the snapshot baked into the installed krcg.

### Identifiers & text format
- Card ids are VEKN CSV integer ids (as strings). Group ids start with `G` (stable, in-repo) or `P` (pending, proposal-only). References are keyed `SRC YYYYMMDD` (e.g. `LSJ 20040518`).
- Ruling id = `utils.stable_hash(text)` (shake_128 → base32). Editing text changes the id; `update_ruling` tracks the old id so reverting drops the change.
- Ruling text embeds: discipline/type **symbols** in brackets `[pot]`, **card names** in braces `{Abbot}`, and **reference ids** in brackets `[LSJ 20040518]`. `utils.py` holds the regexes, the `ANKHA_SYMBOLS` map (text→font glyph), and reference validation (`RULING_AUTHORS` date windows + allowed `RULING_DOMAINS`).

### Users & auth
Login proxies to the VEKN site API (`/login`), stores `user_id` in session. `db.UserCategory` is `BASIC` / `RULEMONGER` / `ADMIN`; rulemongers+admins can approve, admins manage users (`admin.html`, `/user/*` routes). CLI (click group `main`, wired to the `rulings-web` script): `rulings-web resetdb`, `rulings-web makeadmin <vekn>`.

## Module map (`src/vtesrulings/`)
- `__init__.py` — FastAPI app, ASGI lifespan (loads cards + clones rulings repo onto `app.state`), page routes, `SessionMiddleware`, StaticFiles mount, Jinja template filters (`symbolreplace`, `cardreplace`, `newlines`), login/admin routes, CLI commands.
- `api.py` — `/api` blueprint; the proposal-editing REST surface and its `@proposal_update`/`@proposal_readonly` decorators.
- `proposal.py` — `Proposal` + `Manager` (the base/overlay merge logic).
- `repository.py` — clone, YAML load → `Index`, and `Index` → YAML serialize/commit/push.
- `models.py` — pydantic dataclasses for the domain (`Index`, `Ruling`, `Group`, `Reference`, `Card`, `State`, …).
- `db.py` — psycopg async pool; users & proposals persistence.
- `utils.py` — hashing, symbol/card/reference parsing, reference building & validation.
- `discord.py` — webhook posts (submit creates a thread, approve posts to it).
- `scraper.py` — scrapes VEKN forum pages to auto-derive a reference id from a URL.

Frontend lives in `src/front/` (`js/` legacy entrypoints being retired, `island/` Svelte); Vite (`vite.config.ts`) outputs to `src/vtesrulings/static/dist/` (stable entry names `js/index.js`, `js/groups.js`, `js/admin.js`, `js/island.js`, `css/layout.css`). Templates are in `src/vtesrulings/templates/` (`index.html` cards, `groups.html` groups, `admin.html` users).
