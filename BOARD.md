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

- **archon-vibe: ship the consent fix.** `main` is 25 commits ahead of `origin/main` and the newest
  tag `v1.0.7` does not contain `105bdbf`. Decide what that release carries, tag it, deploy beta then
  prod. Until then every returning user's login loops. @lip only. Done: a second login through
  `archon.vekn.net` completes without looping. [[board/cutover.md]] step 1b
- **Ask on Discord that people submit any draft they care about**, so it reaches the queue and is
  judged on its merits during the drain. @lip. Done: posted. [[board/cutover.md]] step 2
- **Drain the in-flight proposals on live v1** — approve or discard every one. @lip. Done:
  `SELECT count(*) FROM proposals` returns 0 on gravelines. [[board/cutover.md]] step 3
- **Run the cutover window**: stop v1, `DELETE FROM users`, push the four `vtes-rulings` commits,
  `just release` and deploy. One-way. Done: `rulings.krcg.org` serves v2, a real archon login works,
  and `board/cutover.md` is deleted along with the links to it in `wiki/product.md` and `CLAUDE.md`.
  [[board/cutover.md]] steps 5–7
- **Audit `tests/` against the testing dogma.** 1937 lines in `test_api.py`, written before the
  policy. Done: every remaining test traces to a claim in `wiki/`, nothing mocks our own code, and
  the ones that don't are gone. [[wiki/dogmas.md#testing]]

<!-- cycles-since-upkeep: 1 -->
