# Epic #2 — Deploy via server-setup + GitHub App

## Target
`server-setup/deploy-targets.yml` already maps `vtes-biased/rulings-website: gravelines`. This epic
conforms the app to that house model (Ansible roles: `nginx_site`, `postgres_db`; systemd; Alloy
observability; pg-backup timers) and ships via a tag→deploy GitHub Actions workflow.

## GitHub App for the YAML repo (replaces the SSH identity)
Today `repository.py` pushes to `git@github.com:vtes-biased/vtes-rulings.git` over SSH with
`~/.ssh/id_rsa` (`GIT_SSH_COMMAND`). Replace with a **GitHub App**:
- **Read is anonymous** — `vtes-rulings` is public, so the startup clone (read path) needs no
  credential over HTTPS. Only the *push* needs auth.
- **Write uses a short-lived installation token** — the server holds the App private key (one
  secret), mints a ~1h installation token per push, scoped to `contents:write` on that one repo.
  No long-lived PAT, no `id_rsa` on the host, revocable in one click.
- **Provenance** — commits attributed to `rulings-bot[bot]`, distinct from human commits.
- **Bonus** — the same App / a `repository_dispatch` is the authenticated way to fire the
  krcg-static rebuild on approval (closes the propagation loop; see below).

Secret shape for gravelines: App ID + installation ID + private key (PEM). `repository.py`'s push
switches from SSH to HTTPS-with-token.

## Propagation loop
`approve/commit → vtes-rulings (YAML) → krcg package → krcg-static rebuild → static.krcg.org → players`.
krcg-static currently rebuilds via a **manual** GH Action. Approval should dispatch that rebuild
(child #17) so an approved ruling actually reaches players without someone remembering.

## The pieces
- #12 GitHub App + HTTPS token push in `repository.py`.
- #13 systemd unit + ASGI server (hypercorn/uvicorn), **single worker** (epic #1 constraint), env +
  secrets layout.
- #14 `nginx_site` vhost + certbot TLS.
- #15 `postgres_db` role: provision DB + backups; drop the `localhost` DB assumption in `db.py`
  (`CONNINFO` becomes env-driven).
- #16 tag→deploy GitHub Actions (build frontend, ship artifact, run migrations, restart service).
- #17 Alloy wiring + approval→krcg-static `repository_dispatch`.

## Secrets to migrate off the dev box
`DISCORD_WEBHOOK`, `DISCORD_SERVER_ID`, `SESSION_SECRET_KEY`, DB creds, and the **GitHub App private
key** (was: the SSH deploy key). All land in the `production` GitHub environment / host, pushed via
`server-setup`'s `just sync` (`DEPLOY_HOST`, `DEPLOY_HOST_KEY`).
