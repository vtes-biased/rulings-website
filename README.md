# VTES rulings website

[![Test](https://github.com/vtes-biased/rulings-website/actions/workflows/test.yml/badge.svg)](https://github.com/vtes-biased/rulings-website/actions/workflows/test.yml)
[![Python](https://img.shields.io/badge/python-3.13-3776ab.svg?logo=python&logoColor=white)](https://www.python.org)
[![Svelte](https://img.shields.io/badge/svelte-5-ff3e00.svg?logo=svelte&logoColor=white)](https://svelte.dev)

A web app for curating official rulings for **VTES** (Vampire: The Eternal Struggle).
Authenticated players draft **proposals** to add or edit rulings, groups, and references;
proposals are discussed on Discord; a rulemonger **approves** them, at which point the
change is serialized to YAML and git-pushed to the separate
[`vtes-biased/vtes-rulings`](https://github.com/vtes-biased/vtes-rulings) repository — the durable
source of truth.

The app is a FastAPI server rendering Jinja templates plus a JSON API, with a Svelte editor island
(TypeScript) and Tailwind CSS, built by Vite.

## Architecture in one breath

Three deliberately separated data sources:

1. **Card data** — loaded from [`krcg`](https://github.com/lionel-panhaleux/krcg) (VEKN CSV) at
   startup.
2. **Rulings base** — the YAML files in the external `vtes-rulings` repo, cloned at startup.
3. **PostgreSQL** — stores only `users` and in-flight `proposals`.

A proposal is an **overlay** on top of the base index. Approving it merges the overlay, serializes
all three YAML files, and pushes to the rulings repo as a GitHub App. Because that in-memory index
is mutated in place, the app **must run as a single worker**.

## Develop

### Prerequisites

- [Python](https://www.python.org) ≥ 3.13 and [Node.js](https://nodejs.org)
- [`uv`](https://docs.astral.sh/uv/) (Python env + deps) and [`just`](https://just.systems) (task runner)
- **PostgreSQL** running locally with database `vtes-rulings` and role `vtes-rulings`. The role
  needs `CREATEDB` and access to the `postgres` maintenance DB (the test harness creates and drops
  a throwaway `vtes-rulings-test` database per session). Override the DB name with `DB_NAME`, creds
  with `DB_USER`/`DB_PWD`, or the whole DSN with `DATABASE_URL`.

### Setup

```shell
touch .env       # local config; see wiki/operations.md for every var the app reads
just update      # npm install --include=dev + uv sync --upgrade --group dev
```

For a working local instance you want at least `DISCORD_WEBHOOK` and `DISCORD_SERVER_ID`, plus an
archon OAuth client (`ARCHON_CLIENT_ID` / `ARCHON_CLIENT_SECRET`) — without one there is no way in
but `TESTING=1`, which turns `POST /login` into a direct session mint.

> On startup the app needs network access: it clones the rulings repo to a temp dir and loads the
> full VEKN card database via `krcg`. It also needs a local PostgreSQL — database `vtes-rulings`,
> role `vtes-rulings`, with `CREATEDB` for the test harness.

### Run locally

```shell
just serve   # Vite watcher (pm2) + hypercorn on 127.0.0.1:5000, --reload --workers 1
just stop    # stop the pm2 frontend process
```

`just` with no recipe lists the rest: `lint`, `fmt`, `typecheck`, `test`, `clean`, `deps-check`.
Single test: `TESTING=1 uv run pytest tests/test_api.py::test_get_card`. Frontend only:
`npm run build`, or `npm run front` to watch.

Tests are hermetic: a vendored rulings snapshot served as a local bare git remote, card data pinned
by the locked `krcg` version, and a throwaway database created and dropped per session — no SSH, no
network.

The `rulings-web` script installed by `uv sync` carries the admin commands (`rulings-web resetdb`).
Who may approve is archon's call, not a local one: hold the `IC` or `Rulemonger` role there.

## Release & deploy

```shell
just release [minor|major]   # bump version (major.minor only), commit, tag, push
```

Pushing the `v*` tag runs the suite as a gate and, if green, attaches the wheel, sdist and pinned
`requirements.txt` to a GitHub Release. **Deploy is a separate, manual step** — `cd ansible && just
deploy` fetches that Release and ships it to gravelines (systemd, nginx, managed Postgres, GitHub
App secrets). The operator runbook — vault password, secrets layout, OAuth client registration — is
[`wiki/deploy.md`](wiki/deploy.md).

## Working in this repository

The repo runs a documentation-first harness. Three lifespans, and every artifact has exactly one:
code is permanent, [`wiki/`](wiki/index.md) is the standing source of truth for *what is* and *what
was decided*, and task context is ephemeral. [`BOARD.md`](BOARD.md) holds what must change — the goal
is zero, and completion is deletion.

Read [`wiki/index.md`](wiki/index.md) before changing anything, and
[`wiki/dogmas.md`](wiki/dogmas.md) before arguing with it. `CLAUDE.md` points agents at the same
places.
