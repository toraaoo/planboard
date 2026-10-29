---
name: planboard-next
description: >
  Pick the next ready task from a planboard plan, build it as the plan describes, and
  track it on the board (doing, then done or blocked). Use when the user asks what to
  work on next, to continue a plan, to build a specific planboard task, or runs
  /planboard next.
argument-hint: "[folder/plan or folder/plan#task]"
license: MIT
---

# planboard next

Load the `planboard` skill first: it has the commands, the rules and the block format.

## 1. Pick the task

- The user named a task (`folder/plan#task`): take it. If `planboard outline <plan>`
  shows it waiting on unfinished tasks, say so and ask before starting.
- The user named a plan: the first ready task of that plan in `planboard next <plan>`.
- Nothing named: `planboard next`. Its "In progress" tasks are unfinished work: ask
  whether to resume one, starting with one whose "finishing it readies" list is longest.
  Otherwise take the first task under "Ready".
- No ready task: report what `planboard next` shows (what is in progress, and what each
  waiting task waits on) and the blocked notes, then stop.

## 2. Read what it builds

- `planboard task show <plan#task>` lists what the task waits on, what needs it, and
  the sections and diagrams it builds.
- Read each one: `planboard show <plan>#<section>`, and the diagram files.
- Read the `context` and `decisions` sections too: the reasons constrain the code.
- Read the tasks it depends on, and check their code is really there.

## 3. Build it

```bash
planboard task status <plan#task> doing
```

- Build exactly the task: its summary and the sections it links. Work for a later task
  stays for that task.
- Follow the repository's own conventions and run its tests, linter and type checker.
- Where the code has to differ from the plan, keep going only if the change is small,
  and record it: update the section with `planboard block set` or `block add`, and say
  so in the report. A large difference: stop and ask.

## 4. Track it

- Done, with tests passing: `planboard task status <plan#task> done`.
- Stuck on something outside the task (a decision, a missing dependency, access):
  `planboard task status <plan#task> blocked --note "what it waits for"`, then ask.
- Clear an old note when it no longer applies: `--note ""`.

## 5. Report

What was built, the files changed, how it was verified, any change to the plan, and
what `planboard next` now offers. Do not start the following task unless asked.
