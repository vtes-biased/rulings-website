#!/bin/sh
# ansible.cfg's vault_password_file: run, not read, so the vault password reaches ansible on stdout
# and never touches disk. sops takes the SSH key from SOPS_AGE_SSH_PRIVATE_KEY_FILE, else
# ~/.ssh/id_ed25519, else ~/.ssh/id_rsa (wiki/deploy.md).
exec sops decrypt --extract '["vault_password"]' "$(dirname "$0")/secrets/vault-pass.sops.yaml"
