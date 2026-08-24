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

- **Silence the yamlfix deprecation warning** in `_commit_index`: pass `dry_run=False`, whose write
  path is identical and whose return value we already discard. One permanent known warning trains
  everyone to skim the warnings block, and the next real one hides there. Done: `just test` reports
  no warnings summary.
- **Pin the frontend deps.** `package-lock.json` has been gitignored since the scaffold commit, so
  CI's three `npm install`s resolve fresh and the bundle v1.4.0 serves cannot be rebuilt from its
  tag. Un-ignore it, commit it after a `just update` so the pin is current rather than stale, move
  CI to `npm ci` and `just update` to `npm update`. Done: `package-lock.json` is tracked, no workflow
  calls bare `npm install`, and `just deps-check` reads the lockfile. [[wiki/operations.md]]
  [[wiki/dogmas.md]]

<!-- cycles-since-upkeep: 6 -->
