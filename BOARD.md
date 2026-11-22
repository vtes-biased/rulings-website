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

- **API-only proposal & thread workflow via static bot Bearer token (no SSH for `/propose`)** — add env-configured non-approver bot Bearer auth (`API_TOKEN` + `API_TOKEN_USER_ID`, stored sops-encrypted in the repo and in `ansible/` vault), `X-Proposal` header selection, `GET /api/proposal` & `GET /api/proposal/{uid}` (own proposals unless approver), and Discord thread read/comment endpoints (`GET`/`POST /api/proposal/{uid}/comments`), then cut `.agents/skills/propose/SKILL.md` over to HTTPS-only. Done when `mise run test`, `lint`, `typecheck` pass, `vault.yml`/`vars.yml` + sops secret are wired, and `/propose` Phase 1 runs with zero SSH. *(Doc-impact: `wiki/auth.md`, `wiki/proposals.md`, `wiki/operations.md`, `wiki/deploy.md`.)*

<!-- cycles-since-upkeep: 10 -->
