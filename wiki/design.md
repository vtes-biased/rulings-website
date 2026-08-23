# Design system

Approved by the human on a design preview, and standing. The concrete values live in
`src/front/css/app.css` as Tailwind v4 `@theme` tokens — one home per fact. This page holds the
decisions an agent cannot recover from reading hex.

## Direction

**Cold, modern, VTM-V5** — drawn from Black Chantry's current cards: near-black cold grounds,
desaturated blue / purple / teal / green, crimson only as the tiny capacity badge.

**Excluded, deliberately: no red, no gilt, no warm parchment, no amber or orange.** A restyle that
reaches for any of them is reversing a decision, not exercising taste.

Light is the default theme, a cool quasi-white document; dark flips the semantic tokens via
`prefers-color-scheme` and a `[data-theme]` override. Chrome (navbar, footer) stays dark in both.

Accents: dusk amethyst `--primary`, petrol `--secondary`, orchid. Card names in ruling text are
petrol and italic (`.krcg-card`). **Discipline and type glyphs are not** — `.krcg-icon` inherits the
surrounding text colour deliberately, because the glyph shape already carries the meaning. That
reverses the preview, which coloured them petrol.

## Overlay states are a functional colour set

`ORIGINAL`, `NEW`, `MODIFIED`, `DELETED` (see [proposals.md](proposals.md)) have their own
`--color-state-*` tokens, kept cold and deliberately distinct from the accents: steel-grey, faded
green, periwinkle, mauve-rose. **No amber, no fire-red** — the usual diff palette is exactly what
this rejects.

## Type

Four faces, by role:

- **Bricolage Grotesque** (200–800 variable) — display: wordmark, headings, card names.
- **Hanken Grotesk** (100–900 variable, italic 400) — reading and UI: body, labels, ruling text.
- **JetBrains Mono** (500) — codes: reference citations, VEKN and group ids, dates.
- **Ankha VTES** — discipline and card-type glyphs, via `.krcg-icon`.
- **VTES Clans** — clan icons, via `.krcg-clan`.

The first three are **self-hosted `woff2`**; the two krcg webfonts load from `static.krcg.org`, which
is ours. **No Google Fonts CDN in production** — adding one is a reversal, not an optimisation.

## Signature component

A ruling renders as a **record card**: a thin left state-spine plus a state chip (mono, uppercase),
inline discipline glyphs, petrol `{card}` references, and a monospace citation tag
(a small dot, then `SRC YYYYMMDD`). Modern and restrained — no wax seal, no illuminated ornament.

## Icon

A "warded crest": petrol shield outline with an amethyst fang on a near-black tile. Assets in
`src/vtesrulings/static/img/` (`favicon.svg`, `favicon.ico`, `apple-touch-icon.png`, `icon-192.png`,
`icon-512.png` maskable), plus `static/site.webmanifest` and the `theme-color` meta, wired in
`layout.html`.
