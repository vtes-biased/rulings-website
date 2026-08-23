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
- Backrefs: a card names another card in a ruling, and that ruling shows on both pages.

**Propose, for a logged-in player.** Any archon member holding a VEKN id may open a proposal and
edit inside it: add/edit/delete a ruling on a card or a group, adapt a group ruling's text for one
card, create or edit a reference, create a group and manage its card membership and per-card
prefixes. A proposal has a name and a description, carries a consistency check, and is submitted to
Discord — which opens a thread on it.

**Approve, for an approver.** Anyone holding `IC` or `Rulemonger` on archon sees everyone's
proposals, reads the diff of one, and approves it. Approval merges the overlay, regenerates all
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

## Status (2026-08-23)

`rulings.krcg.org` **still runs v1.3.0**. `main` carries two landed epics — the card-token id
migration and the archon OAuth login — and the switch to them is a single hard one-way cutover. See
[`../board/cutover.md`](../board/cutover.md); read it before touching login, users, the rulings
format or the deploy.
