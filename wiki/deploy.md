# Deploy — gravelines

The app runs on **gravelines**, provisioned by **server-setup**, which owns the foundation: base
packages including Postgres, nginx and certbot, ssh/ufw/tuning, PG backups, Alloy. This repo's
`ansible/` play only ships the app, consuming server-setup's `postgres_db` and `nginx_site` roles: a
hardened systemd unit running **single-worker** hypercorn behind an nginx/TLS vhost at
`rulings.krcg.org`.

**Deploy is manual.** CI only builds and attaches the release artifacts — see
[operations.md](operations.md). Ansible tooling comes from the repo-root project's `dev` group (the
recipes call `uv run --project ..`); run everything from the `ansible/` directory.

```shell
just ping          # ansible ping as the deploy user — run this first
just dry-deploy    # --check --diff; review before applying
just deploy        # deploy the latest GitHub Release
RELEASE_TAG=v0.9 just deploy   # pin a specific release
SOURCE=local just deploy       # build and deploy a local wheel (dev)
QUICK=1 just deploy            # artifacts only (--tags app): wheel + unit, skip db/nginx
```

If `just ping` fails on auth, the `deploy` user's key is not authorised on gravelines yet.

**Wait for the release build before deploying.** `just release` only tags; the wheel and the
frontend dist are built by CI and attached to the GitHub Release afterwards, and `just deploy`
fetches those assets. Deploying in the gap installs an incomplete release and the site answers
**502** — nginx is up, nothing is listening on the backend port. Deploying again once the assets are
there fixes it; nothing needs to be undone. Check first:

```shell
gh run list --repo vtes-biased/rulings-website --limit 3   # the Release run must be `completed`
gh release view <tag> --repo vtes-biased/rulings-website   # and the assets must be attached
```

## One-time prerequisites

1. **DNS** — `rulings.krcg.org` → `152.228.170.51` (A record).
2. **The vault password**, decrypted (below).
3. **Secrets** — `vault.yml` filled and the GitHub App key dropped in (below).
4. **The archon OAuth client**, registered with its redirect URI verbatim (below). Nobody can log in
   without it.

## The vault password

The production ansible-vault password lives **in the repo, age-encrypted**, decryptable only by the
admins whose public keys are in `ansible/secrets/age-recipients.txt`. Install
[`age`](https://github.com/FiloSottile/age), then:

```shell
age -d -i ~/.ssh/id_rsa -o .vault_pass secrets/vault-pass.age
```

`.vault_pass` is git-ignored.

**Adding a recipient.** Recipients are one public key per line — an `ssh-ed25519` / `ssh-rsa` line
(e.g. from `https://github.com/<user>.keys`) or an `age1…` key. Editing the list does not re-key
anything; an existing recipient must re-encrypt:

```shell
age -d -i ~/.ssh/id_rsa -o .vault_pass secrets/vault-pass.age   # 1. decrypt
echo 'ssh-ed25519 AAAA… alice' >> secrets/age-recipients.txt    # 2. add the PUBLIC key
age -R secrets/age-recipients.txt -o secrets/vault-pass.age < .vault_pass   # 3. re-encrypt
```

The password value is unchanged — you are only widening who can decrypt it. **Removing** a recipient
is the same flow with their line deleted, but re-encrypting only stops *future* decrypts: anyone who
already decrypted still holds the password. Revoking for cause means rotating the password itself.

## Secrets — the GitHub App

The app pushes approved rulings to `vtes-biased/vtes-rulings` as a GitHub App. Two kinds:

**The private key (PEM)** — multi-line, kept vault-encrypted at
`ansible/roles/asgi_service/files/rulings_github_app.pem.vault`, decrypted by the `asgi_service` role
to `/etc/rulings/rulings_github_app.pem` on the host.

**The Client ID and Installation ID** — short scalars in `vault.yml`, edited with
`ansible-vault edit inventories/production/group_vars/all/vault.yml`. `vars.yml` shows how each is
wired into the app env:

```yaml
vault_db_password: "<the vtes-rulings db password>"
vault_session_secret_key: "<openssl rand -hex 32>"
vault_discord_webhook: "https://discord.com/api/webhooks/..."
vault_archon_client_secret: "<shown once at client registration>"
vault_rulings_github_client_id: "Iv23li..."          # the App's Client ID (JWT issuer)
vault_rulings_github_installation_id: "12345678"     # numeric
```

The installation id is the number in `https://github.com/settings/installations/<ID>`, or
`gh api /repos/vtes-biased/vtes-rulings/installation --jq .id`.

The `krcg-static` rebuild dispatch uses the **same App through a separate installation** — see
[vtes-ecosystem.md](vtes-ecosystem.md). Reaching a repo on another account required making the App
public, which is irreversible once installed there.

## Secrets — the archon OAuth client

Login is OAuth2 against archon; there is no local password. **Two archon deployments, two clients** —
separate databases, so a registration on one is unknown to the other:

| | archon | env var | client id | client secret |
|---|---|---|---|---|
| **prod** | `archon.vekn.net` | `ARCHON_URL` in `vars.yml` | `app_env.ARCHON_CLIENT_ID` | `vault_archon_client_secret` |
| **dev** | `archon.krcg.org` (beta) | none — `archon.py` defaults to it | `.env` | `.env` |

Register each where it belongs (the CRUD is IC-or-DEV: `POST /oauth/clients`, or the Developer
section of the archon profile page), with:

- **Redirect URI** — archon matches it **verbatim**, no prefix match. Give each client only its own:
  `https://rulings.krcg.org/login/callback` for prod (derived from `SITE_URL_BASE`),
  `http://127.0.0.1:5000/login/callback` for dev (the `just serve` bind, and the `SITE_URL_BASE`
  default).
- **Scope** — `profile:read` only. `user:impersonate` would hand us the whole archon API and we need
  nothing from it.
- **Client ID** — public: it rides in every consent URL the browser sees, so it sits plaintext in
  `vars.yml` (prod) and `.env` (dev).
- **Client secret** — displayed **once**. For prod, have `ansible-vault edit` open *before* you
  register.

Archon's production nginx proxies `/oauth` as an allowlisted prefix, so the handshake works there.
