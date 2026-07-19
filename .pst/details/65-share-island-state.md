# #65 — Share reactive group state across the editor-island mounts

Follow-up to #64 (author group-ruling overrides from the group page).

## Problem
The group page mounts **two independent Svelte islands** (`main.ts`), each hydrated from its own SSR
`data-*` JSON, with no shared reactive state:
- `GroupEditor` on `#groupEditor` — owns the member list + prefixes; mutates its own `group.cards`.
- `RulingsEditor` → `RulingCard` → `Adaptations` on `#rulingsList` — receives `members` as a
  **one-time snapshot** at mount.

Because the snapshot never tracks `GroupEditor`'s mutations, `Adaptations` drifts:
- A card **added** to the group this session does **not** appear in the "Adapt a card" picker.
- A card **removed** this session **still** appears; adapting it 400s per keystroke (backend
  membership check in `proposal.override_ruling`) and renders its raw uid (`byUid.get(uid)?.name ?? uid`).
- Rules out a live "adapted" chip in the member list (would need the overrides map, which lives in
  the other mount) — deferred in #64 for the same reason.

Only a full page reload currently reconciles them.

## Also (user ask): reset on proposal switch
A single shared source of truth gives **one place to reset** when the active proposal changes.
Today proposal switching goes through a full navigation (`?prop=…`) that remounts everything, so
state resets for free — but any future in-place proposal switch, or just cleaner teardown, wants a
single `reset(seed)` entry point rather than re-seeding two mounts.

## Direction (decide in-ticket)
- **A. Shared rune module** — a `groupStore.svelte.ts` holding `$state` (the group: cards/prefixes,
  and ideally the rulings' overrides map) that both `GroupEditor` and `Adaptations` import. `main.ts`
  seeds it once from the SSR JSON; `reset(seed)` re-seeds on proposal change. Minimal; idiomatic
  Svelte 5 cross-mount state. Leaning here.
- **B. One parent mount** — wrap `#groupEditor` + `#rulingsList` under a single island so the two
  become child components sharing props/context. Cleaner data flow but a bigger template/SSR reshape
  (the two live in different template regions with a static `<h3>Rulings</h3>` between them).

Lean **A**: smallest change that fixes the drift and yields the single reset point. Whichever wins,
membership mutations in `GroupEditor` must flow to `Adaptations`' `available`/picker reactively, and
`byUid` must resolve names for any card still referenced by an override.

## Touch points
`src/front/island/main.ts` (seed/reset), `GroupEditor.svelte` (read/write shared group),
`RulingsEditor.svelte` + `Adaptations.svelte` (drop the `members` prop snapshot, read shared state),
possibly a new `*.svelte.ts` store. No backend change.

## Closes the #64 limitations
Removes the "members SSR snapshot" comment/caveat in `Adaptations.svelte`; re-enables the deferred
member-list "adapted" chip as an easy add once the overrides map is shared.
