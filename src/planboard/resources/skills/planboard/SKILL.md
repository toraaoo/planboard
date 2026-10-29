---
name: planboard
description: >
  Read, track and write implementation plans kept as planboard JSON (a planboard.toml
  in the repo, or plan.json files with sections/ and diagrams/ folders). Use when the
  user mentions planboard, a plan, its tasks or board, asks what to work on next, or
  asks to plan a feature before building it. Modes: new, next, status, sync.
argument-hint: "[new|next|status|sync] [plan or request]"
license: MIT
---

# planboard

Plans live in the repository as folders of JSON and Mermaid files. The `planboard` CLI
reads them, and validates every change before it writes. Use the CLI for every change it
can make; it covers every field, including section content. Edit a file by hand only
when no command fits, then run `planboard validate`.

Run `planboard`. If it is not on the PATH, try `uv run planboard`, then
`uvx planboard`. If none works, tell the user to install it
(`uv tool install planboard`) and stop.

## Modes

`/planboard <mode>`, or the `planboard-<mode>` skill, runs one workflow. Load that skill
and follow it:

| Mode | Does |
| --- | --- |
| `new` | Write a plan for a feature: decisions, design, diagrams, tasks |
| `next` | Pick the next ready task, build it, and track it on the board |
| `status` | Report progress: done, in progress, blocked, ready next. Changes nothing |
| `sync` | Bring task statuses in line with the code and the git history |

No mode: orient with the steps below, then do what the user asked.

## Find your way

1. `planboard where` shows which plans folder is in use. If it says "user data folder",
   there is no workspace in this repo.
2. `planboard outline` lists every plan with its status and progress.
3. `planboard outline <plan>` maps one plan: the file of each section and diagram, and
   each task with its status, what it waits on and what it builds.
   `planboard outline --tag <tag>` lists only the plans with that tag.
4. Read only what you need: `planboard show <plan>#<section>`, `planboard task show
   <plan#task>`, or `planboard block list <plan#section>` for numbered blocks.
5. `planboard next` shows tasks in progress, then the ones ready to start, and when
   none is ready, what each waiting task waits on. `planboard board [plan]` shows tasks
   by status. Both take a plan or a folder (`planboard next api`) and `--tag`.
6. `planboard search <words>` finds plans, tasks, sections and diagrams; it tolerates
   typos.

A reference is `folder/plan`, or `folder/plan#id` for a task, section or diagram. Add
`--json` to any read command for structured output, `-q` to drop confirmations, and
`-n` to check a write without writing.

## Change things

| To change | Do |
| --- | --- |
| A task's status | `planboard task status <plan#task> <todo\|doing\|blocked\|done> [--note "why"]` |
| Tasks | `planboard task add / set / move / rename / rm` |
| Plan metadata | `planboard plan set <plan> --title --summary --status --branch --tags --depends-on` |
| A plan's id, or the plan | `planboard plan mv <plan> <new>`, `planboard plan rm <plan>` |
| Sections | `planboard section add / set / rename / move / rm` |
| One block of a section | `planboard block add / set / move / rm <plan#section> …` |
| A whole section's blocks | `planboard section set <plan#section> --from file.json` (or `-` for stdin) |
| Diagrams | `planboard diagram add / set / rename / rm`; or edit `diagrams/<id>.mmd` |
| A new plan | `planboard new <folder>/<slug> --title "…" --summary "…" --tags "…"` |
| A new workspace | `planboard init` (ask the user first: it adds files to the repo) |

Blocks are numbered from 1 in `planboard block list`. Add one with its type and fields:

```bash
planboard block add <plan#section> text --text "…"
planboard block add <plan#section> heading --text "…" --at 2
planboard block add <plan#section> list --item "…" --item "…" [--ordered]
planboard block add <plan#section> table --columns "Decision | Why" --row "… | …"
planboard block add <plan#section> callout --title "…" --text "…" [--tone warning]
planboard block add <plan#section> code --language python --from file.py
planboard block add <plan#section> diagram --ref "#id" --caption "…"
planboard block add <plan#section> --json '{"type": "list", "items": [{"text": "…", "items": ["…"]}]}'
```

`block set <plan#section> <n>` changes fields the same way, or replaces the block with
`--json`. For a long section, write its blocks as JSON and use `section set --from`.

`planboard <command> --help` lists every option. List options are comma-separated, and
an empty string clears an optional field: `--depends-on "#a,other/plan"`, `--note ""`.
Table cells are `|`-separated.

## Rules

- Never hand-edit task statuses, task order, the `sections` list or any id in
  `plan.json`. The CLI keeps files, task links and `#links` in sync and stamps `updated`.
- A write that would break a reference or link in any plan is refused, and nothing is
  written. Fix the plans that refer to it first. `--force` writes anyway; use it only
  when the user asks.
- After any hand edit, run `planboard validate`. It must exit 0 before you finish.
- Ids and folder names are lowercase kebab-case. Sections and diagrams share one id
  namespace per plan.
- Ids are file and folder names: rename with `section rename`, `diagram rename`,
  `task rename` or `plan mv`, never by renaming a file or folder.
- A task is `done` only when its code is written and its tests pass. `blocked` always
  gets a `--note` saying what it waits for.
- Do not change a plan's `status` (`draft`, `approved`, `archived`) unless the user asks.
  Progress comes from the tasks.

## The format

A plan folder holds `plan.json` (metadata, section order, diagram index, tasks),
`sections/<id>.json` (`{ "title", "blocks": [...] }`) and `diagrams/<id>.mmd`.

Blocks, in a section's `blocks` list:

| `type` | Fields |
| --- | --- |
| `text` | `text` |
| `heading` | `text` |
| `list` | `items` (strings, or `{ "text", "items" }` to nest), `ordered` |
| `table` | `columns`, `rows` (`null` for an empty cell), `caption` |
| `callout` | `tone` (`note` or `warning`), `title`, `text` |
| `code` | `code`, `language`, `caption` |
| `diagram` | `ref` (`#id`, or `folder/plan#id`), `caption` |

Text takes `` `code` ``, `**bold**` and `[label](href)`; an href is a URL, `#id`,
`folder/plan` or `folder/plan#id`. A task's `dependsOn` takes `#task`, `folder/plan`
(done when all its tasks are) or `folder/plan#task`. `validate` fails on a reference
that does not resolve, a dependency cycle, and a diagram the plan never shows.
