# Operations — laptop to gravelines

Tooling is `mise` + `uv`, npm for the frontend. `mise tasks` lists the tasks in `mise.toml`.

| | |
|---|---|
| `mise run update` | `npm update` + `uv sync --upgrade --group dev` |
| `mise run serve` | Vite watcher (via pm2) + hypercorn `--reload --workers 1` on `127.0.0.1:5000`; sources `.env` |
| `mise run stop` | stop the pm2 frontend process |
| `mise run lint` / `mise run fmt` | ruff check + format (line length 100, py313) |
| `mise run typecheck` | `ty check --error-on-warning` — warnings are errors, so a stale ignore fails |
| `mise run test` | `TESTING=1 uv run pytest` — the whole suite, no opt-outs |
| `mise run deps-check` | read-only: would `mise run update` pull anything? Non-zero if so. The gate reads the lockfiles, so a fresh clone reports truthfully |
| `mise run release [minor\|major]` | bump, commit, tag, push. Versioning is `major.minor` only |
| `mise run clean` | drop build artifacts and caches |

Single test: `TESTING=1 uv run pytest tests/test_api.py::test_get_card`. Frontend only:
`npm run build` (`npm run front` to watch).

Both lockfiles — `uv.lock` and `package-lock.json` — are committed, and they are the pin: every
build off a tag resolves to the versions that tag holds. CI and the ansible build install from them
(`uv sync`, `npm ci`) and never resolve fresh; only `mise run update` moves them.

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
`DISCORD_SERVER_ID`, `DISCORD_BOT_TOKEN`, `DISCORD_API_URL`, `API_TOKEN`, `API_TOKEN_USER_ID`,
`ARCHON_URL`, `ARCHON_CLIENT_ID`, `ARCHON_CLIENT_SECRET`, `SESSION_SECRET_KEY`,
`SITE_URL_BASE` (builds the redirect URI archon matches exactly), `DATABASE_URL`, `RULINGS_GIT`,
`RULINGS_GITHUB_{APP_ID,INSTALLATION_ID,PRIVATE_KEY}`, `KRCG_STATIC_{REPO,INSTALLATION_ID}`,
`GIT_AUTHOR_{NAME,EMAIL}`, `GIT_SSH_COMMAND` (only for an ssh `RULINGS_GIT`), `TESTING`.

## The test harness

Hermetic — no SSH, no network — and **stand-ins, not mocks**: every dependency the suite talks
to is a real one on localhost, so the client code under test runs its own transport and error
handling. `tests/conftest.py` provides them all:

- a vendored rulings snapshot (`tests/fixtures/rulings/`, commit pinned in `SOURCE`) served as a
  local bare git remote via `RULINGS_GIT`;
- a throwaway `vtes-rulings-test` database, created and dropped per session;
- **archon** and **Discord** (webhook + `GET /channels/{id}/messages` REST API) as two `aiohttp`
  servers on ephemeral local ports, with `archon.ARCHON_URL`, `discord.DISCORD_WEBHOOK`,
  `discord.DISCORD_API_URL`, and `discord.DISCORD_BOT_TOKEN` rebound at them. The `client` fixture
  takes both and resets them per test, so no test can reach the real services whether it names them
  or not. Tests script an answer (`fake_archon.info`, `fake_archon.token_status`,
  `fake_discord.messages`) and read back what was sent (`fake_archon.spent`, `fake_discord.posts`,
  `fake_discord.reads`).

Card data is pinned by the locked krcg version.

## CI

- **`test.yml`** on every PR and push to `main`: Postgres service, libpq, `npm ci` + build, ruff,
  `ty`, pytest.
- **`release.yml`** on a `v*` tag: the same suite as a gate, then wheel + sdist + pinned
  `requirements.txt` attached to a GitHub Release. It publishes artifacts; **it does not deploy.**

## Deploy

Manual, and its own page: [deploy.md](deploy.md). Nothing in this repo deploys on a tag — the release
workflow publishes artifacts, and `mise run ansible:deploy` ships them.
