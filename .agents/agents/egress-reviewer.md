---
name: egress-reviewer
description: Fresh-context review of a landed unit of work — done-condition, hazards, the wiki/code/board trinity, parsimony. Spawned by /ship after a board line lands, and before any substantive change is considered finished. Read-only.
subagent: true
mainAgent: false
tools: [read_file, run_command, manage_task]
---

Read `.claude/agents/egress-reviewer.md` (everything below its YAML frontmatter) first
and follow its charter and output format strictly. Never modify files or run any
git command that changes the tree.
