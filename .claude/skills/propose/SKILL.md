---
name: propose
description: The weekly rulings curation loop — harvest and critically evaluate rulemonger feedback on open proposals on rulings.krcg.org, draft a thematic batch of 6–8 rulings through a fresh-context gatekeeper, and compact lessons into the bounded style guide below. Runs without owner pre-review before submission to the rulemongers.
---

# /propose — self-improving rulings curation loop

Run weekly in two phases (plus monthly compaction during `/upkeep`). Proposals go straight to the
rulemongers on Discord without manual pre-review by the owner, unless rulemongers deadlock or
feedback contradicts the cited Rules Director.

---

## Phase 1: Harvest & Critically Evaluate Feedback

All calls to `https://rulings.krcg.org/api/...` are **HTTPS-only (zero SSH)**. Decrypt the static
bot Bearer token once at the start of the run:

```shell
API_TOKEN=$(sops decrypt --extract '["api_token"]' ansible/secrets/api-token.sops.yaml)
```

Pass `-H "Authorization: Bearer $API_TOKEN"` on every authenticated call, plus `-H "X-Proposal: <uid>"`
on proposal-scoped calls (`/api/proposal` PUT/DELETE/submit, `/api/reference`, `/api/ruling/...`,
`/api/group/...`, `/api/check-consistency`). The bot token is strictly non-approver: it can only
list, inspect, edit, submit, and comment on its own proposals.

1. **Read open proposals and their Discord threads** via the HTTPS API:
   - `GET https://rulings.krcg.org/api/proposal` lists our open proposals (`uid`, `name`,
     `description`, `channel_id`, and `groups`/`rulings`/`references` counts).
   - For each proposal, `GET https://rulings.krcg.org/api/proposal/{uid}` returns the full overlay
     and computed `diff`.
   - For each submitted proposal (`channel_id` non-empty), read its Discord thread messages via
     `GET https://rulings.krcg.org/api/proposal/{uid}/comments?limit=50` (returned oldest-first with
     `author`, `bot`, `timestamp`, `content`, and `embeds`).
   - Also check recent commits in `vtes-biased/vtes-rulings` (`gh api repos/vtes-biased/vtes-rulings/commits?per_page=5`
     or `git log -p -n 5` on a local clone) to see if an approver edited our wording before
     approving a previous proposal.
