# #17 — approval → krcg-static rebuild dispatch

## Decisions
- **Fetch strategy: Option A, open-coded in krcg-static.** krcg-static's `load_cards()` builds
  cards from krcg's packaged CSVs but pulls rulings **live** from `vtes-rulings` via
  `krcg.rulings.load_online(cards)` instead of `load_local`. No new krcg feature/release — the
  bleeding-edge-rulings behavior is krcg-static-specific, so it lives there.
- **Trigger: GitHub App `repository_dispatch`.** On approval, after the push to `vtes-rulings`,
  rulings-website fires `POST /repos/lionel-panhaleux/krcg-static/dispatches`
  (`event_type: rulings-updated`) using the same App installation-token machinery as the push (#12).
  krcg-static's `data.yml` gains a `repository_dispatch: {types: [rulings-updated]}` trigger.
- **Install scope: the vtes-biased App is made PUBLIC and installed on the personal
  `lionel-panhaleux` account** (krcg-static lives there, not in vtes-biased). Cross-account install
  requires a public App; a private App can't reach a foreign repo. NOTE: irreversible — a public App
  can't be made private again once installed on another account.

## Manual GitHub-console prerequisites (owner)
1. App → Settings → Advanced → Danger zone → **Make public**.
2. Install the App on `lionel-panhaleux`, scoped to **krcg-static** only.
3. Grant the installation **Contents: write** (required by the create-repository-dispatch endpoint).
4. Note the new installation id for the krcg-static dispatch (distinct from the vtes-rulings one).

## Caveat
`raw.githubusercontent.com` has a ~5-min CDN cache, so a rebuild fired the instant after the push
may fetch a just-stale YAML; a short retry/delay in the build covers it.

## Alloy observability
Separate half of this ticket, untouched by the above.
