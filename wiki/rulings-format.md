# The rulings YAML format

The `vtes-biased/vtes-rulings` repository is the durable source of truth. Three files under
`rulings/`: `references.yaml`, `groups.yaml`, `rulings.yaml`.

**The forever-format principle.** The database is a single self-sufficient YAML file, usable with a
text editor and no processing. Countless VTES resources have been lost to unmaintained databases and
impractical formats; the survivors are the simplest time-tested text standards. YAML over CSV
because a card has several rulings; YAML over JSON because someone must be able to pick it up
without context in twenty years. (Source: `vtes-rulings/README.md`, mirrored from
`repository.py:RULINGS_COMMENT`.)

Everything below follows from that: no fields, no normalisation, nothing that needs tooling to read.

## Keys

A ruling attaches to a card or to a group, keyed `<id>|<name>`:

- **Card** — the VEKN CSV integer id: `100015|Academic Hunting Ground`.
- **Group** — an id starting with `G`: `G00008|Permanent not replaced`. Groups are defined in
  `groups.yaml` as a set of cards, each optionally carrying a `prefix`.

A group id beginning with `P` is **pending** — it exists only inside a proposal and is renumbered to
a stable `G` id when the proposal is approved.

## A ruling entry

Usually a plain string. Four things live inside the text:

1. **Symbols** in brackets — `[pot]`, `[MERGED]`, `[1 CONVICTION]`. The vocabulary is
   `krcg.rulings.ANKHA_SYMBOLS`: inferior/superior disciplines, virtues, card types, and
   FLIGHT/MERGED/CONVICTION. Note `[viz]` is the Vision virtue, distinct from `[vis]` Visceratika.
2. **Cards** in braces, carrying the id like the keys do — `{100006|Abbot}`. The name inside a brace
   is the *disambiguated* one (`{200041|Alan Sovereign (ADV)}`) because a brace names a card mid-
   sentence. Editors type `{Abbot}`; `utils.normalize_cards` rewrites it to the id form on save.
3. **References** in brackets at the end — `[LSJ 20040518]`, resolved in `references.yaml`.
4. **Emphasis**, markdown-like: `**bold**`, `*italic*` (`utils.RE_EMPHASIS`).

**Names are as printed on the card**, not as filed in the VEKN CSV (`The Ankou`, not `Ankou, The`).
The id beside the name is what identifies the card, so the name is free to be restyled upstream. This
reverses an earlier decision that names should match the CSV — krcg 5.3 (2026-07-01) started storing
printed names and the serializer writes what krcg gives it.

### Reminders

A **reminder** restates official card text or a core rule — not a genuine ruling, needs no
discussion, and **may carry no reference**. It ends its text with a trailing `[REMINDER]` tag. The
tag is a text marker only; `models.RulingKind` is `RULING` (default) or `REMINDER`, and
`check_consistency`'s "at least one reference" rule applies to `RULING` alone.

Reminders and overrides are independent.

### Overrides

A group ruling may need different wording for a few cards in the group. That entry becomes a map —
the **only** reason an entry is ever a map:

```yaml
G00008|Permanent not replaced:
  - text: The permanent is not replaced. [LSJ 20040518]
    overrides:
      100015|Academic Hunting Ground: The hunting ground is not replaced. [LSJ 20040518]
```

The override replaces the **body text only**: same ruling identity, same shared references (an
override body carries no reference markers). It generalises `prefix`, which is the trivial case —
overriding just the leading icon, uniformly across all of a group's rulings.

Known limitation: a `{Card}` mentioned only inside an override body produces no backref, because
`get_backrefs` reads the base ruling's cards.

## References

`references.yaml` maps a reference id to a URL. The id is `SRC YYYYMMDD` (`LSJ 20040518`); the
source prefix is one of `krcg.rulings.RULING_AUTHORS`. Two validations, both in
`utils.check_reference`:

- the URL host must be in `utils.RULING_DOMAINS` — exactly `www.vekn.net`, `usenet.krcg.org`,
  `www.blackchantry.com`. The bare `vekn.net` and `blackchantry.com` are **not** accepted, and
  neither is `groups.google.com` nor `boardgamegeek.com`;
- the date must fall inside that author's Rules Director window. `RBK` (Rulebook) and `RTR` (Rules
  Team Ruling) have no window and carry no date; every other source does.

