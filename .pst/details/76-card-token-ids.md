# Card tokens carry the card id

`{Abbot}` becomes `{100006|Abbot}` — the `<card_id>|<card_name>` shape the ruling
keys have always used. "Pip" in the request is that pipe.

## Why now

`rulings.yaml`'s own design notes, discarded-option 3:

> The **cards names** are the ones used in the VEKN CSV reference file. We could
> have opted for other alternatives, but we believe consistency with the existing
> reference is the stronger argument.

That is no longer true. krcg 5.3 (2026-07-01) stores names as printed — `The
Ankou`, not the CSV's filing form `Ankou, The` — and the serializer writes what
krcg gives it. Measured against upstream `GiottoVerducci/vtescsv@main`:

| | total | not an exact upstream CSV name |
|---|---|---|
| inline `{Name}` tokens | 395 distinct / 831 occurrences | **20 distinct / 38 occurrences** |
| ruling keys | 1295 | **46** |

The 20 tokens are 17 article-form (`The Rack`, `The Embrace`, `The Erciyes
Fragments`, `An Anarch Manifesto`…) plus `Theo Bell (G2 ADV)`, `Alan Sovereign
(ADV)` and `Helena (ADV)` — krcg `unique_name` disambiguators that were never CSV
names at all.

The keys diverge just as much but stay resolvable, because they carry the id.
That is the whole argument: the fix is already in the file, applied to keys only.

## Consumers of the token

- `krcg/rulings.py` — `RE_CARD = {[^}]+}`, `parse_cards` yields the inner string,
  `parse_ruling` does `cards[name]` against the fuzzy `CardDict`. Breaks on an
  id-bearing token. **krcg-static reads the YAML live** (`load_online`), so the
  first approval after migration would break its rebuild → krcg ships first (#77).
- `rulings-website/utils.py` — `parse_cards`, `normalize_cards`, `plain_text`.
  `normalize_cards` already rewrites every token on save, so it is the natural
  and only place the canonical form needs to be produced (#78).
- `vtes-rulings/scripts/check_rulings.py` — validates `id|name` on keys today,
  nothing on tokens (#79).
- `groups.yaml` prefixes carry symbols but **zero** card tokens — not in scope.

## Docs live in three places, one of them generated

1. `rulings-website/src/vtesrulings/repository.py` `RULINGS_COMMENT` — **authoritative**
2. `vtes-rulings/rulings/rulings.yaml` header — generated from 1 on every approval
3. `vtes-rulings/README.md` — hand-maintained mirror of 1

So 1 must change in the same commit as the serializer, or the next approval
pushes a stale header back over the migrated file. 3 follows 1.

## OPEN Q — decide before starting: what does the ruling uid hash?

`uid = utils.stable_hash(text)` over the normalized text, so rewriting tokens
renumbers **606 of 2302 rulings** (26%), breaking their `#r-<uid>` permalinks and
any Discord thread linking them. That churn is unavoidable; the question is
whether it can happen *again*.

1. **Accept the churn, keep hashing the raw text.** Simplest. But the next
   printed-name change — exactly what krcg 5.3 just did — renumbers rulings all
   over again.
2. **Hash the text with each token reduced to its id.** Same one-off churn now,
   then names can drift freely forever without touching a uid. Costs a second
   normalization step in front of `stable_hash`, and the uid stops being derivable
   from the stored text by eye.
3. **Normalize on edit only.** No churn, but the file holds both forms
   indefinitely and every consumer must accept both forever.

Option 2 is what the format change is *for* — 1 fixes today's mismatch and leaves
the mechanism that caused it intact. Not decided here.
