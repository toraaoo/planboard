from __future__ import annotations

from typing import Annotated

import typer

from ...domain.edits.sections import (
    add_section,
    move_section,
    remove_section,
    rename_section,
    set_section,
)
from ...domain.json import JsonValue
from . import completion
from .shared import (
    WORD,
    After,
    Before,
    DryRun,
    Force,
    PlanArg,
    Yes,
    anchor_ref,
    confirm,
    parse_ref,
    place,
    read_file,
    read_json,
    write,
)

group = typer.Typer(
    help="Add, rename, move and remove sections. Change their blocks with "
    "planboard block, or replace them with section set --from.",
    no_args_is_help=True,
)

SectionRef = Annotated[
    str,
    typer.Argument(
        click_type=WORD,
        metavar="SECTION",
        help="folder/plan#section",
        autocompletion=completion.anchors("section"),
    ),
]
NewId = Annotated[
    str, typer.Argument(click_type=WORD, metavar="ID", help="kebab-case id")
]
BlocksFile = Annotated[
    str | None,
    typer.Option(
        "--from",
        metavar="FILE",
        help="JSON: a list of blocks, or { title, blocks }; - is stdin.",
    ),
]


@group.command()
def add(
    ctx: typer.Context,
    plan: PlanArg,
    section_id: NewId,
    title: Annotated[
        str,
        typer.Option(
            metavar="TEXT",
        ),
    ],
    text: Annotated[
        str | None, typer.Option(metavar="MARKUP", help="The opening paragraph.")
    ] = None,
    source_file: BlocksFile = None,
    after: After = None,
    before: Before = None,
    dry_run: DryRun = False,
    force: Force = False,
) -> None:
    """Add a section, at the end of the document unless placed.

    Give its content as one paragraph with --text, or as blocks with --from.
    """
    plan_id = parse_ref(plan).plan_id
    position = place(after, before)
    if (text is None) == (source_file is None):
        raise typer.BadParameter("Give --text or --from, one of them.")
    blocks = None if source_file is None else _blocks(source_file)[1]
    write(
        ctx,
        plan_id,
        lambda draft: add_section(draft, section_id, title, text, position, blocks),
        f"Added {plan_id}#{section_id}",
        dry_run=dry_run,
        force=force,
    )


@group.command("set")
def set_content(
    ctx: typer.Context,
    ref: SectionRef,
    title: Annotated[
        str | None,
        typer.Option(
            metavar="TEXT",
        ),
    ] = None,
    source_file: BlocksFile = None,
    dry_run: DryRun = False,
    force: Force = False,
) -> None:
    """Change a section's title, or replace its blocks with --from.

    --from takes a JSON list of blocks, or a section object { "title", "blocks" }.
    To change one block, use planboard block.
    """
    plan_id, section_id = anchor_ref(ref, "section")
    if title is None and source_file is None:
        raise typer.BadParameter("Nothing to change: give --title or --from.")
    blocks: list[JsonValue] | None = None
    if source_file is not None:
        file_title, blocks = _blocks(source_file)
        title = title or file_title
    write(
        ctx,
        plan_id,
        lambda draft: set_section(draft, section_id, title, blocks),
        f"Updated {plan_id}#{section_id}",
        dry_run=dry_run,
        force=force,
    )


def _blocks(source_file: str) -> tuple[str | None, list[JsonValue]]:
    """The title, if given, and blocks of a JSON section or list of blocks."""
    value = read_json(read_file(source_file), source_file)
    if isinstance(value, list):
        return None, value
    if isinstance(value, dict) and isinstance(blocks := value.get("blocks"), list):
        title = value.get("title")
        return (title if isinstance(title, str) else None), blocks
    raise typer.BadParameter(
        f"{source_file} must hold a list of blocks or an object with blocks."
    )


@group.command()
def rename(
    ctx: typer.Context,
    ref: SectionRef,
    new_id: NewId,
    dry_run: DryRun = False,
    force: Force = False,
) -> None:
    """Change a section's id: its file, the tasks that build it and #links to it."""
    plan_id, section_id = anchor_ref(ref, "section")
    write(
        ctx,
        plan_id,
        lambda draft: rename_section(draft, plan_id, section_id, new_id),
        f"Renamed {plan_id}#{section_id} to #{new_id}",
        dry_run=dry_run,
        force=force,
    )


@group.command()
def move(
    ctx: typer.Context,
    ref: SectionRef,
    after: After = None,
    before: Before = None,
    dry_run: DryRun = False,
    force: Force = False,
) -> None:
    """Change a section's place in the document."""
    plan_id, section_id = anchor_ref(ref, "section")
    position = place(after, before, required=True)
    write(
        ctx,
        plan_id,
        lambda draft: move_section(draft, section_id, position),
        f"Moved {plan_id}#{section_id}",
        dry_run=dry_run,
        force=force,
    )


@group.command("rm")
def remove(
    ctx: typer.Context,
    ref: SectionRef,
    yes: Yes = False,
    dry_run: DryRun = False,
    force: Force = False,
) -> None:
    """Remove a section and its file. Refused while a task builds it."""
    plan_id, section_id = anchor_ref(ref, "section")
    if not dry_run:
        confirm(f"Remove {plan_id}#{section_id} and its file?", yes)
    write(
        ctx,
        plan_id,
        lambda draft: remove_section(draft, section_id),
        f"Removed {plan_id}#{section_id}",
        dry_run=dry_run,
        force=force,
    )
