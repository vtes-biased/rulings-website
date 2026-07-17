# #28 — Two-kind entry model: RULING vs REMINDER

## Decision (locked)
A **closed two-value kind**, not a tag system:
- `RULING` — the default; **reference required** (unchanged behavior).
- `REMINDER` — "confirms something that should be clear from the card text + game rules, but players
  ask anyway"; **reference optional** (often a rulebook `RBK` ref, sometimes none).

Capped at two kinds for now. Add a third only if a real case appears — do not build general tags.

## Why it's a kind, not a label
The substantive change is *reference-optionality*. Today `check_consistency()` enforces
"At least one reference is required" for **every** ruling. REMINDER entries must be exempt. So the
model needs an explicit kind, and the consistency rule branches on it.

## The explicit-marker requirement
A REMINDER **cannot** be represented as "a ruling with the reference missing" — that is
indistinguishable from a malformed ruling. The kind must be an explicit marker in the YAML.

## Representation (design with #27)
Both #27 and #28 want a group/card ruling entry to optionally be a **structured map** instead of a
bare string. Design that entry schema once:
- Plain string ⇒ `RULING` (back-compat, the common case).
- Map ⇒ may carry `kind: reminder` and/or `overrides:` (#27).
- Bracket/brace namespaces are already taken (`[sym]`, `[REF]`, `{card}`), so a leading inline token
  is risky — prefer the structured-map marker (`kind: reminder`) which parses unambiguously and reads
  clearly. Confirm in-ticket.

## Touch points
- `models.py`: add `kind` (enum, default RULING) to the ruling model.
- `utils.build_ruling` / `repository.py` load+serialize: parse & emit the marker; `stable_hash` of
  the text still yields the uid.
- `proposal.Manager.check_consistency`: reference-required rule applies to RULING only.
- Svelte editor (#9): kind toggle; when REMINDER, reference field is optional.