**The newsgroup lives at `usenet.krcg.org`.** 908 references cite
`rec.games.trading-cards.jyhad`, and pointed at Google Groups until Google stopped serving that
archive reliably; every one of them points at our own copy now, which is why `groups.google.com` is
no longer a reference domain. `/t/<ThreadId>/` is the thread and `#mN` the message, **counted from
the top of the thread** — a message inserted into a thread moves every anchor below it, so the
archive's message order is part of the contract, not a rendering detail. A citation with no `#mN`
means the thread survives and the cited reply does not. The same text heads `references.yaml`,
written from `repository.py:REFERENCES_COMMENT` on every approval.

The archive holds more than the newsgroup, whose own posts stop in 2010: a cited VEKN forum topic
the forum has since dropped is copied in beside them, which is how `ANK 20210529` still resolves,
and so are the fifty-seven BoardGameGeek threads L. Scott Johnson took part in, under
`/t/bgg-<ThreadId>/`. A thread copied from a forum keeps the number that forum gave each post, so
the four citations into those threads anchor on that number (`#6142361`) rather than on a
positional `#mN` — which is why `boardgamegeek.com` is no longer a reference domain either.

Nothing checks that the cited message's own date matches the reference id: the id carries the
**ruling's** date, and the message it points at is only its best surviving witness — sometimes a
later post quoting it. `vtes-rulings/scripts/check_rulings.py` checks a newsgroup citation for
thread existence and anchor validity — a positional anchor against the message count, a
forum-copied one against the thread's post numbers — and no more, and only a VEKN forum URL is read
back there to flag a mismatch. Reading a URL back to *propose* an id is a different job, and
`scraper.py` here does it for both the forum and the newsgroup archive.

**New `RBK` references cannot be created** — the rulebooks are a closed set, all already listed, so
`Manager.insert_reference` refuses one and the editor offers them from a select instead.

`scraper.py` derives a reference id from a pasted VEKN forum URL, and from a `/t/<thread>/#mN`
archive URL: `USENET_AUTHORS` maps the `class="who"` spelling the archive uses — several per
director, only some of them the `RULING_AUTHORS` full name — to a source prefix, and
`<time datetime>` gives the date. Only ever a **proposal**, so the editor leaves the id typable:
the cited post may be a director relaying an `RTR`, or quoting a ruling older than his own term.
It reads the positional `#mN` only, so an archive URL anchored on a forum-copied thread's post
number proposes nothing and the id is typed by hand. A proposal the editor never touched dies with
the URL it was read from — the next URL that proposes nothing blanks it, because an id left
standing beside a replaced URL writes a reference whose id and URL disagree, and `check_reference`
validates neither against the other.

Three answers are not errors and must stay **404**, not 400: an *archive* URL with no `#mN` to
read, an archive message by someone in no `USENET_AUTHORS`, and a site that will not answer. The
first two are legitimate citations and the third is an outage — none of them contradicts the URL,
and a 400 blanks *and locks* the editor's label field, which would leave the reference unaddable. A
400 is for the URL the archive does contradict: an unknown thread, an anchor past the last
message.

## The ruling uid

`uid = utils.stable_hash(text)` (shake_128 → base32), computed over the normalised text **with each
card token reduced to its bare id** (`{101565|Rebirth}` → `{101565}`) before hashing. So a card
rename never renumbers a ruling — and the uid is deliberately no longer derivable by eye from the
stored text.

Editing a ruling's text changes its uid; the proposal tracks the old one so a revert drops the
change cleanly. The uid is the `#r-<uid>` permalink anchor, and Discord threads link it.

## The format is krcg's

`utils.py` re-exports `ANKHA_SYMBOLS`, `RULING_AUTHORS`, `RE_RULING_REFERENCE`, `RE_CARD`,
`RE_REMINDER` and `RE_SYMBOL` from `krcg.rulings` rather than restating them. Same file, same font,
one owner: a new discipline or a new Rules Director arrives here with a krcg version bump.

## The docs exist in three places

`repository.py:RULINGS_COMMENT` is **authoritative**. The header of `rulings/rulings.yaml` is
generated from it on every approval, and `vtes-rulings/README.md` is a hand-maintained mirror. A
format change edits `RULINGS_COMMENT` in the same commit as the serializer, or the next approval
pushes a stale header back over the file. `REFERENCES_COMMENT` heads `references.yaml` the same way
and carries the same hazard: text hand-edited into either file upstream is deleted by the next
approval unless it lands in the constant too.
