from __future__ import annotations

import os
import sys
from dataclasses import asdict, replace
from typing import Annotated

import typer

from ...application import payloads
from ...application.catalog import Catalog
from ...application.ports import PlanExistsError
from ...domain.draft import InvalidPlanError
from ...domain.edits.plan import set_plan
from ...domain.ids import is_plan_id
from ...domain.plan import PlanStatus
from . import completion, tasks
from .render import outline as outline_view
from .render import terminal
from .shared import (
    CLEAR_HELP,
    LIST_HELP,
    WORD,
    DryRun,
    Force,
    JsonFlag,
    PlanArg,
    Yes,
    clearable,
    collect,
    confirm,
    console,
    done,
    fail,
    hint,
    keep,
    listed,
    missing_plan,
    parse_ref,
    print_json,
    refusals,
    warn_problems,
    workspace_of,
    write,
)

group = typer.Typer(
    help="Edit a plan's metadata, move it or delete it.", no_args_is_help=True
)


def outline(
    ctx: typer.Context,
    plan: Annotated[
        str | None,
        typer.Argument(
            click_type=WORD,
            metavar="[PLAN]",
            help="folder/plan",
            autocompletion=completion.plans,
        ),
    ] = None,
    tag: Annotated[
        str | None,
        typer.Option(
            metavar="NAME", help="List only plans with this tag.", show_default=False
        ),
    ] = None,
    as_json: JsonFlag = False,
) -> None:
    """List every plan, or map one plan's files, sections, diagrams and tasks."""
    workspace = workspace_of(ctx)
    snapshot = workspace.catalog()
    if plan is not None and tag is not None:
        raise typer.BadParameter("--tag filters the list of plans; drop PLAN.")
    if tag is not None:
        snapshot = _tagged(snapshot, tag)
    if plan is None:
        if as_json:
            print_json(payloads.list_plans(snapshot))
            return
        if tag is not None and not snapshot.loaded:
            print(f"No plan has the tag '{tag}'.", flush=True)
            return
        print(outline_view.overview(snapshot), flush=True)
        if not snapshot.loaded and not snapshot.broken:
            hint(ctx, 'Start one: planboard new <folder/plan> --title "…"')
        return
    if plan in snapshot.broken:
        lines = "\n".join(f"  {error}" for error in snapshot.broken[plan].errors)
        fail(f"{plan} cannot be read:\n{lines}", "Fix the files, then run validate.")
    entry = snapshot.loaded.get(plan)
    if entry is None:
        missing_plan(workspace, plan)
    if as_json:
        print_json(outline_view.plan_json(snapshot, entry))
    else:
        print(outline_view.plan_outline(snapshot, entry))


def _tagged(snapshot: Catalog, tag: str) -> Catalog:
    """The catalog with only the plans that have the tag; broken plans drop out."""
    loaded = {k: v for k, v in snapshot.loaded.items() if tag in v.plan.tags}
    return replace(snapshot, loaded=loaded, broken={})


def show(
    ctx: typer.Context,
    ref: Annotated[
        str,
        typer.Argument(
            click_type=WORD,
            metavar="REF",
            help="folder/plan, or folder/plan#id for a section, diagram or task",
            autocompletion=completion.anchors("anchor"),
        ),
    ],
    as_json: JsonFlag = False,
    pager: Annotated[
        bool | None,
        typer.Option(
            "--pager/--no-pager",
            help="Page the document. Default: when printing to a terminal.",
            show_default=False,
        ),
    ] = None,
) -> None:
    """Read a plan as a document, or one section, diagram or task of it."""
    workspace = workspace_of(ctx)
    target = parse_ref(ref)
    snapshot = workspace.catalog()
    entry = snapshot.loaded.get(target.plan_id)
    if entry is None:
        missing_plan(workspace, target.plan_id)
    anchor = target.anchor
    if anchor is not None and anchor not in entry.plan.anchors():
        if entry.plan.task(anchor) is not None:
            tasks.show_one(ctx, snapshot, target.plan_id, anchor, as_json=as_json)
            return
        fail(
            f"'{anchor}' is not a section or diagram of {target.plan_id}.",
            f"Run planboard outline {target.plan_id} for its ids.",
        )
    if not as_json:
        document = terminal.plan_document(snapshot, entry, anchor)
        if pager if pager is not None else sys.stdout.isatty():
            os.environ.setdefault("LESS", "FRX")
            with console.pager(styles=True):
                console.print(document)
        else:
            console.print(document)
        return
    payload = workspace.plan(target.plan_id)
    if anchor is None:
        print_json(payload)
    elif anchor in entry.plan.diagrams:
        print_json(asdict(snapshot.diagrams.resolve(f"#{anchor}", target.plan_id)))
    else:
        sections = payload["plan"]["sections"]
        print_json(next(s for s in sections if s["id"] == anchor))


