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
touch .env              # create an env file (see below)
uv sync --group dev     # Python deps incl. the dev group (tests, ruff, ty, ansible)
just update             # same, plus the frontend: npm install + uv sync --group dev
```

`just update` installs both the frontend (`npm`) and Python (`uv`) dependencies.

### Environment

Put local config in `.env`. The two you'll usually want for a working local instance:

```shell
DISCORD_WEBHOOK=<your Discord community server webhook URL>
DISCORD_SERVER_ID=<your Discord server id>
```

Other vars the app reads (all optional locally):
`SESSION_SECRET_KEY`, `SITE_URL_BASE`, `DATABASE_URL` (and `DB_NAME`/`DB_USER`/`DB_PWD`),
`RULINGS_GIT`, `RULINGS_GITHUB_{APP_ID,INSTALLATION_ID,PRIVATE_KEY}` (the GitHub App used to push
approvals), `KRCG_STATIC_{REPO,INSTALLATION_ID}`, `GIT_AUTHOR_{NAME,EMAIL}`, and `GIT_SSH_COMMAND`.
`TESTING=1` bypasses real VEKN login validation.

> On startup the app needs network access: it clones the rulings repo to a temp dir and loads the
> full VEKN card database via `krcg`.

### Run locally

```shell
just serve   # Vite build watcher (via pm2) + hypercorn ASGI dev server on 127.0.0.1:5000, --reload --workers 1
just stop    # stop the pm2 frontend process
```

Frontend only: `npm run build` (one-shot) or `npm run front` (watch).

### Tasks

```shell
just lint        # ruff check + format --check
just fmt         # ruff check --fix + format
just typecheck   # ty (warnings are errors)
just test        # TESTING=1 pytest (excludes the `discord` marker)
just clean       # remove build artifacts and caches
just deps-check  # report whether newer deps are available (read-only)
```

Run a single test: `TESTING=1 uv run pytest tests/test_api.py::test_get_card`

Tests are hermetic: a vendored rulings snapshot is served as a local bare git remote, card data is
pinned by the locked `krcg` version, and the DB is a throwaway created and dropped per session — no
SSH or network required.

### CLI

The `rulings-web` script (installed by `uv sync`) exposes admin commands, e.g.:

```shell
uv run rulings-web resetdb
uv run rulings-web makeadmin <vekn-id>
```

## Release & deploy

```shell
just release [minor|major]   # bump version (major.minor only), commit, tag, push
```

Pushing the `v*` tag is the deploy trigger: CI builds the frontend, ships, and restarts the service.
This is an app, not a published library — no wheel is built or attached. Deployment (gravelines,
systemd, nginx, managed Postgres, GitHub App secrets) is handled by Ansible; see
[`ansible/README.md`](ansible/README.md).
