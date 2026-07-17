# #22 — Bug catalog (local browser-drive)

Booted the current Quart app locally (Postgres.app DB, cloned rulings repo, cards from VEKN) with
`QUART_TESTING=1` to bypass the VEKN password check, and drove it in Chrome.

## Confirmed WORKING (Chrome)
- Card search + autocomplete (`GET /api/complete`).
- Card view: image, text, rulings with reference badges.
- Login / logout (testing-mode bypass).
- Proposal creation — `POST /api/proposal` → 200.
- Ruling contenteditable editing: click-in reveals the icon/card-insert toolbar; blur saves —
  `PUT /api/ruling/100038/WUF4F3LL` → 200; row flips to MODIFIED with restore/delete controls.

## Bugs found
- **#23 (confirmed, root-caused):** proposal name/description Save fails. `saveProposal()` at
  `src/front/js/layout.ts:635` issues `PUT /api/proposal/approve` (405 → HTML error page → JS
  `Unexpected token '<' … not valid JSON`) instead of `PUT /api/proposal`. Copy-pasted from
  `approveProposal()` directly above it. One-line endpoint fix. Name/description never persist.
- **#30 (new):** the "You have active proposals waiting for submission" alert lists *every*
  unsubmitted proposal as an inline link with no cap — floods the whole viewport (hundreds of
  entries here). Built in `__init__.py` index route from `get_user_proposals`. Amplified by leftover
  test data but the missing cap is the real bug.
- **#31 (new, minor):** the red error toast from a failed fetch never auto-dismisses; it stays stuck
  on screen. `do_fetch` error path in `layout.ts`.
- **#32 (new, feeds #19):** the dev DB is full of orphaned `test-user` "Test" proposals — the test
  suite shares the real local Postgres and never cleans up. Reinforces the isolated-DB harness in #19.

## Not testable here
- **#24 (Firefox editing):** the Chrome-only automation tooling can't drive Firefox. Editing relies
  on `contenteditable`, the likely Firefox culprit; expected to be resolved by the Svelte rewrite
  (#9). Needs a manual Firefox pass to confirm the specific breakage.
- **Mobile:** `resize_window` didn't yield a faithful mobile render in the screenshot tool, so no
  concrete mobile findings were captured. #29 (mobile-first) proceeds on its own merit.

## Artifact left behind
Test proposal `5FVQCWON` (Alastor) with one edited ruling remains in the local DB — harmless; drop
if desired.
