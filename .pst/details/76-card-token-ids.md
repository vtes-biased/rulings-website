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

## DECIDED — the uid hashes tokens reduced to their id

`uid = utils.stable_hash(text)` over the normalized text, so rewriting tokens
renumbers **606 of 2302 rulings** (26%), breaking their `#r-<uid>` permalinks and
any Discord thread linking them. That one-off churn is unavoidable — the stored
text changes, so the hash does.

**What is avoidable is it happening again**, and that is the call: before hashing,
reduce each token to its id (`{100807|Rebirth}` -> `{100807}`); the stored text
keeps the name. Names can then drift forever — the next krcg rename, another
printed-name correction — without renumbering a single ruling. The uid stops
being derivable from the stored text by eye, which is the price.

Implemented in #78, in front of `stable_hash` in `build_ruling`. #79's migration
pass must run against that, or every ruling it rewrites gets a uid that the app
then disagrees with.

Rejected: hashing the raw text (pays the permalink cost and leaves the coupling
that caused the problem, making this a patch rather than a fix), and normalizing
on edit only (no churn, but the file carries both forms indefinitely and every
consumer must accept both forever — against the forever-format principle).
