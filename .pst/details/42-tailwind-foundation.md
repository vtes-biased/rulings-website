# #42 — Tailwind v4 foundation (approved design system)

Direction: **cold, modern, VTM-V5** — drawn from Black Chantry's current cards (near-black cold
grounds; desaturated blue/purple/teal/green; crimson only as the tiny capacity badge). No red, no
gilt, no warm parchment, no amber/orange. Approved via the design preview + icon proposals.

## Palette (→ Tailwind `@theme` `--color-*`)
Light (default; cool quasi-white document):
`--bg #E7E6EC · --surface #F7F6FA · --surface-2 #EDECF3 · --text #1B1C26 · --text-muted #6A6B7C · --hairline #D7D6E1`
Chrome (dark in both themes): `--chrome-bg #101017 · --chrome-2 #191922 · --chrome-text #E7E6EF · --chrome-muted #8D8DA1`
Accents: `--primary #6D55A6 (dusk amethyst) · --primary-bright #8B70C6 · --secondary #35818F (petrol) · --secondary-bright #4AA3B1 · --orchid #A25F97`

Dark:
`--bg #0F1016 · --surface #191A24 · --surface-2 #22232F · --text #E5E4EF · --text-muted #9C9CAF · --hairline #2C2D3A`
Chrome: `--chrome-bg #0A0A11 · --chrome-2 #14141D` (text/muted same)
Accents: `--primary #A488CC · --primary-bright #BBA2DD · --secondary #55B1C0 · --secondary-bright #70CAD8 · --orchid #C58FB8`

Overlay states (functional, cold, distinct from accents — separate `--color-state-*`):
Light: `original #82869A · new #4D997A · modified #6D82C6 · deleted #BB6D8D`
Dark:  `original #999DB2 · new #63BD97 · modified #8FA1E0 · deleted #D98CAD`
(Original steel-grey / New faded-green / Modified periwinkle / Deleted mauve-rose — no amber, no fire-red.)

## Type (→ `@theme` `--font-*`)
- Display: **Bricolage Grotesque** (700/800) — wordmark, headings, card names.
- Reading & UI: **Hanken Grotesk** (400/500/600/700, italic 400) — body, labels, rulings.
- Codes: **JetBrains Mono** (500) — reference citations, VEKN/group ids, dates.
- Glyphs: **Ankha VTES** (existing krcg webfont) — discipline/type symbols; keep `.krcg-icon`.
Self-host Bricolage/Hanken/JetBrains woff2 (no Google CDN in prod) via `@font-face`; inline discipline
glyphs use `--secondary` (petrol).

## Icon — "warded crest" (done, committed with this epic)
Petrol shield outline (`#58B0BF`) + amethyst fang (`#9B82D0`) on a `#12121A` tile. Assets under
`src/vtesrulings/static/img/`: `favicon.svg` (rounded master), `favicon.ico` (16/32/48),
`apple-touch-icon.png` (180, full-bleed), `icon-192.png`, `icon-512.png` (maskable). Plus
`static/site.webmanifest` and `<meta name="theme-color" content="#101017">`. Wired in `layout.html` head.

## Signature component
A ruling renders as a **record card**: thin left state-spine + a state chip (mono uppercase), inline
petrol discipline glyphs, accent-colored `{card}` refs, and monospace citation tags (`§`-free, a small
dot + `SRC YYYYMMDD`). Modern/restrained — no wax-seal or illuminated ornament.

## Build wiring — DONE (coexistence approach)
- `tailwindcss` + `@tailwindcss/vite` (v4.3.3) installed; plugin added to `vite.config.ts`; new `app`
  entry (`src/front/css/app.css`) → `css/app.css`, loaded in `layout.html` head after `layout.css`.
- `app.css` = **tokens + fonts only** for now: `@import "tailwindcss/theme.css"` + `@theme {…}` +
  4 self-hosted `@font-face` (Bricolage/Hanken variable via weight ranges; static Hanken-italic + mono).
  Preflight AND the utilities import are intentionally omitted so it stays inert against the still-
  Bootstrap pages (utilities generated off Bootstrap markup collide on `.collapse`, `.h-90`, …).
- Bootstrap (`layout.scss` → `css/layout.css`) still loads and still styles the unconverted templates.
- **Deferred to #43:** add `@import "tailwindcss/utilities.css"` + `@source` (templates become Tailwind);
  the `light-dark()` token cleanup + the manual toggle. **Deferred to #41:** re-add preflight, migrate
  the `.krcg-*`/krcg-modal/backref helpers + ankha/vtes-clans `@font-face` out of `layout.scss`, and
  drop `bootstrap`/`sass` deps.
- Default theme light; dark flips the semantic tokens via `prefers-color-scheme` + `[data-theme]`.

Preview artifacts (reference): design system + icon proposals were approved by the user.
