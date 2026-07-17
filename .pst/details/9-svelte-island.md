# #9 — Svelte editor island + Vite build

Retire `layout.ts` (1156 lines) + `groups.ts` (373) + Parcel. Split the frontend into an
**SSR read side** and a **Svelte editor island** mounted only in edit mode. Last open child of
epic #1.

## Three decisions (locked)
1. **Read-side ruling rendering moves to Jinja SSR.** Today rulings render client-side
   (`displayRulingCard`) even for anonymous readers; only card text is server-rendered. The macro
   resolves `[symbol]`→glyph span, `{Card}`→card span, and pulls `[REF]` out of the body into
   footer badges — same data the ruling dict already carries (`symbols`/`cards`/`references`, each
   with a `.text` marker). Read pages become crawlable; the island handles **edit only**.
2. **Structured token editor** for ruling text (and group-card prefixes). Model text as a token
   list (plain-text segments / symbol chips / card chips); Svelte renders editable segments +
   non-editable chips. No `contenteditable=plaintext-only` / `execCommand` — that reliance is the
   Firefox #24 bug. Serialize tokens back to the `[sym]`/`{Card}`/`[REF]` text format on save.
3. **Drop Bootstrap for Tailwind CSS v4.** Whole frontend (Jinja templates + Svelte island) styled
   with Tailwind v4 via `@tailwindcss/vite` (CSS-first `@theme` config, mobile-first). Bootstrap's
   JS behaviors (modal / dropdown / collapse / toast / tooltip) and `bootstrap5-autocomplete` are
   replaced by tiny vanilla/Svelte components — no framework JS. Keep the ankha/krcg webfonts and
   the `.krcg-*` helper classes; bootstrap-icons webfont may stay short-term (standalone, not the
   framework) or be swapped for inline SVG icons later.

## Target shape
- **SSR (all users):** index/groups/admin Jinja, incl. the new ruling macro. krcg.js (external,
  `static.krcg.org/web/krcg.js`) still powers `.krcg-card` hover on server-rendered spans.
- **Chrome bundle (every page, small vanilla/TS):** nav-active, card+user search autocomplete,
  login/logout, proposal modal actions, krcg hover glue, toasts (dismissible/auto — #31).
- **Editor island (Svelte, edit mode only — `proposal` present):** ruling token editor +
  references + group editor. Mobile-first. Mounts on `#rulingsList` / `#groupDisplay`, hydrating
  from the `data-*` JSON the SSR emits (or a fetch).
- **Build:** Vite replaces Parcel (done, #35). Entry points: chrome bundle, island, Tailwind CSS
  entry. Output to `src/vtesrulings/static/dist/` (stable names `js/{index,groups,admin,island}.js`,
  `css/layout.css`; shared chunks + fonts hashed). `just serve` runs `vite build --watch` (pm2) +
  hypercorn; `just release` builds via Vite.

## API surface (from api.py map)
JSON everywhere the island touches, except two cases to handle:
- `POST /api/group` returns **302 redirect** → change to return `asdict(Group)` JSON (ticket #40).
- `DELETE /api/ruling/{t}/{r}` returns **empty 200** (no body) when a NEW ruling is fully removed;
  otherwise `asdict(Ruling)`. Handle empty-body.
Proposal "select" is bound by the `?prop=` query param on page load (`__init__.py:182`), not by any
api endpoint — the island always runs inside an already-selected proposal, so no change needed.
Write endpoints accept JSON / form / text-plain JSON bodies (`get_params`, api.py:41).

Key response shapes: `Ruling{uid,target:NID,text,state,symbols[{text,symbol}],references[Reference+text],cards[BaseCard+text]}`,
`Group{uid,name,state,cards[CardInGroup{...,state,prefix,symbols}]}`, `Reference{uid,url,source,date,state}`.
`State` = ORIGINAL/NEW/MODIFIED/DELETED.

## Carry-forward bugs the rewrite MUST resolve (do not reintroduce)
- **#24** Firefox editing — solved by the token editor (no plaintext-only contenteditable). Verify in Firefox.
- **#30** active-proposals cap — already SSR-capped (`ACTIVE_PROPOSALS_CAP`). Verify island doesn't regress.
- **#31** fetch-error toast — must auto-dismiss / be dismissible, not stick.

## Sacred (unchanged)
proposal → Discord → approve flow; YAML-as-forever-format; VEKN login. The overlay merge lives in
`proposal.Manager` (backend) — the island is a thin JSON client over `/api`, no overlay logic moves
to the front.

## Children (parent:#9)
- **#35** ✅ Vite+Svelte scaffold, Parcel retired, build/serve wired. *(done)*
- **#42** Tailwind v4 foundation: `@tailwindcss/vite` + main CSS (`@theme` tokens, fonts, `.krcg-*`); drop bootstrap/sass from the CSS entry.
- **#43** Convert Jinja templates to Tailwind + retire Bootstrap CSS (layout/index/groups/admin/404).
- **#36** SSR ruling macro; read pages render rulings server-side; drop client read-render.
- **#37** Chrome bundle (Tailwind + vanilla/Svelte modal/dropdown/collapse/tooltip/toast #31 + autocomplete).
- **#38** Ruling token editor island (symbol/card insert, overlay, restore/delete, save).
- **#39** Reference editing in the island (footer badges + reference modal).
- **#40** Group editor island (name/cards/prefixes) + `POST /group` → JSON.
- **#41** Final retire: delete old TS, drop bootstrap/@popperjs/autocomplete/sass deps; verify #24/#30/#31 + mobile; close #9.

## Suggested sequence
#35 done → **#42** (Tailwind foundation, before any template touches). Then #43 (convert templates)
+ #36 (ruling macro, Tailwind markup) + #37 (chrome behaviors) — all touch the shared templates, so
serialize where they overlap. Then #38 → #39 → #40 (the island proper). #41 last (dep cleanup +
cross-browser/mobile verification, then close).
