# Architecture

planboard is a hexagonal (ports and adapters) application. The plan format and its rules
sit in the middle. Use cases wrap them, and everything that touches the outside world
(files, the terminal, HTTP) is an adapter at the edge.

```
            adapters/cli      adapters/web          (driving adapters)
                   \              /
                    application                     use cases + the PlanRepository port
                   /       |
             domain        ports.PlanRepository
                                 ^
                                 |
                     adapters/filesystem             (driven adapter)

  bootstrap.py wires adapters/filesystem into application.Workspace.
  config.py decides which plans folder to open.
```

## The dependency rule

Imports point inward only. `tests/unit/test_architecture.py` enforces it:

| Layer | May import | Must not import |
| --- | --- | --- |
| `domain` | itself, pydantic | `application`, `adapters`, `config`, `bootstrap`, `resources`, typer, rich, http |
| `application` | `domain`, `resources` | `adapters`, `config`, `bootstrap`, typer, rich, http |
| `adapters/filesystem` | `domain`, `application` | other adapters, `config`, `bootstrap` |
| `adapters/web` | `domain`, `application` | other adapters, `config`, `bootstrap` |
| `adapters/cli` | everything | |

## Modules

```
src/planboard/
  __init__.py           Public API: Workspace, open_workspace, Plan, Task, errors, __version__
  __main__.py           python -m planboard
  py.typed              PEP 561: the package ships type information
  config.py             Find the plans folder: --data, PLANBOARD_DATA, planboard.toml, user folder
  bootstrap.py          Composition root: open_workspace() wires the filesystem adapter in

  domain/               Pure: no I/O, no frameworks besides pydantic
    base.py ids.py blocks.py plan.py
                        Pydantic models: the format's single source of truth
    json.py             JsonValue, JsonObject
    layout.py           File names inside a plan folder
    draft.py            A plan's documents in memory, assembled and validated
    references.py       Resolve dependencies and links, find cycles, ready tasks
    search.py           Fuzzy search over plans, tasks, sections and diagrams
    schemas.py          Render the JSON Schemas from the models
    edits/              Changes to a Draft: plan, tasks, sections, blocks, diagrams

  application/          Use cases, independent of how plans are stored or shown
    ports.py            PlanRepository (the port), LoadedPlan, BrokenPlan, EditResult, errors
    workspace.py        Workspace: every use case; the CLI, web app and library call this
    catalog.py          Every plan loaded at once, with its problems and dependents
    diagrams.py         Resolve diagram refs, through the port
    payloads.py         JSON read models for the web API and --json

  adapters/
    filesystem/         FilePlanRepository: plans as folders of JSON and Mermaid files
      files.py          JSON reads and atomic writes
      repository.py     The PlanRepository implementation
      schemas.py        Write and check the schema files of a workspace
      agents.py         Coding agents and their project and user skill folders
      skills.py         Install the shipped skills for chosen agents
    cli/                Typer: app.py, one module per command group (blocks.py: block)
      completion.py     Shell completion for plan, task, section and diagram refs
      render/           outline.py (plain text), terminal.py (rich)
    web/                server.py (standard-library HTTP + JSON API), static/ (built)

  resources/            Package data read through importlib.resources
    templates/          The skeleton planboard new writes
    skills/             The agent skills planboard skill install puts in place
```

## The web app

`frontend/` is a React app (Vite, TanStack Router and Query, shadcn/ui) built with bun.
`bun run build` writes it to `src/planboard/adapters/web/static/`, which is gitignored and
served by `server.py`. Routes use hash history, so the server needs no fallback route; the
app reads only `/api/*`.

`hatch_build.py` runs that build when Hatchling packages from the repository. The sdist
carries the built files and no `frontend/`, so a wheel built from it needs no JavaScript
toolchain. `PLANBOARD_SKIP_FRONTEND=1` packages the files already in `static/`.

## Adding things

- **A field in the format**: change the model in `domain/`, then run `planboard schema`.
- **An edit**: write a function over `Draft` in `domain/edits/`, then call it through
  `Workspace.edit` from the CLI or web adapter. It is validated and written atomically.
- **A new store** (a database, a remote API): implement `application.ports.PlanRepository`
  and pass it to `Workspace`. Nothing in `domain` or `application` changes.
- **A new interface** (a TUI, an MCP server): add an adapter that builds a `Workspace`
  with `planboard.open_workspace()` and calls its methods.

## Working on planboard

- Format rules and edits are pure functions in `domain/`. New use cases go on
  `Workspace`; adapters call only that. Storage goes through `PlanRepository`.
- Read package data (templates, skills, web static files) with `importlib.resources`,
  never with paths built from `__file__`.
- Tests mirror the source under `tests/unit/`; end-to-end CLI and wheel checks are in
  `tests/integration/`. Add dependencies with `uv add` (or `uv add --dev`).
- An agent skill is a folder in `resources/skills/` holding a `SKILL.md` whose `name`
  matches the folder. A mode of `/planboard` is its own `planboard-<mode>` skill, listed
  in the main skill's Modes table.
