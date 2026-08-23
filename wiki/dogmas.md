# Dogmas

Paradigms chosen by the human. Ingress challenges an incoming ask against this page; egress checks
the landed change against it. Overturning one is valid work; violating one silently is not.

## Data

**Nothing permanent lives outside the YAML.** The `vtes-rulings` files are the reference data. The
database holds in-flight proposals and one row per user; approving a proposal serialises it to YAML
and drops it. Keep the YAML simple and human-readable — see [rulings-format.md](rulings-format.md)
for the forever-format argument.

**Facts have one home.** Card data is krcg's, identity and roles are archon's, rulings are the YAML
repo's, and the ruling *format* is krcg's too (`utils.py` re-exports its regexes rather than
restating them). We copy a fact only where the copy is rewritten from the owner on every read
(`users.vekn`, `users.approver`).

## Edit UX

**Edit mode is live.** Direct editing plus continuous save, every action trivially revertible. No
confirmation modals, no submit or save buttons, no multi-step commit flows. Ergonomy through
simplicity and directness. This is what the overlay model buys — reverting is dropping an overlay
entry, so nothing needs guarding.

## Code

**Tight, local, KISS.** No patterns, abstractions or indirection for elegance's sake — they must earn
their keep. Don't write for a human reader's comfort; keep it terse for agentic workers.

**Locality first.** Co-locate what changes together; keep files readable in one pass. Extract a
module only behind an interface much narrower than what it hides. Layering ceremony — clean-arch,
hexagonal — is an anti-pattern here: it mass-produces shallow modules, which are pure token cost and
misuse surface.

**KISS means hazard-avoidance, not small diffs.** Big rewrites are cheap; the coding loop is agentic
and rewrites fast. What is expensive is *hazard* — non-local interdependency, behaviour not evident
where it lives, traps for a future agent without today's context. Prefer the design a fresh agent
can understand from the files in front of it. The amount of code needing a rewrite is never a reason
to defer.

**Repetition over false abstraction.** Similar-looking but causally unrelated code stays repeated.
Never factor on resemblance.

**Comments are for traps only.** The wiki holds the why, the code shows the how. A comment is
justified only by a subtle non-local constraint invisible at the point of reading. No narration, no
changelogs, **no TODOs** — discovered work goes through ingress or gets done now.

**Framework idioms as they come.** FastAPI dependency injection (including `Depends()` in argument
defaults), pydantic dataclasses for the domain, `os.getenv` read at point of use rather than a
settings object. Errors: raise, and let the exception handlers in `__init__.py` render them —
`ValueError` and `KeyError` are the data-error channel.

## Testing

**Few tests, high coverage of behaviour.** Test what the product does at its boundaries — the API,
the CLI, end-to-end nominal paths and the failure modes that matter — never how it does it. Agents
don't make local mistakes, they make non-local ones: unit tests of internals calcify implementation
and tax every change, while integration and non-regression tests catch what matters and survive
refactors.

- A test is the executable slice of this wiki: each must trace to a declared behaviour. One that maps
  to no wiki claim is evicted.
- **Mocks are banned by default** — a mock that mirrors the code tests the code against itself. Use
  real dependencies (a real Postgres, a real local git remote, temp files) or don't test that path.
  The current harness holds the line; keep it there.
- Exception: property-style tests for genuinely hazardous invariants (parsing, concurrency) — the
  same spots KISS flags.
- **Weakening or deleting a test is an egress rejection** unless the wiki-declared behaviour changed.

*(Adopted 2026-08-23.)*

## Dependencies

Prefer what is already here, then a few lines, then a dependency. krcg is the exception in the other
direction: anything about cards or the rulings format belongs upstream in krcg, not reimplemented
here. `just deps-check` reports in-range drift; `just update` takes it.

## Commits and branches

**Trunk-based**: commit straight to `main`, fast-forward, no feature branches. Two or three agents
may work parallel board lines on `main` — each claims its line, stays aware of siblings, keeps to its
own commits; imperfect commit isolation is acceptable when files overlap.

Describe the change itself in the message. **GitHub** issue numbers are the exception: when a commit
fixes a known GitHub issue, close it with a `Fixes #N` line just above the trailers.

## Human inflexion points

Interrupt the human only for: a dogma or paradigm choice (short option set plus a recommendation), an
irreversible or outward-facing action, a genuine change to product scope, or an egress deadlock after
two rounds. Everything else proceeds. HitL effort goes into the harness, not the code — the ratchet
turns a correction into a standing rule.
