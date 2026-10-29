---
name: planboard-new
description: >
  Write a new planboard implementation plan for a feature or change: context,
  decisions, design with Mermaid diagrams, risks, tests, and an ordered list of tasks
  with dependencies. Use when the user asks to plan, design or scope work before
  building it, or runs /planboard new.
argument-hint: "<folder/plan> [what to build]"
license: MIT
---

# planboard new

Load the `planboard` skill first: it has the commands, the rules and the block format.

## 1. Understand before writing

- Read the request, then the code it touches: entry points, models, tests, config. A
  plan names real files, types and commands, not placeholders.
- `planboard outline` lists existing plans, and `planboard search <words>` finds
  related ones. Do not duplicate one; extend it, or depend on it with `--depends-on`.
- Ask the user about anything the code cannot answer: scope, constraints, a choice
  between designs. Do not invent requirements.
- `planboard where`: if no workspace is found, ask before running `planboard init`.

## 2. Create it

```bash
planboard new <folder>/<slug> --title "…" --summary "…" --tags "…" [--branch …] [--depends-on …]
```

The template has sections `context`, `decisions`, `design`, `risks` and `tests`, two
inline diagrams and one task. Replace every placeholder; remove what the plan does not
need (`planboard section rm`, `planboard diagram rm`, `planboard task rm`).

## 3. Write the sections

Write each section with the CLI, so every change is validated:

- `planboard block list <plan>#<section>` shows the template's numbered blocks.
- Replace them one at a time with `planboard block set` / `block add` / `block rm`, or
  write the section's blocks as a JSON list and run `planboard section set
  <plan>#<section> --title "…" --from -` with the JSON on stdin.
- `planboard show <plan>#<section>` to read the result.

- **Context**: what exists today, what is missing, what this changes. Name files.
- **Decisions**: a table, one row per choice: the decision and why, including the
  option not taken.
- **Design**: the shape of the change. Use a diagram for anything with structure: a
  `flowchart` with subgraphs for components, a `sequenceDiagram` for a flow between
  actors, an `erDiagram` for tables. Use `code` blocks for interfaces and schemas.
- **Risks**: a table of what could go wrong and how the design prevents it.
- **Tests**: what each layer proves.
- Add a section per larger part when the design gets long (`planboard section add`).

Write diagrams to files: `planboard diagram add <plan> <id> --alt "…" --from - --section
<section>` with the Mermaid source on stdin. Every diagram needs alt text and a block
that shows it.

## 4. Write the tasks

Tasks are the board cards, in build order.

- One task is one reviewable change that builds, passes its tests and leaves the system
  working. Prefer five small tasks to one large one.
- `planboard task add <plan> <id> --title "…" --summary "…" --sections … --diagrams …
  --depends-on "#…"`. Link every task to the sections and diagrams it builds.
- `dependsOn` only for real ordering: the task cannot start before the other is done.
  `planboard next` uses it to say what is ready.
- The first task is the smallest step that proves the design.

## 5. Finish

- `planboard validate` exits 0.
- `planboard outline <plan>`: every task links a section, no section is orphaned, the
  build order reads top to bottom.
- Leave `status` at `draft`. Tell the user the plan id, the task count, the open
  questions, and `planboard serve` to read it in the browser.
