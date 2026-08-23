# CLAUDE.md

A web app for curating the official **VTES** rulings: players draft **proposals**, an **approver**
approves one, and the change is serialised to YAML and pushed to `vtes-biased/vtes-rulings`, which is
the durable source of truth. FastAPI + Jinja on the read side, a JSON API and a Svelte editor island
on the write side.

## Three lifespans

Every artifact has exactly one. Anything you cannot assign a lifespan to is noise: delete it.

- **Code** — permanent. Source of truth for *how*.
- **[`wiki/`](wiki/index.md)** — standing. Source of truth for *what is* and *what was decided*.
- **Task context** — ephemeral. Plans, findings, reasoning. Dies when the task completes. An in-flight
  board line may park its elaborated contract in `board/<slug>.md`; that file dies with the line.

There is no other tracker. No plan document, no TODO file, no in-chat checklist, and **no TODO
comments in code** — discovered work goes through `/intake` or gets done now.

## Start here

1. **[`wiki/index.md`](wiki/index.md)** — the map. Every page is reachable from it. Read the pages
   your task touches *before* the code. [`wiki/dogmas.md`](wiki/dogmas.md) is the standard both
   ingress and egress check against.
2. **[`BOARD.md`](BOARD.md)** — what must change, in priority order. The goal is zero; completion is
   deletion. Continue a line before opening a new one.

Context lives in the wiki, asks live on the board. Never the other way round.

## The three loops

- **`/intake`** — ingress. Nothing reaches the board unchallenged: conflict, completability, scope,
  doc-impact. Use it whenever new work arrives and is not being done right now.
- **`/ship`** — take the top line, do the work, land the **trinity** in one unit (code changed +
  doc-impact wiki pages updated + board line deleted), then spawn `egress-reviewer`. This is how
  substantive changes land here.
- **`/upkeep`** — maintenance, every 20 shipped lines or monthly: wiki lint, board eviction, harness
  ratchet.

Egress review is by a fresh-context agent that has not seen the implementation conversation. Its
findings are **blocking** or **advisory**; after two rejection rounds, escalate to the human rather
than a third.

## Commands

`just` with no recipe lists them. The ones you will use: `just test`, `just lint`, `just typecheck`,
`just serve`, `npm run build`. Details, prerequisites, env vars, CI and deploy are in
[`wiki/operations.md`](wiki/operations.md).

## Commits

Trunk-based: straight to `main`, fast-forward, no feature branches. Describe the change itself. A
`Fixes #N` line above the trailers only for a real **GitHub** issue.

## Right now

`rulings.krcg.org` still runs v1.3.0. `main` carries the archon-login and card-token epics, and the
switch is a single hard one-way cutover — read [`board/cutover.md`](board/cutover.md) before touching
login, users, the rulings format or the deploy.
