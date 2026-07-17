# Epic #1 — Tech stack rework

## Goal
Replace the Quart + hand-rolled-TS stack with **FastAPI + Jinja SSR** for the read side and a
**Svelte island** for the proposal editor, without changing the north star: the durable artifact is
the YAML-in-git rulings repo; this app stays thin and disposable around it.

## The asymmetry this is built around
- **Durable source of truth:** the `vtes-biased/vtes-rulings` YAML repo (references/groups/rulings).
- **Read side is near-static** but must reflect an approved change *the instant it is committed* —
  so SSR from an in-memory `Index`, not a pre-built static site.
- **Only the editor is genuinely dynamic** (`layout.ts`, ~1156 lines of contenteditable + fetch +
  overlay state). That is the only thing that needs a framework.

## Chosen architecture
- **FastAPI** app. ASGI lifespan loads the krcg `CardMap`/`CardSearch` and clones the rulings repo
  into a temp dir, holding the parsed `Index` in memory (same model as today's Quart `while_serving`).
- **Jinja SSR** for public read pages (index/groups/admin) — crawlable, cache-friendly, fast.
- **Svelte island** mounted only on the authenticated proposal editor. Built with **Vite**
  (replaces Parcel). Talks to the existing `/api` JSON surface.
- **Single worker (hard constraint).** Read pages render from the in-memory `Index`; approval
  merges + pushes to git then reloads the `Index`. Two workers ⇒ divergent in-memory indexes + two
  checkouts racing to push. One worker is correct for a rules-team tool with a handful of editors,
  not a compromise. Enforced at the systemd/ASGI layer (see epic #2).

## Migration mapping (Quart → FastAPI)
- `quart.Quart` + `while_serving` → FastAPI app + `lifespan` context manager.
- `api.Blueprint` → `APIRouter(prefix="/api")`.
- `@proposal_update` / `@proposal_readonly` decorators → FastAPI dependencies (they load/lock the
  proposal via `db.POOL` and stash it on request state).
- `quart.g` / `quart.session` → request state + a session middleware (keep VEKN login + cookie now;
  Archon OAuth is a later epic).
- Template filters (`symbolreplace`, `cardreplace`, `newlines`) + `external_link` context processor
  → Jinja env globals/filters on the FastAPI templates instance.
- `db.py` psycopg async pool is framework-agnostic — reuse as-is.

## Scope of the Svelte island (#9)
Everything the current editor does: contenteditable ruling text, symbol/card/reference insertion &
autocomplete, the NEW/MODIFIED/DELETED overlay display, group editing. Design it **mobile-first**
(covers the editor half of the mobile epic). This rewrite is expected to resolve the Firefox
editing bugs (#24) since we drop the browser-specific `execCommand` reliance.

## Sacred (do not change here)
- The proposal → Discord → approve flow (hooks/UI may improve in epic #5, mechanism stays).
- The YAML format stays simple & human-readable (format *may* evolve for #27/#28, but stays plain).
- VEKN login stays for now.

## Children
#6 FastAPI scaffold + lifespan · #7 SSR pages + auth · #8 /api port · #9 Svelte island + Vite ·
#10 bump krcg · #11 single-worker index model.

## Suggested sequence
#6 → #7 → #8 (backend working on FastAPI, parity with today) → #9 (island) in parallel once #8's API
is stable → #10 early (unblocks everything) → #11 folds in with #6.

## Carry-forward: known bugs the rewrite must resolve (do NOT reintroduce)
Closed as superseded by this rewrite rather than patched on the retiring `layout.ts` — but they must
be actively handled/verified in the new frontend:
- **#24** — editing must work cross-browser (Firefox); the new editor (#9) must not depend on
  `contenteditable`/`execCommand` quirks. Verify in Firefox before closing #9.
- **#30** — the "active proposals" alert (SSR, #7) must **cap/paginate** the list; do not render an
  unbounded set of proposal links.
- **#31** — fetch-error surfacing (in the island / #9) must **auto-dismiss** (or be dismissible), not
  leave a stuck toast.
