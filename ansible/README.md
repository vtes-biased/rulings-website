# Deploy — rulings-website on gravelines

Ships the app onto the **server-setup-provisioned** `gravelines` host as a hardened
systemd service (single-worker hypercorn) behind an nginx/TLS vhost at
**rulings.krcg.org**, on a managed Postgres DB. server-setup owns the foundation
(base packages incl. Postgres/nginx/certbot, ssh/ufw/tuning, PG backups, Alloy); this
play only ships the app and consumes server-setup's `postgres_db` / `nginx_site` roles.
Deploy is **manual** (`just deploy`); CI only builds + attaches the release artifacts.

Ansible tooling comes from the repo-root project's `dev` group — no separate install,
the recipes call `uv run --project ..`. Run everything from this `ansible/` dir.

## One-time prerequisites

1. **DNS**: `rulings.krcg.org` → `152.228.170.51` (A record). Likely already set for the
   v1 app; certbot issuance in the deploy needs it resolving first.
2. **Vault password** (see below) — decrypt it before the first deploy.
3. **Secrets** — fill `vault.yml` and drop in the GitHub App key (see below).

## Vault password

The production ansible-vault password is stored **in the repo, age-encrypted**,
decryptable only by the admins whose public keys are in `secrets/age-recipients.txt`
(same list as the rest of the org). Create it once, then everyone with a listed key
can decrypt it:

```bash
# Create the password (first time only), age-encrypt it to the recipients, commit the .age:
head -c 32 /dev/urandom | base64 > .vault_pass          # a fresh random password
age -R secrets/age-recipients.txt -o secrets/vault-pass.age < .vault_pass
git add secrets/vault-pass.age                          # ciphertext — safe to commit
```

Day-to-day, decrypt it into the git-ignored `.vault_pass` (the deploy
recipes default `ANSIBLE_VAULT_PASSWORD_FILE` to it):

```bash
age -d -i ~/.ssh/id_rsa -o .vault_pass secrets/vault-pass.age
# ... run just deploy ...
rm -f .vault_pass    # git-ignored, but remove when done
```

Install [`age`](https://github.com/FiloSottile/age) first (`brew install age`).

## Secrets — where the GitHub App creds go

The app pushes approved rulings to `vtes-biased/vtes-rulings` as a **GitHub App**.
Two kinds of secret:

**1. The private key (PEM)** — multi-line, delivered as an ansible-vault file that the
`asgi_service` role decrypts to `/etc/rulings/rulings_github_app.pem` on the host:

```bash
# with .vault_pass present (see above):
export ANSIBLE_VAULT_PASSWORD_FILE=$PWD/.vault_pass
ansible-vault encrypt --output roles/asgi_service/files/rulings_github_app.pem.vault \
    ~/Downloads/rulings-bot.<...>.private-key.pem
git add roles/asgi_service/files/rulings_github_app.pem.vault   # encrypted — safe to commit
```

**2. The Client ID + Installation ID** — short scalars, they live in `vault.yml`
alongside the other secrets. Create/edit it with:

```bash
ansible-vault edit inventories/production/group_vars/all/vault.yml
```

and set these keys (see `vars.yml` for how they're wired into the app env):

```yaml
vault_db_password: "<any strong string; peer auth makes it vestigial>"
vault_session_secret_key: "<openssl rand -hex 32>"
vault_discord_webhook: "https://discord.com/api/webhooks/..."
vault_discord_server_id: "<discord server id>"
vault_rulings_github_client_id: "Iv23li..."          # the App's Client ID (JWT issuer)
vault_rulings_github_installation_id: "12345678"     # numeric — see below
```

**Getting the Installation ID**: open the App's installation on the org and read the
number in the URL `https://github.com/settings/installations/<INSTALLATION_ID>`, or:

```bash
gh api /repos/vtes-biased/vtes-rulings/installation --jq .id
```

## Step 0 — verify access + foundation (before deploying)

```bash
just ping                              # ansible ping as the deploy user
```

If it fails on auth, the `deploy` user/key isn't authorized on gravelines yet — fix in
`server-setup` (`add-admin.yml --limit gravelines`) before continuing. Once in, confirm
the foundation is current and note the v1 app's names/port so we replace it cleanly:

```bash
ssh deploy@152.228.170.51 '
  which uv; nginx -v; psql --version; systemctl status alloy --no-pager | head -3
  ls /etc/nginx/sites-enabled/                 # find the v1 rulings vhost
  systemctl list-units --type=service --state=running | grep -iE "rulings|krcg|timer|archon"
  sudo -u postgres psql -tAc "SELECT datname FROM pg_database WHERE datistemplate=false;"
  ss -tlnH | awk "{print \$4}" | sort -u       # confirm backend_port (8095) is free
'
```

If the v1 DB has in-flight proposals worth keeping, set `db_name`/`db_user` in
`vars.yml` to the existing DB name (the `postgres_db` role won't clobber an existing DB).

## Deploy

```bash
just dry-deploy                 # --check --diff; review before applying
just deploy                     # deploy the latest GitHub Release
RELEASE_TAG=v0.9 just deploy    # pin a specific release
SOURCE=local just deploy        # build + deploy a local wheel (dev)
QUICK=1 just deploy             # artifacts-only (--tags app): wheel + unit, skip db/nginx
```

After deploy: `curl -I https://rulings.krcg.org`, `systemctl status rulings`,
`journalctl -u rulings -f`. Remove the leftover v1 unit/vhost once the new one is
serving (its systemd unit + `/etc/nginx/sites-enabled/<v1>`), then reload nginx.

## Files

- `playbooks/deploy.yml` — the deploy play (postgres_db → asgi_service → nginx_site).
- `roles/asgi_service/` — app-specific role: wheel → uv venv → env + PEM → systemd unit.
- `tasks/` — shared `fetch_release.yml` (download the Release wheel) + `app_user.yml`.
- `vars/release_artifacts.yml` — which repo/tag to fetch, wheel glob.
- `inventories/production/` — host + `group_vars/all/{vars,vault}.yml`.
