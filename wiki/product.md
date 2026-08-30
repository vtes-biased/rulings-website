# Product

**rulings.krcg.org** — a web app for curating the official VTES rulings. Authenticated players draft
**proposals** to add or edit rulings, groups and references; proposals are discussed on Discord; an
**approver** approves one, and the change is serialised to YAML and pushed to
`vtes-biased/vtes-rulings`, which is the durable source of truth.

## Capabilities

**Read, for anyone.**
- A page per card: its printed text, the rulings on it, and the rulings it inherits from every group
  it belongs to. Symbols render as glyphs, card names as hoverable links, references as badges.
- A page per group: the group's rulings and its card membership.
- A search box completing card names; groups are listed and browsable.
- The home page lists the latest rulings changes, newest first, each linking to the card or
  group page. Read off the `vtes-rulings` git history, not stored: a commit that only renames
  keys is not a change.
- Backrefs: a card names another card in a ruling, and that ruling shows on both pages.

**Propose, for a logged-in player.** Any archon member holding a VEKN id may open a proposal and
edit inside it: add/edit/delete a ruling on a card or a group, adapt a group ruling's text for one
card, create or edit a reference, create a group and manage its card membership and per-card
prefixes. A proposal has a name and a description, carries a consistency check, and is submitted to
Discord — which opens a thread on it.

**Approve, for an approver.** Anyone holding `IC` or `Rulemonger` on archon sees everyone's
proposals, reads the diff of one, and approves it. The diff marks a group target as a group
rather than a card of that name, and names the cards a group gained, lost or reprefixed, new
groups included. Approval merges the overlay, regenerates all
three YAML files, pushes them, posts to the proposal's Discord thread and triggers a `krcg-static`
rebuild.

## Deliberately not

- **No permanent storage outside the YAML.** The database holds in-flight proposals and one row per
  user. Approving drops the proposal.
- **No card editing.** Card data is krcg's, read-only here, referenced only.
- **No user management.** Identity, VEKN id and roles are archon's, rewritten on every login. There
  is no local password, no local role ladder, no admin page.
- **No name or email.** A user is a VEKN id.
- **No confirmation modals, no save buttons, no multi-step commit flows** — see
  [dogmas.md](dogmas.md).
- **No multi-worker deployment.** The rulings index lives in-process and is mutated on approval.

## Shape

A FastAPI server: Jinja-rendered pages for the read side, a JSON API under `/api` for the editor, and
a Svelte editor island (TypeScript, Tailwind, built by Vite) mounted on the pages that edit. Three
deliberately separated data sources, described in [proposals.md](proposals.md).

## Status (2026-08-30)

`rulings.krcg.org` runs **v1.5.0**, deployed 2026-08-30. Archon is the only way in — the legacy
`users` rows were deleted at the v1.4.0 cutover, so every account is created by its first archon
login — and every reference now cites `www.vekn.net`, `usenet.krcg.org` or `www.blackchantry.com`,
with the editor proposing the id from a pasted forum or archive URL. See
[rulings-format.md](rulings-format.md).
