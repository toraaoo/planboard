from __future__ import annotations

from typing import Annotated

import typer

from ...domain.edits.diagrams import (
    add_diagram,
    remove_diagram,
    rename_diagram,
    set_diagram,
)
from . import completion
from .shared import (
    WORD,
    DryRun,
    Force,
    PlanArg,
    Yes,
    anchor_ref,
    confirm,
    parse_ref,
    read_source,
    write,
)

group = typer.Typer(
    help="Add, change, rename and remove Mermaid diagrams.", no_args_is_help=True
)

DiagramRef = Annotated[
    str,
    typer.Argument(
        click_type=WORD,
        metavar="DIAGRAM",
        help="folder/plan#diagram",
        autocompletion=completion.anchors("diagram"),
    ),
]
Source = Annotated[str | None, typer.Option(metavar="TEXT", help="Mermaid source.")]
SourceFile = Annotated[
    str | None,
    typer.Option(
        "--from", metavar="FILE", help="Read the source from a file; - is stdin."
    ),
]


@group.command()
def add(
    ctx: typer.Context,
    plan: PlanArg,
    diagram_id: Annotated[
        str, typer.Argument(click_type=WORD, metavar="ID", help="kebab-case id")
    ],
    alt: Annotated[
        str, typer.Option(metavar="TEXT", help="What the diagram shows, for readers.")
    ],
    source: Source = None,
    source_file: SourceFile = None,
    inline: Annotated[
        bool,
        typer.Option(
            help="Keep the source in plan.json, not diagrams/.", show_default=False
        ),
    ] = False,
    section: Annotated[
        str | None,
        typer.Option(
            metavar="ID",
            help="Show it at the end of this section. To place it elsewhere: "
            "planboard block add <section> diagram --ref #id --at N.",
        ),
    ] = None,
    caption: Annotated[
        str | None,
        typer.Option(metavar="TEXT", help="Caption for the block --section adds."),
    ] = None,
    dry_run: DryRun = False,
    force: Force = False,
) -> None:
    """Add a diagram, written to diagrams/<id>.mmd."""
    plan_id = parse_ref(plan).plan_id
    text = read_source(source, source_file)
    if text is None:
        raise typer.BadParameter("Give the Mermaid source with --source or --from.")
    write(
        ctx,
        plan_id,
        lambda draft: add_diagram(
            draft,
            diagram_id,
            alt,
            text,
            inline=inline,
            section=section,
            caption=caption,
        ),
        f"Added diagram {plan_id}#{diagram_id}",
        dry_run=dry_run,
        force=force,
    )


@group.command("set")
def set_fields(
    ctx: typer.Context,
    ref: DiagramRef,
    alt: Annotated[
        str | None,
        typer.Option(
            metavar="TEXT",
        ),
    ] = None,
    source: Source = None,
    source_file: SourceFile = None,
    dry_run: DryRun = False,
    force: Force = False,
) -> None:
    """Change a diagram's alt text or source."""
    plan_id, diagram_id = anchor_ref(ref, "diagram")
    text = read_source(source, source_file)
    if text is None and alt is None:
        raise typer.BadParameter("Nothing to change: give --alt, --source or --from.")
    write(
        ctx,
        plan_id,
        lambda draft: set_diagram(draft, diagram_id, alt, text),
        f"Updated diagram {plan_id}#{diagram_id}",
        dry_run=dry_run,
        force=force,
    )


@group.command("rm")
def remove(
    ctx: typer.Context,
    ref: DiagramRef,
    yes: Yes = False,
    dry_run: DryRun = False,
    force: Force = False,
) -> None:
    """Remove a diagram, its file, the blocks that show it and task links to it."""
    plan_id, diagram_id = anchor_ref(ref, "diagram")
    if not dry_run:
        confirm(
            f"Remove diagram {plan_id}#{diagram_id} and every block showing it?", yes
        )
    write(
        ctx,
        plan_id,
        lambda draft: remove_diagram(draft, plan_id, diagram_id),
        f"Removed diagram {plan_id}#{diagram_id}",
        dry_run=dry_run,
        force=force,
    )


@group.command()
def rename(
    ctx: typer.Context,
    ref: DiagramRef,
    new_id: Annotated[
        str, typer.Argument(click_type=WORD, metavar="ID", help="kebab-case id")
    ],
    dry_run: DryRun = False,
    force: Force = False,
) -> None:
    """Change a diagram's id: its file, the blocks that show it, tasks and #links."""
    plan_id, diagram_id = anchor_ref(ref, "diagram")
    write(
        ctx,
        plan_id,
        lambda draft: rename_diagram(draft, plan_id, diagram_id, new_id),
        f"Renamed diagram {plan_id}#{diagram_id} to #{new_id}",
        dry_run=dry_run,
        force=force,
    )
