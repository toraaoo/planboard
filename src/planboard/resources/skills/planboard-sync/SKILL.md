---
name: planboard-sync
description: >
  Bring a planboard plan's task statuses in line with the code: find tasks that are
  built but not marked done, marked done but missing, or stuck in doing, and fix the
  board with the user's approval. Use when the board looks stale, after work done
  outside planboard, or when the user runs /planboard sync.
argument-hint: "[folder/plan]"
license: MIT
---

# planboard sync

Load the `planboard` skill first: it has the commands, the rules and the format.

## 1. Collect the evidence

- The plan: the one named, or each plan that is not `archived` in `planboard outline`.
- `planboard outline <plan>` for its tasks, their statuses and the sections they build.
- For each task, look for its code: the files, types and commands its sections name,
  the tests that cover them, and `git log --oneline` on the plan's `branch` or the
  current branch for commits that mention it.

## 2. Compare

For each task, one finding when the board and the code disagree:

| Board | Code | Proposal |
| --- | --- | --- |
| `todo` or `doing` | built and tested | `done` |
| `doing` | no change in recent history | back to `todo`, or `blocked` with a note |
| `blocked` | the note's reason is gone | `todo`, and clear the note |
| `done` | missing or reverted | `todo`, with a note |

Built but untested is not done. Partly built stays `doing`. Every finding names the
file, test or commit it rests on; no evidence, no finding.

## 3. Apply

List the findings as numbered proposals, then ask which to apply. Apply each one with
`planboard task status <plan#task> <status> [--note "…"]`; never edit statuses by hand.
Where the code took a different shape than a section describes, report it and offer to
update the section (`planboard block set`); do not rewrite the design unasked.

End with `planboard validate` (must exit 0) and the new `done/total` for each plan.
