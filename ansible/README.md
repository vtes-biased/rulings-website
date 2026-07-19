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

1. **DNS**: `rulings.krcg.org` → `152.228.170.51` (A record).
2. **Vault password** (see below) — decrypt it before the first deploy.
3. **Secrets** — fill `vault.yml` and drop in the GitHub App key (see below).

## Vault password

The production ansible-vault password is stored **in the repo, age-encrypted**,
decryptable only by the admins whose public keys are in `secrets/age-recipients.txt`.
Install [`age`](https://github.com/FiloSottile/age) first.
Once your key is added to recipients, you can decrypt the vault password into the git-ignored `.vault_pass`.

```bash
age -d -i ~/.ssh/id_rsa -o .vault_pass secrets/vault-pass.age
# ... run just deploy ...
```

### Adding a recipient

Recipients are the public keys in `secrets/age-recipients.txt` — one per line, either an
`ssh-ed25519`/`ssh-rsa` key (e.g. a line from `https://github.com/<user>.keys`) or an `age1…` key
from `age-keygen`. Editing the list doesn't re-key `vault-pass.age` on its own; **you must re-encrypt it**, 
so an existing recipient has to run this:

```bash
age -d -i ~/.ssh/id_rsa -o .vault_pass secrets/vault-pass.age   # 1. decrypt (existing recipient)
# 2. add the newcomer's PUBLIC key
echo 'ssh-ed25519 AAAA… alice' >> secrets/age-recipients.txt
age -R secrets/age-recipients.txt -o secrets/vault-pass.age < .vault_pass   # 3. re-encrypt to the new list
```

The password value is unchanged — you're only widening who can decrypt it; the newcomer can decrypt
once the re-encrypted `.age` is committed. **Removing** a recipient is the same flow with their line
deleted, but re-encrypting only stops *future* decrypts — anyone who already decrypted still holds
the password, so if you're revoking for cause, rotate the vault password itself.

## Secrets — where the GitHub App creds go

The app pushes approved rulings to `vtes-biased/vtes-rulings` as a **GitHub App**.
Two kinds of secret:

**1. The private key (PEM)** — multi-line, delivered as an ansible-vault file that the
`asgi_service` role decrypts to `/etc/rulings/rulings_github_app.pem` on the host.
It stays vault-encrypted at `ansible/roles/asgi_service/files/rulings_github_app.pem.vault`.

**2. The Client ID + Installation ID** — short scalars, they live in `vault.yml`
alongside the other secrets. Create/edit it with:

```bash
ansible-vault edit inventories/production/group_vars/all/vault.yml
```

and set these keys (see `vars.yml` for how they're wired into the app env):

```yaml
vault_db_password: "<actual db password for vtes-rulings db>"
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

If it fails on auth, the `deploy` user/key isn't authorized on gravelines yet.

## Deploy

```bash
just dry-deploy                 # --check --diff; review before applying
just deploy                     # deploy the latest GitHub Release
RELEASE_TAG=v0.9 just deploy    # pin a specific release
SOURCE=local just deploy        # build + deploy a local wheel (dev)
QUICK=1 just deploy             # artifacts-only (--tags app): wheel + unit, skip db/nginx
```
