# #25 + #26 — Proposal diff page, hub, and Discord diff

Two epic-#5 children landed together (they share one backend diff): the on-site approver
diff view (#25) and the Discord adaptive diff + thread updates (#26). The user also asked to
fold in a mobile-first nav redo (drop the BCP logo) and turn the page into a proposal **hub**
(list / switch / start proposals), since a dedicated page makes that natural.

## Shared backend: the proposal diff
`Manager.diff() -> models.ProposalDiff` walks the overlay (`prop.references/groups/rulings`) and
returns a structured, render-agnostic diff consumed by BOTH the site (Jinja SSR) and Discord.

New `models.py` dataclasses:
- `ReferenceDiff(uid, url, source, state, old_url="")`
- `GroupCardChange(uid, name, state, prefix="", old_prefix="")`
- `GroupDiff(uid, name, state, old_name="", cards=[GroupCardChange])`  — NEW lists all cards; MODIFIED lists only changed cards
- `OverrideChange(card: NID, old="", new="")`  — per-card body-text override delta (pst #27)
- `RulingDiff(ruling: Ruling, previous: Ruling|None, overrides=[OverrideChange])`  — `previous` = base ruling for MODIFIED
- `TargetDiff(target: NID, is_group: bool, rulings=[RulingDiff])`  — rulings grouped under their card/group
- `ProposalDiff(references=[], groups=[], rulings=[TargetDiff])` + `is_empty`

State reconciliation mirrors `get_ruling` (MODIFIED→NEW when the base ruling vanished). ORIGINAL
overlay rulings are skipped. Group rulings show the raw group text (per-card effective text is a
group-page concern, not a diff concern).

## #25 — proposal.html (dedicated page + hub)
Route in `__init__.index()` (`elif page == "proposal.html"`). Sections:
- no user → login prompt.
- no active `?prop` → "Your proposals" list (switch) + "Start a new proposal" form.
- active proposal → editable name+desc (inline, continuous save), action buttons
  (Submit | Post update | Approve | Delete + Discord link), then the rendered diff (references /
  groups / rulings-by-target, reusing the `ruling_card` macro; MODIFIED shows a muted struck
  "was" line), then a switch-proposal list (own + all submitted, for approvers).
`proposal.get_proposal_url` now points at `/proposal.html?prop=` (used by the active-proposals
alert AND the Discord link).

`db.get_all_proposals(limit)` added for the approver switch list.

## Nav redo (folded in)
`layout.html`: drop the BCP logo; nav = Cards / Groups / Proposal(user-only, active dot) / Admin
on the left, theme + login/logout on the right; mobile-first flex-wrap. The lifecycle buttons
and the whole collapsible proposal **panel** and the proposal **modal** move OUT of layout onto
proposal.html. Card/group pages keep only the nav "Proposal" active indicator + per-item state dots.

## #26 — Discord adaptive diff + thread updates
`discord.py`:
- `format_diff(diff) -> str`: adaptive markdown, size-bounded to Discord's embed limit
  (~3800 chars); grouped bullets, per-ruling text truncated, trailing "…(N more)" when it overflows.
- `submit_proposal(prop, diff)`: initial message carries the diff (creates the thread).
- `post_proposal_update(prop, diff)`: posts the current diff to the existing thread.
- `proposal_approved(prop, diff)`: approval message includes the diff summary.
`api.submit_proposal` routes to submit vs post_update by `channel_id`; the frontend button is
"Submit" pre-submission, "Post update" after (same id/handler). `approve_proposal` builds the diff
before `merge()` and passes it to `proposal_approved`.

## Frontend
`chrome.ts`: keep start/submit/approve/delete handlers (ids preserved, buttons relocated); replace
the modal Save with debounced inline auto-save on `#proposalEditForm` name/desc; the same submit
handler serves Submit and Post update. `index.ts` quick-proposal button unchanged.

## Verify
`just fmt` + `just lint` + `just test` (discord test is `-m discord`, opt-in). Live Chrome pass:
proposal page diff (NEW/MODIFIED rulings, groups, refs) + hub/start view + card-page banner.
Reviewer subagent run before commit.

## Reviewer findings addressed (all fixed)
1. MODIFIED-by-override/kind only rulings no longer render a bogus struck "old" body — `diff()`
   gates `previous` on actual text change (`text_changed`). Unit test `test_diff_override_only_modified`.
2. Discord description+diff now budgeted under the 4096 embed cap via `discord._compose`
   (`format_diff` takes a `limit`).
3. Overrides surfaced on NEW rulings too (compute for any non-DELETED state).
4. `test_proposal_diff_page` discovers the base group ruling at runtime (no hard-coded hash id).
5. `db.get_submitted_proposals` filters `channel_id <> ''` in SQL (was fetch-then-filter under a cap).
6. State→color map deduped into a `state_class` macro (`_macros.html`), reused by proposal.html.
7. `proposal.ts` comment corrected. (groups.html keeps its own local `state_text` — pre-existing,
   out of scope.)
