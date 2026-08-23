# Operations — laptop to gravelines

Tooling is `just` + `uv`, npm for the frontend. `just` with no recipe lists them.

| | |
|---|---|
| `just update` | `npm install --include=dev` + `uv sync --upgrade --group dev` |
| `just serve` | Vite watcher (via pm2) + hypercorn `--reload --workers 1` on `127.0.0.1:5000`; sources `.env` |
| `just stop` | stop the pm2 frontend process |
| `just lint` / `just fmt` | ruff check + format (line length 100, py313) |
| `just typecheck` | `ty check --error-on-warning` — warnings are errors, so a stale ignore fails |
| `just test` | `TESTING=1 uv run pytest` (excludes the `discord` marker) |
| `just deps-check` | read-only: would `just update` pull anything? Non-zero if so |
| `just release [minor\|major]` | bump, commit, tag, push. Versioning is `major.minor` only |
| `just clean` | drop build artifacts and caches |

Single test: `TESTING=1 uv run pytest tests/test_api.py::test_get_card`. Frontend only:
`npm run build` (`npm run front` to watch).

## Runtime prerequisites

- **PostgreSQL** locally: database `vtes-rulings`, role `vtes-rulings`, with `CREATEDB` and access to
  the `postgres` maintenance database (the test harness creates and drops `vtes-rulings-test` per
  session). Override with `DB_NAME` / `DB_USER` / `DB_PWD`, or the whole DSN with `DATABASE_URL`
  (prod passes a unix-socket peer-auth DSN).
- **Network at startup**: the app clones the rulings repo to a temp dir and loads the full VEKN card
  database through krcg (`load_local`, from krcg-packaged CSVs).
- **An archon OAuth client** registered for the archon deployment you point at, or there is no way in
  but `TESTING=1`.
- **Pushing approvals** authenticates as a **GitHub App**: `repository.py` mints a short-lived
  installation token from `RULINGS_GITHUB_APP_ID` (App ID or Client ID) +
  `RULINGS_GITHUB_INSTALLATION_ID` + `RULINGS_GITHUB_PRIVATE_KEY` (PEM path) and pushes over HTTPS as
  `rulings-bot[bot]`. Unset → plain `git push` (tests, local file remotes). No `id_rsa` on the host.
  The *read* path is anonymous HTTPS on the public repo.

Env vars are read directly via `os.getenv`, no settings object: `DISCORD_WEBHOOK`,
`DISCORD_SERVER_ID`, `ARCHON_URL`, `ARCHON_CLIENT_ID`, `ARCHON_CLIENT_SECRET`, `SESSION_SECRET_KEY`,
`SITE_URL_BASE` (builds the redirect URI archon matches exactly), `DATABASE_URL`, `RULINGS_GIT`,
`RULINGS_GITHUB_{APP_ID,INSTALLATION_ID,PRIVATE_KEY}`, `KRCG_STATIC_{REPO,INSTALLATION_ID}`,
`GIT_AUTHOR_{NAME,EMAIL}`, `GIT_SSH_COMMAND` (only for an ssh `RULINGS_GIT`), `TESTING`.

## The test harness

Hermetic — no SSH, no network. `tests/conftest.py` serves a vendored rulings snapshot
(`tests/fixtures/rulings/`, commit pinned in `SOURCE`) as a local bare git remote via `RULINGS_GIT`,
and runs against a throwaway `vtes-rulings-test` database it creates and drops per session. Card data
is pinned by the locked krcg version.

## CI

- **`test.yml`** on every PR and push to `main`: Postgres service, libpq, npm build, ruff, `ty`,
  pytest.
- **`release.yml`** on a `v*` tag: the same suite as a gate, then wheel + sdist + pinned
  `requirements.txt` attached to a GitHub Release. It publishes artifacts; **it does not deploy.**

## Deploy

Manual, and its own page: [deploy.md](deploy.md). Nothing in this repo deploys on a tag — the release
workflow publishes artifacts, and `cd ansible && just deploy` ships them.
