---
name: planboard-status
description: >
  Report the progress of planboard plans: what is done, in progress, blocked and ready
  next, and what holds the rest back. Read-only. Use when the user asks for the status
  of a plan or of all plans, where things stand, or runs /planboard status.
argument-hint: "[folder/plan]"
license: MIT
---

# planboard status

Load the `planboard` skill first: it has the commands and the format. This mode changes
nothing.

## Gather

- `planboard validate --json`: problems come first in the report.
- One plan named: `planboard outline <plan> --json` and `planboard board <plan> --json`.
- Nothing named: `planboard outline --json`, `planboard board --json` and
  `planboard next --json` across all plans.
- `planboard next --json` returns `ready`, `doing`, `blocked` and `waiting` lists. Each
  task has `waitingOn`, and `readies`: the todo tasks that finishing it would free.

## Report

Short, in this order, empty parts left out:

1. **Problems**: anything `validate` reports.
2. **Progress**: per plan, `done/total` and its status (`draft`, `approved`, `archived`).
3. **In progress**: `doing` tasks.
4. **Blocked**: each blocked task with its note.
5. **Ready next**: the first tasks in `next`'s `ready` list.
6. **Waiting**: tasks held back by a dependency, and the unfinished task with the
   longest `readies` list.
7. **Out of order**: `doing` or `done` tasks whose own `waitingOn` is not empty.

Use references (`folder/plan#task`) so the user can act on them. End with one line: the
task to pick up next, or the decision that unblocks the most work.
