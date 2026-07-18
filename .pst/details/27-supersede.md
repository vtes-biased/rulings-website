# #27 — Supersede group-ruling text per card

## Decision (locked)
A card may override the **body text** of a group ruling, while it stays the **same ruling** —
same identity, same **shared references**. Text override only (adapt pronouns / examples). This
**generalizes `prefix`**: prefix is the trivial case (override only the leading icon).

## Current model (context)
- `groups.yaml`: `group_nid → { card_nid → prefix }` (per-card value is today just the prefix string).
- `rulings.yaml`: `group_id → [ plain ruling strings ]`.
- `models.CardInGroup`: `uid, name, printed_name, img, state, prefix, symbols`.
- `proposal.Manager.get_rulings()` is the merge point: for each card in a group it currently yields a
  `Ruling` with `text = prefix + " " + ruling.text` and `symbols = ruling.symbols + card.symbols`,
  **keeping the group ruling's `uid` and `references`**. The override plugs in exactly here.

## The crux: granularity
Override is per **(card, group-ruling)** — a card adapts *some* of a group's rulings, not all, and
different rulings need different text. So it is richer than `prefix` (which is per-card, uniform
across all the group's rulings). The model must key overrides by ruling identity.

## Representation candidates (YAML must stay readable — decide in-ticket)
- **A. Co-locate with the base ruling (leaning here).** In `rulings.yaml` a group ruling may be a
  plain string (today) *or* a map: `{ text: "...", overrides: { <card_id>: "adapted text" } }`.
  Override sits next to the text it replaces — readable, no hash references.
- **B. Extend the group entry.** In `groups.yaml` the per-card value becomes `{ prefix, overrides:
  { <ruling_uid>: "..." } }`. Keeps rulings.yaml as strings but references ruling hashes in YAML — ugly.
- Lean **A**. Note this is the *same* "a ruling entry may be a structured map, not a bare string"
  schema move that #28 needs — **design the entry schema once, across #27 + #28.**

## Touch points
- `models.py` (CardInGroup / the group-ruling representation), `repository.py` load+serialize,
  `proposal.Manager.get_rulings` (apply override instead of prefix-prepend when present),
  the Svelte editor (#9) to author overrides, back-compat for existing plain-string rulings.
- References are untouched by design — they always come from the base group ruling.

## Resolved (implemented with #28)
- **Candidate A.** Override lives on the group ruling entry in `rulings.yaml`:
  `{text, overrides: {<card_id>|<printed_name>: "adapted body"}}` (card key uses the same
  `id|name` NID as groups.yaml, for readability). Stored in the model as `Ruling.overrides:
  dict[card_uid, text]`. The adapted text is **body-only** — no reference markers; refs are shared
  from the base ruling (the token editor already strips refs, so a saved override is naturally
  body-only).
- Effective card ruling (`Manager._effective_group_ruling`): if the card has an override, text =
  override, symbols/cards parsed from it, refs = base ruling's; else the existing prefix+base path.
  An override subsumes the prefix for that one ruling (prefix stays the trivial per-card case).
- **Edited on the card page** (index.html), not the group page — a card adapts *its* inherited
  group rulings (few), avoiding a cards×rulings matrix on a 75-card group. The inherited RulingCard
  gains "Adapt for this card" / "Reset to group text". Override save: `PUT
  /api/ruling/{group}/{ruling}/override/{card}` `{text}`; empty text clears (revert).
- `Manager.override_ruling` copies the base group ruling into the overlay carrying the override
  (state MODIFIED; dropped back to base when it matches again). `update_ruling` carries overrides
  forward across a text edit and includes them in its revert-to-base check.
- Effective card rulings carry the base ruling's `overrides` map so the island knows whether *this*
  card is overridden (shows Reset vs Adapt).
- Known limitation: a `{Card}` mentioned only inside an override body produces no backref
  (`get_backrefs` reads the base ruling's `cards`). Low impact; revisit if override-only mentions
  become common.
