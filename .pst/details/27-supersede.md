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
