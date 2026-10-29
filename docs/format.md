# The plan format

A plan is one folder under the workspace's plans folder. Every name is lowercase
kebab-case.

```
plans/auth/api-keys/               plan id: auth/api-keys
  plan.json                        metadata, section order, diagram index, tasks
  sections/
    decisions.json                 { title, blocks }, one file per section
    model.json
  diagrams/
    data-model.mmd                 Mermaid source
```

Folders group plans on the index. The plan id is the folder's path under the plans folder.
Plans do not nest: a `plan.json` inside a plan folder is ignored.

## plan.json

```json
{
  "$schema": "../../.schema/plan.schema.json",
  "title": "API keys",
  "summary": "What this builds and why.",
  "status": "approved",
  "updated": "2026-10-23",
  "branch": "feat/api-keys",
  "tags": ["auth", "security"],
  "dependsOn": ["billing/plans"],
  "diagrams": {
    "data-model": { "alt": "How API keys relate to accounts and scopes.", "file": "diagrams/data-model.mmd" }
  },
  "sections": ["decisions", "model"],
  "tasks": [{ "id": "key-lookup", "title": "Key lookup", "status": "todo" }]
}
```

| Field | Notes |
| --- | --- |
| `$schema` | Written by planboard: a relative path to the workspace's schema folder. |
| `status` | `draft`, `approved` or `archived`: the state of the document. Progress comes from the tasks. |
| `updated` | Stamped by every CLI or board write. History lives in git. |
| `diagrams` | Every diagram the plan defines, by id. See [Diagrams](#diagrams). |
| `sections` | Section ids in reading order. Each is `sections/<id>.json`, and becomes a link target `#id`. |
| `tasks` | The board cards, in build order. Their position is their number. |

A section file in `sections/` that `sections` does not list is a `validate` problem.

## Section files

```json
{
  "$schema": "../../../.schema/section.schema.json",
  "title": "Data model",
  "blocks": [{ "type": "text", "text": "Each key belongs to one account." }]
}
```

The id is the file name. Both schemas are generated from the models, so editors that read
JSON Schema (VS Code, JetBrains, Zed) autocomplete fields and flag mistakes as you type.
`planboard schema` rewrites them after an upgrade.

## Tasks

```json
{
  "id": "middleware",
  "title": "Middleware",
  "status": "todo",
  "summary": "Reject requests over the limit with a 429.",
  "note": "Why it is blocked, when it is.",
  "dependsOn": ["#redis-store", "auth/api-keys#key-lookup"],
  "sections": ["design"],
  "diagrams": ["request-flow"]
}
```

`sections` and `diagrams` name the parts of the document a task builds; the document shows
the task beside each section, and the task links to both.

## References

`dependsOn`, on a plan or a task, takes references in three forms:

| Reference | Means |
| --- | --- |
| `#task` | A task in the same plan |
| `folder/plan` | Another plan, done when all of its tasks are done |
| `folder/plan#task` | A task in another plan |

A task whose dependencies are not done "waits on" them: on its card, in `outline` and in
`board`. `next` lists the todo tasks that wait on nothing. `validate` fails on a reference
that does not resolve and on a dependency cycle.

## Blocks

Text fields accept inline markup: `` `code` ``, `**bold**` and `[label](href)`. An href
is a web address, `#id` for a section or diagram in this plan, `folder/plan` for another
plan, or `folder/plan#id` for a section or diagram in it. `validate` fails on a link that
does not resolve.

| `type` | Fields | Renders |
| --- | --- | --- |
| `text` | `text` | A paragraph |
| `heading` | `text` | A sub-heading inside the section |
| `list` | `items` (strings or `{ text, items }`), `ordered` | A list, nested when an item has `items` |
| `table` | `columns`, `rows` (`null` for an empty cell), `caption` | A table; the first column heads each row |
| `callout` | `tone` (`note`, `warning`), `title`, `text` | A highlighted note |
| `code` | `code`, `language`, `caption` | A code sample with a copy button |
| `diagram` | `ref`, `caption` | A diagram from a `diagrams` map; see [Diagrams](#diagrams) |

Hierarchies, flows and data models are diagrams: a Mermaid `flowchart` with subgraphs for
containment, a `sequenceDiagram` for a flow between actors, an `erDiagram` for tables.

## Diagrams

A diagram is [Mermaid](https://mermaid.js.org/intro/) source, defined once in `plan.json`'s
`diagrams` map and shown wherever a `diagram` block references it. Each entry has `alt`
text and either a `file`, relative to the plan folder and inside it, or inline `source`
for a few lines. `planboard diagram add` writes the file to `diagrams/<id>.mmd`.

Show a diagram with a block. The caption belongs to the block, so the same diagram can be
explained differently in two places, or in another plan:

```json
{ "type": "diagram", "ref": "#request-flow", "caption": "How a request reaches its handler." }
{ "type": "diagram", "ref": "auth/api-keys#data-model" }
```

Link to a diagram the same way as to a section, `[the tables](#data-model)`.
Section and diagram ids share one namespace per plan, so `#id` always means one thing.
`validate` fails on a missing or empty file, a `ref` that does not resolve, and a diagram
the plan defines but never shows.

The web app bundles Mermaid 12.1.0 and its fonts into the package, so diagrams render
without a network connection.
