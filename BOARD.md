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

- Push `newsgroup-archive` 48ad293 and `vtes-rulings` 61d252f — the handle annotation the scraper
  maps, and the four BoardGameGeek citations moved onto `#mN`. Until the Pages build behind the
  first, the live archive still says bare `Rulemonger` and those threads propose no reference id in
  production, as they did before; until the second, the file production reads still holds the post
  numbers nothing here reads any more. Chase @lip, 29 Aug.

<!-- cycles-since-upkeep: 9 -->