def new(
    ctx: typer.Context,
    plan: Annotated[
        str,
        typer.Argument(
            click_type=WORD,
            metavar="PLAN",
            help="folder/plan, for example api/rate-limiting",
        ),
    ],
    title: Annotated[
        str | None, typer.Option(metavar="TEXT", help="Defaults to the slug in words.")
    ] = None,
    summary: Annotated[
        str | None,
        typer.Option(
            metavar="TEXT",
        ),
    ] = None,
    tags: Annotated[
        str | None, typer.Option(metavar="LIST", help="Comma-separated.")
    ] = None,
    depends_on: Annotated[
        str | None,
        typer.Option(metavar="REFS", help="Plan references, comma-separated."),
    ] = None,
    branch: Annotated[
        str | None,
        typer.Option(
            metavar="NAME",
        ),
    ] = None,
    dry_run: DryRun = False,
) -> None:
    """Write a new plan folder from the template."""
    workspace = workspace_of(ctx)
    if not is_plan_id(plan):
        raise typer.BadParameter(f"'{plan}' must be kebab-case segments joined by /.")
    fields = {
        key: value
        for key, value in {
            "summary": clearable(summary or ""),
            "tags": listed(tags or ""),
            "dependsOn": listed(depends_on or ""),
            "branch": clearable(branch or ""),
        }.items()
        if value is not None
    }
    try:
        folder = workspace.create_plan(plan, title, fields=fields, dry_run=dry_run)
    except PlanExistsError:
        fail(f"{plan} already exists.", f"Run planboard outline {plan}.")
    except InvalidPlanError as error:
        lines = "\n".join(f"  {line}" for line in error.errors)
        fail(f"Nothing written; {plan} would be invalid:\n{lines}")
    if dry_run:
        console.print(f"Dry run, nothing written. {plan} would be valid.")
        console.print(f"  would create {folder}/", highlight=False)
        return
    done(ctx, f"Created {folder}/")
    warn_problems(workspace)
    hint(
        ctx,
        f"Next: fill it in, then planboard validate. Read it: planboard show {plan}",
    )


@group.command("set")
def set_metadata(
    ctx: typer.Context,
    plan: PlanArg,
    title: Annotated[
        str | None,
        typer.Option(
            metavar="TEXT",
        ),
    ] = None,
    summary: Annotated[
        str | None,
        typer.Option(
            metavar="TEXT",
        ),
    ] = None,
    status: Annotated[PlanStatus | None, typer.Option()] = None,
    branch: Annotated[str | None, typer.Option(metavar="NAME", help=CLEAR_HELP)] = None,
    tags: Annotated[str | None, typer.Option(metavar="LIST", help=LIST_HELP)] = None,
    depends_on: Annotated[
        str | None, typer.Option(metavar="REFS", help=f"Plan references. {LIST_HELP}")
    ] = None,
    dry_run: DryRun = False,
    force: Force = False,
) -> None:
    """Change a plan's title, summary, status, branch, tags or dependencies."""
    plan_id = parse_ref(plan).plan_id
    changes = collect(
        ("title", title, keep),
        ("summary", summary, keep),
        ("status", status, keep),
        ("branch", branch, clearable),
        ("tags", tags, listed),
        ("dependsOn", depends_on, listed),
    )
    write(
        ctx,
        plan_id,
        lambda draft: set_plan(draft, changes),
        f"Updated {plan_id}",
        dry_run=dry_run,
        force=force,
    )


@group.command("mv")
def move(
    ctx: typer.Context,
    plan: PlanArg,
    new_id: Annotated[
        str,
        typer.Argument(
            click_type=WORD,
            metavar="NEW",
            help="folder/plan, for example api/throttling",
        ),
    ],
    dry_run: DryRun = False,
    force: Force = False,
) -> None:
    """Move a plan to a new id: its folder, and its references to itself.

    Refused while another plan refers to the old id, unless --force.
    """
    plan_id = parse_ref(plan).plan_id
    workspace = workspace_of(ctx)
    with refusals(workspace, plan_id):
        result = workspace.move_plan(plan_id, new_id, dry_run=dry_run, force=force)
    if dry_run:
        console.print(f"Dry run, nothing written. {new_id} would be valid.")
        console.print(f"  would move {len(result.written)} files to {new_id}/")
        return
    done(ctx, f"Moved {plan_id} to {new_id}")
    warn_problems(workspace)


@group.command("rm")
def remove(
    ctx: typer.Context,
    plan: PlanArg,
    yes: Yes = False,
    dry_run: DryRun = False,
    force: Force = False,
) -> None:
    """Delete a plan folder. Refused while another plan refers to it, unless --force."""
    plan_id = parse_ref(plan).plan_id
    workspace = workspace_of(ctx)
    if not dry_run:
        confirm(f"Delete {plan_id} and every file in it?", yes)
    with refusals(workspace, plan_id):
        files = workspace.remove_plan(plan_id, dry_run=dry_run, force=force)
    if dry_run:
        console.print("Dry run, nothing removed.")
        for name in files:
            console.print(f"  would remove {plan_id}/{name}", highlight=False)
        return
    done(ctx, f"Removed {plan_id} ({len(files)} files)")
    warn_problems(workspace)


def search(
    ctx: typer.Context,
    query: Annotated[
        str,
        typer.Argument(
            click_type=WORD, help="Words to find; any case, a typo or two is fine."
        ),
    ],
    limit: Annotated[
        int,
        typer.Option("--limit", "-l", metavar="N", help="Show at most this many."),
    ] = 20,
    as_json: JsonFlag = False,
) -> None:
    """Fuzzy-find plans, tasks, sections and diagrams, best match first.

    Every word must match a word in the text: exactly, as a prefix, or with a typo.
    Exits 1 when nothing matches.
    """
    if limit < 1:
        raise typer.BadParameter("--limit must be 1 or more.")
    hits = workspace_of(ctx).search(query)[:limit]
    if as_json:
        print_json([asdict(hit) for hit in hits])
    else:
        console.print(terminal.hits(hits))
    if not hits:
        raise typer.Exit(1)
