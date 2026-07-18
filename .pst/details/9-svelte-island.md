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
JSON everywhere the island touches, except two cases handled:
- `POST /api/group` returned a **302 redirect** → now returns `asdict(Group)` JSON (done, #40); the
  add-group button reads the new uid and navigates.
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
- **#42** ✅ Tailwind v4 foundation: `@tailwindcss/vite` + main CSS (`@theme` tokens, fonts, `.krcg-*`). *(done)*
- **#43** ✅ Convert Jinja templates to Tailwind + retire Bootstrap CSS (layout/index/groups/admin/404). *(done)*
- **#36** ✅ SSR ruling macro (`_macros.html` + `ruling_body` filter); read pages render rulings server-side; client read-render retired. *(done)*
- **#37** ✅ Chrome bundle (`chrome.ts`): vanilla modal/collapse/toast #31 + keyboard autocomplete + nav/theme/login/proposal. Tooltips → native `title`; the icon-picker dropdown moved with the editor to the island. *(done)*
- **#38** ✅ Ruling token editor island: `island/` = `main.ts` (hydrates `#rulingsList` from SSR
  `data-ruling`), `RulingsEditor` (list + add), `RulingCard` (state chip/spine, restore/delete,
  coalesced debounced save), `TokenEditor` (contenteditable host + glyph picker + card autocomplete),
  `tokens.ts` (tokenize/serialize), `types.ts`. Shared `js/net.ts` extracted from `chrome.ts`
  (`do_fetch`/`displayError`/`debounce`/`postJSON`/`putJSON`) so the island reuses them without
  re-running chrome init. Verified live (Chrome): mount, read-only inherited rulings, add/type/save,
  `[sym]`/`{card}` insert round-trip, MODIFIED+ref-preserve, restore (cancels pending save), delete.
  Firefox **editing** verified good (#24, the plaintext-only reliance is gone). *(done)*
- **#39** ✅ Reference editing in the island: footer badge add/remove + drag-drop between rulings,
  and a `ReferenceModal` (search existing by URL/label via `/api/reference/search`, pick a rulebook
  ref, or create new via `POST /api/reference`). Refs live as `[uid]` markers re-appended on save;
  `SymbolEditor` exposes `editor.body`. Verified live (Chrome): rulebook add, label-search add,
  create-new, remove, drag-drop — DOM + server both. *(done)*
- **#40** ✅ Group editor island (`GroupEditor` on `#groupEditor`): name edit, card add
  (autocomplete)/remove/restore, per-card prefix token editor (`PrefixEditor`), group delete/restore.
  Extracted `SymbolEditor` (shared contenteditable core) + `CardSearch` (shared `/api/complete`
  autocomplete). `POST /api/group` → JSON; "+ New group" in chrome.ts. Mutations serialized through a
  promise chain (no save races); restore flushes pending edits first. Also fixed `update_group` to
  drop the overlay when a group is edited back to base. Verified live (Chrome): new group, rename,
  add/remove/restore card, prefix insert, group delete→restore. *(done)*
- **#41** ✅ Final retire: `layout.ts`/`layout.scss` deleted, bootstrap/@popperjs/
  bootstrap5-autocomplete/sass/bootstrap-icons/@types deps dropped, icons inlined as SVG (`icon()`
  macro). Re-asserted no Bootstrap remains: no JS import, nothing in package.json/node_modules, no
  `data-bs-*` (the `btn-*`/`row-item`/`nav-row` names are local Tailwind `@apply` components).
  Carry-forward (a) **resolved**: `bindCardHover()` in `chrome.ts` moved from one-shot per-element
  binding to **document-level delegation** (`closest(".krcg-card")` on mouseover/mouseout/click), so
  island-mounted spans (read-only bodies, editor chips, autocomplete-inserted chips) get krcg
  hover/click with no island coupling — spans are text-only so bubbling can't flicker. The rewrite
  also fixed a latent bug: the old handler called `outCard.call(this)` with no event, throwing on
  every SSR-span mouseout (krcg's own binding masked it). Carry-forward (b) **accepted, not deduped**:
  `CardSearch` vs chrome's `setupAutocomplete` differ across the framework boundary (navigate vs
  `onPick`, Svelte vs vanilla menu) and already share `debounce`; a shared fetch helper wouldn't earn
  its keep. Verified live (`TESTING=1` server, Chrome, card Abactor in edit mode): island mounts,
  bubbling mouseover on an island chip (which krcg never binds) opens the preview → delegation covers
  island spans; **mobile-first edit** at 454px has zero horizontal overflow, glyph picker + reference
  modal both fit. Firefox editing (#24) ✅ verified in #38. #30/#31 ✅. The ticket's literal "delete
  groups.ts/index.ts/admin.ts" is superseded — they stay as thin per-page Vite entries (templates
  reference them by stable name); the 1156-line `layout.ts` is the file that's gone. *(done — closes #9)*

## Landed together (43+37+36, then the #41 retire)
The read side is fully Tailwind and Bootstrap-free (CSS, JS, and the icon font). Edit mode is
intentionally editor-less until the island (#38–40): the old contenteditable ruling/group editors
were removed (which also deletes the #24 Firefox root cause), so a proposal shows rulings read-only
for now. `index/groups/admin.ts` are thin `chrome.ts` imports; icons are inline SVG via `_macros.html`.
#41 stays open as the epic's final gate: its remaining clauses (Firefox/mobile **editing**, close #9)
need the island. Firefox couldn't be automated here (Chrome-only tooling) — verify the read side
manually in Firefox when convenient; it uses only cross-browser-standard APIs.

## Suggested sequence
#35 done → **#42** (Tailwind foundation, before any template touches). Then #43 (convert templates)
+ #36 (ruling macro, Tailwind markup) + #37 (chrome behaviors) — all touch the shared templates, so
serialize where they overlap. Then #38 → #39 → #40 (the island proper). #41 last (dep cleanup +
cross-browser/mobile verification, then close).
