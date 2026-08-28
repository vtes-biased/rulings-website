# Board

What must change. The goal is zero. **Completion is deletion** — no closed state, no archive; git
history is the record. Context lives in [`wiki/`](wiki/index.md), never here: a line that cannot be
completed is documentation, and belongs on a wiki page instead.

**Order is priority**, and priority is decided by these rules, top down:

1. **Blocks someone else** — another person, another repo, another line.
2. **User-visible breakage.**
3. **User-visible feature.**
4. **Internal cleanup.**

Ties break to the smaller line. An item waiting on someone is not a state: it is a dated
follow-up ("chase @lip, 12 Sep"), owned by whoever wrote it.

---

- **Propose the reference id from a pasted `usenet.krcg.org` URL**, as `scraper.py` does for VEKN
  forum URLs: `/t/<id>/#mN` → that message's `<time datetime>` and `class="who"` author, mapped to a
  source prefix (the archive writes both `LSJ` and `L. Scott Johnson`). Server-side only —
  `api.py:search_reference` gains the branch, `ReferenceModal` already takes `computed_uid`. The id
  stays editable and nothing is checked against it: the id is the ruling's date, the post only its
  witness (`wiki/rulings-format.md`). Done: the endpoint returns `computed_uid` for a `#mN` URL and
  400 for an unknown thread or out-of-range anchor.

<!-- cycles-since-upkeep: 8 -->