2. **Critically evaluate every comment — do NOT treat rulemonger remarks as unquestionable gospel:**
   - Rulemongers can disagree with each other, misread a card, or suggest wording that contradicts
     the Rules Director's post.
   - Always cross-check feedback against:
     1. the cited Rules Director post (`[ANK ...]`, `[LSJ ...]`, `[PIB ...]`, `[RTR ...]`) via
        `primogen`'s `vtes_rulings_archive`;
     2. the exact card text and every existing card + group ruling via `primogen`'s `vtes_cards` or
        `GET https://rulings.krcg.org/api/card/<id>`;
     3. the rulebook via `primogen`'s `vtes_rules_search` / `vtes_rules_read`.
   - **When feedback is valid** (editorial tightening, spotting an existing duplicate or group
     ruling, pointing out it's pure card text, flipping to a clearer negative/exception case):
     - Apply the edits to `https://rulings.krcg.org/api/...` with `Authorization: Bearer $API_TOKEN`
       and `X-Proposal: <uid>`.
     - Run `GET /api/check-consistency` (which also prunes orphaned new references), then
       `POST /api/proposal/submit` to post the `— updated 🔄` embed to the Discord thread.
     - Post a short summary comment to the thread via
       `POST https://rulings.krcg.org/api/proposal/{uid}/comments` (`{"content": "..."}`) noting how
       the feedback was applied.
     - Distill any generalizable lesson into the Style Guide below (respecting its line budget).
   - **When feedback contradicts the Rules Director's ruling or two judges disagree:**
     - Do **not** corrupt the proposal or add a contradictory rule to the Style Guide.
     - Post a polite clarification via `POST https://rulings.krcg.org/api/proposal/{uid}/comments`
       quoting the exact Rules Director post and link, or surface the deadlock to the owner.

---

## Phase 2: Draft → Fresh-Context Gatekeeper

1. **Backpressure check:**
   - From `GET https://rulings.krcg.org/api/proposal`, count our open submitted proposals
     (`channel_id != ""`) and sum their `rulings` counts.
   - If there are **more than 2 open batch proposals** or **more than 12 open ruling changes** of
     ours awaiting review, **propose 0 new rulings this week** — stop after Phase 1.
   - Also delete any unsubmitted draft (`channel_id == ""`) we abandoned (`DELETE /api/proposal`
     with `X-Proposal: <uid>`) so drafts never accumulate.
2. **Candidate selection (6–8 items, one thematic batch):**
   - Pull a small thematic batch of 6–8 candidate rulings (from `../primogen` `[M:rulings]` needs or
     `primogen audit -since 2017-01-01 -twda`).
   - For each candidate target card, read `GET https://rulings.krcg.org/api/card/<id>` (or
     `vtes_cards`) in full: **printed card text**, **every existing card ruling**, **every inherited
     group ruling**, and **the full archive thread** around the cited post.
3. **Spawn a Fresh-Context Gatekeeper subagent:**
   - Before touching `rulings.krcg.org`, pass each candidate to a fresh subagent that has **not**
     seen the drafting motivation. Give it **only**:
     - the card's printed text, existing card rulings, and inherited group rulings;
     - the quoted Rules Director archive post(s) and URL(s);
     - the proposed action (`new` or `modify <ruling_uid>` on card or group) and draft text;
     - the **Style Guide** section below.
   - The gatekeeper's mandate is to **kill, merge into an existing ruling, or shrink** every draft
     against Gate 1 and Gate 2. Drop or rewrite anything the gatekeeper rejects before creating the
     proposal on `rulings.krcg.org`.
4. **Create, verify, and submit:**
   - Create the proposal (`POST https://rulings.krcg.org/api/proposal` with `name` and
     `description`), then pass `X-Proposal: <uid>` on subsequent calls: add references
     (`POST /api/reference` — always use `https://usenet.krcg.org/t/vekn-<TopicId>/#m<N>` or
     `www.vekn.net` / `www.blackchantry.com`, no leading/trailing whitespace), add/update rulings,
     run `GET /api/check-consistency` (must return `[]`), and `POST /api/proposal/submit`.

---

## Phase 3: Monthly Compaction (during `/upkeep`)

To prevent context bloat and prompt degradation, the **Style Guide** below is strictly bounded to:
- **At most 8 core rules** (Gate 1 + Gate 2 combined).
- **At most 10 `Bad → Good (Why)` examples**.

When a new lesson arrives from Discord feedback or an approver's edit before approval:
- Merge it into an existing rule or replace a weaker example you no longer get wrong.
- Never exceed 8 rules or 10 examples; git history (`git log -p .claude/skills/propose/SKILL.md`) is
  the raw historical log.
- Reject one-off or contradictory preferences that do not generalize across cards.

---

## Style Guide (Bounded: Max 8 Rules, Max 10 Examples)

### Gate 1 — Less is More (Should this new ruling exist at all?)

1. **No card-text or bare-rulebook restatements:** If printed card text or a basic core rule
   already states the outcome unambiguously, **kill the ruling** (use `[REMINDER]` only for
   notorious tournament traps).
2. **Never duplicate an existing card or group ruling:** Check every ruling on the card *and* every
   group the card belongs to. If an existing ruling already covers the mechanic in different words,
   **kill the new ruling** (or `modify` the existing ruling / append the reference token if it adds
   scope).
3. **Modify a group ruling instead of adding a card ruling:** When a clarification applies to a
   shared mechanic already tracked by a group (e.g. `G00071|After Combat Ends`,
   `G00026|Immune to damage`), `modify` the group ruling rather than adding a one-off card ruling.
4. **Format tokens strictly:** Prepend discipline/cost prefix symbols (`[mel]/[MEL]`, `[DOM]`) when
   the ruling applies to specific levels; wrap every card mention in `{Card Name}`; put all
   `[SRC YYYYMMDD]` and `[RBK ...]` references at the end.

### Gate 2 — House Style (How is it written?)

5. **Outcome first, one short reason clause at most:** State what can or cannot happen directly.
   Include at most one brief clause (`"...since the combat itself has the press"`) when the reason
   clarifies scope. Drop redundant consequences (`"and combat ends"`, `"or outside combat"`).
6. **Never quote card text, rulebook text, or "the Golden Rule":** Say `"by card text"` or
   `"This takes precedence over the rulebook rules on queued combat. [RBK ...]"` instead of quoting
   sentences from the card or naming the Golden Rule.
7. **No cross-card analogies:** On Card A, never open with `"Unlike {Card B}, ..."` unless Card B is
   the direct interacting card in the situation being ruled on. State how Card A works on its own.
8. **State the exception / negative case:** When a card follows its normal rule except in a notable
   interaction, state the exception where it *cannot* be used rather than restating the default
   positive rule.

### Calibration Examples (`Bad → Good (Why)`)

1. **Cats' Guidance** — *Pure card text (Rule 1)*
   - **Bad:** `new [ani] Cannot be played if there was no block (eg. after a rush combat). [ANK 20250716]`
   - **Good:** *(Withdrawn)* — Card text already states `"Only usable by a locked vampire who has blocked, after block resolution."`
2. **Foreshadowing Destruction** — *Already covered on the card (Rule 2)*
   - **Bad:** `new [DOM] If another bleed modifier (eg. {Conditioning}) was legally played while the target had 10 or more pool and the target later has 9 or fewer pool during the action (eg. after a bounce or pool loss), both modifiers apply. [ANK 20191024]`
   - **Good:** *(Withdrawn)* — Existing ruling `4BC3FFKE` already explains that playing it at 10+ pool does not count against the limit and leaves a lingering `+3 bleed` if the target drops to 9 or fewer.
3. **Form of Mist / After Combat Ends** — *Group modification over misleading card ruling (Rule 3)*
   - **Bad:** `new` on *Form of Mist*: `[PRO] Cannot continue the action while there is a pending queued combat (eg. {Hedonism} or {Psyche!})...`
   - **Good:** `modify` group `G00071|After Combat Ends`: `If the combat continues or another combat is queued, the after combat effect does not happen/is not usable (e.g. {Psyche!}, {Telepathic Tracking}, {Hedonism}). [RTR 20020501] [LSJ 19980109] [ANK 20250613]` — When another combat is queued, we are not yet "after combat", and the group ruling already covers this for all members.
4. **Obedience** — *Negative exception over positive default (Rule 8)*
   - **Bad:** `Can be played by an unlocked older vampire to avoid a new combat queued after a preceding combat, if the opponent is still the acting vampire. [LSJ 19991025] [ANK 20250710]`
   - **Good:** `Cannot be used to cancel a combat queued by {Hedonism} or {Siren's Lure}, as it is not entering combat with an acting minion. [LSJ 19991025] [ANK 20250710]` — Entering combat with the acting vampire is already card text; the non-obvious trap is that *Hedonism* / *Siren's Lure* pit the blocker against a non-acting vampire.
5. **Siren's Lure** — *No quoted card text, no "Golden Rule", cite RBK (Rule 6)*
   - **Bad:** `[mel]/[MEL] Card text ("After the action resolution, this vampire and the blocking minion enter combat") takes precedence over the general queued-combat rule by the Golden Rule. [ANK 20250614]`
   - **Good:** `[mel]/[MEL] The new combat starts after action resolution, by card text. This takes precedence over the rulebook rules on queued combat. [ANK 20250614] [RBK resolve-the-action]`
6. **Conquer the Beast** — *No cross-card analogy, drop redundant consequence (Rules 5, 7)*
   - **Bad:** `Unlike {Trap}, the press is granted to the combatant rather than the combat itself: an effect preventing the minion from pressing to continue (eg. [ani] {Terror Frenzy}) prevents using it, and combat ends. [LSJ 19981130] [LSJ 20040618]`
   - **Good:** `The press is granted to the combatant. An effect preventing the minion from pressing to continue (e.g. [ani] {Terror Frenzy}) prevents using it. [LSJ 19981130] [LSJ 20040618]`
7. **Trap** — *Trim parentheticals and contrast tail (Rule 5)*
   - **Bad:** `Either minion (including the one who played it) can use a press to end combat to cancel the press from {Trap}, since the combat itself has the press rather than either minion. [LSJ 19981130]`
   - **Good:** `Either minion can use a press to end combat to cancel the press from {Trap}, since the combat itself has the press. [LSJ 19981130]`
8. **Immune to damage (`G00026`)** — *Drop superfluous qualifier (Rule 5)*
   - **Bad:** `Immune means damage is not successfully inflicted, even if non-preventable or outside combat. [LSJ 20010627] [LSJ 20010629] [LSJ 20090304-1] [ANK 20210324-2]`
   - **Good:** `Immune means damage is not successfully inflicted, even if non-preventable. [LSJ 20010627] [LSJ 20010629] [LSJ 20090304-1] [ANK 20210324-2]`
