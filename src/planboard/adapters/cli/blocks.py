from __future__ import annotations

from typing import Annotated, Literal

import typer
from rich.text import Text as RichText

from ...domain.draft import Draft
from ...domain.edits.blocks import (
    add_block,
    move_block,
    remove_block,
    replace_block,
    set_block,
)
from ...domain.json import JsonObject, JsonValue
from . import completion
from .render import terminal
from .shared import (
    WORD,
    DryRun,
    Force,
    JsonFlag,
    Yes,
    anchor_ref,
    confirm,
    console,
    fail,
    missing_plan,
    print_json,
    read_file,
    read_json,
    workspace_of,
    write,
)

group = typer.Typer(
    help="List, add, change, move and remove the blocks of a section.",
    no_args_is_help=True,
)

BlockType = Literal["text", "heading", "list", "table", "callout", "code", "diagram"]

SectionRef = Annotated[
    str,
    typer.Argument(
        click_type=WORD,
        metavar="SECTION",
        help="folder/plan#section",
        autocompletion=completion.anchors("section"),
    ),
]
Number = Annotated[
    int, typer.Argument(metavar="N", help="The block's number in `block list`.")
]
Text = Annotated[
    str | None,
    typer.Option(metavar="MARKUP", help="text, heading, callout. Inline markup works."),
]
Title = Annotated[str | None, typer.Option(metavar="TEXT", help="callout.")]
Tone = Annotated[Literal["note", "warning"] | None, typer.Option(help="callout.")]
Items = Annotated[
    list[str] | None,
    typer.Option(
        "--item", metavar="TEXT", help="list: one item; repeat it. Nest with --json."
    ),
]
Ordered = Annotated[
    bool | None,
    typer.Option("--ordered/--unordered", help="list.", show_default=False),
]
Columns = Annotated[
    str | None, typer.Option(metavar="CELLS", help='table: "Name | Why", |-separated.')
]
Rows = Annotated[
    list[str] | None,
    typer.Option(
        "--row",
        metavar="CELLS",
        help='table: "cell | cell"; repeat it. An empty cell is null.',
    ),
]
Code = Annotated[str | None, typer.Option(metavar="TEXT", help="code.")]
CodeFile = Annotated[
    str | None,
    typer.Option(
        "--from", metavar="FILE", help="code: read it from a file; - is stdin."
    ),
]
Language = Annotated[
    str | None, typer.Option(metavar="NAME", help='code. "" clears it.')
]
Caption = Annotated[
    str | None, typer.Option(metavar="TEXT", help='table, code, diagram. "" clears it.')
]
DiagramRef = Annotated[
    str | None,
    typer.Option("--ref", metavar="#ID", help="diagram: #id or folder/plan#id."),
]
Json = Annotated[
    str | None,
    typer.Option(
        "--json",
        metavar="JSON",
        help="The whole block as JSON, for any type or nesting; - reads stdin.",
    ),
]

# Each option, the block field it sets and the block types it applies to.
FIELDS: dict[str, tuple[str, frozenset[str]]] = {
    "text": ("text", frozenset({"text", "heading", "callout"})),
    "title": ("title", frozenset({"callout"})),
    "tone": ("tone", frozenset({"callout"})),
    "item": ("items", frozenset({"list"})),
    "ordered": ("ordered", frozenset({"list"})),
    "columns": ("columns", frozenset({"table"})),
    "row": ("rows", frozenset({"table"})),
    "code": ("code", frozenset({"code"})),
    "language": ("language", frozenset({"code"})),
    "caption": ("caption", frozenset({"table", "code", "diagram"})),
    "ref": ("ref", frozenset({"diagram"})),
}
CLEARABLE = frozenset({"language", "caption"})


@group.command("list")
def list_blocks(ctx: typer.Context, ref: SectionRef, as_json: JsonFlag = False) -> None:
    """Number a section's blocks, for set, move and rm."""
    plan_id, section_id = anchor_ref(ref, "section")
    workspace = workspace_of(ctx)
    entry = workspace.catalog().loaded.get(plan_id)
    if entry is None:
        missing_plan(workspace, plan_id)
    section = next((s for s in entry.plan.sections if s.id == section_id), None)
    if section is None:
        fail(
            f"No section named '{section_id}' in {plan_id}.",
            f"Run planboard outline {plan_id} for its ids.",
        )
    blocks = [
        block.model_dump(mode="json", exclude_none=True) for block in section.blocks
    ]
    if as_json:
        print_json([{"number": n, **b} for n, b in enumerate(blocks, start=1)])
        return
    width = len(str(len(section.blocks)))
    for number, block in enumerate(section.blocks, start=1):
        line = RichText.assemble(
            (f"{number:>{width}}  ", "dim"),
            (f"{block.type:<8}", "bold"),
            terminal.preview(block),
        )
        console.print(line, no_wrap=True, overflow="ellipsis")


@group.command()
def add(
    ctx: typer.Context,
    ref: SectionRef,
    block_type: Annotated[
        BlockType | None,
        typer.Argument(
            metavar="[TYPE]", help="Optional with --json.", show_default=False
        ),
    ] = None,
    text: Text = None,
    title: Title = None,
    tone: Tone = None,
    item: Items = None,
    ordered: Ordered = None,
    columns: Columns = None,
    row: Rows = None,
    code: Code = None,
    code_file: CodeFile = None,
    language: Language = None,
    caption: Caption = None,
    diagram: DiagramRef = None,
    as_json: Json = None,
    at: Annotated[
        int | None,
        typer.Option(metavar="N", help="Make it block N. Default: the last."),
    ] = None,
    dry_run: DryRun = False,
    force: Force = False,
) -> None:
    """Add a block to a section, at the end unless --at.

    planboard block add api/rate-limiting#design callout --title "Why" --text "…"
    """
    plan_id, section_id = anchor_ref(ref, "section")
    options = _options(
        text,
        title,
        tone,
        item,
        ordered,
        columns,
        row,
        code,
        code_file,
        language,
        caption,
        diagram,
    )
    if as_json is not None:
        if options:
            raise typer.BadParameter("Give --json or field options, not both.")
        block = _json_block(as_json)
        if block_type is not None and block.get("type") != block_type:
            raise typer.BadParameter(f"The JSON block is not a {block_type} block.")
    elif block_type is None:
        raise typer.BadParameter("Give the block TYPE, or the block as --json.")
    else:
        block = {"type": block_type, **_fields(block_type, options, clearing=False)}
    write(
        ctx,
        plan_id,
        lambda draft: add_block(draft, section_id, block, at),
        f"Added a {block.get('type')} block to {plan_id}#{section_id}",
        dry_run=dry_run,
        force=force,
    )


@group.command("set")
def set_fields(
    ctx: typer.Context,
    ref: SectionRef,
    number: Number,
    text: Text = None,
    title: Title = None,
    tone: Tone = None,
    item: Items = None,
    ordered: Ordered = None,
    columns: Columns = None,
    row: Rows = None,
    code: Code = None,
    code_file: CodeFile = None,
    language: Language = None,
    caption: Caption = None,
    diagram: DiagramRef = None,
    as_json: Json = None,
    dry_run: DryRun = False,
    force: Force = False,
) -> None:
    """Change a block's fields, or replace the whole block with --json.

    Lists given with --item or --row replace the old ones.
    """
    plan_id, section_id = anchor_ref(ref, "section")
    options = _options(
        text,
        title,
        tone,
        item,
        ordered,
        columns,
        row,
        code,
        code_file,
        language,
        caption,
        diagram,
    )
    if as_json is not None:
        if options:
            raise typer.BadParameter("Give --json or field options, not both.")
        block = _json_block(as_json)

        def change(draft: Draft) -> None:
            replace_block(draft, section_id, number, block)
    elif not options:
        raise typer.BadParameter("Nothing to change: give a field option or --json.")
    else:
        block_type = _type_of(ctx, plan_id, section_id, number)
        changes = _fields(block_type, options, clearing=True)

        def change(draft: Draft) -> None:
            set_block(draft, section_id, number, changes)

    write(
        ctx,
        plan_id,
        change,
        f"Updated block {number} of {plan_id}#{section_id}",
        dry_run=dry_run,
        force=force,
    )


@group.command()
def move(
    ctx: typer.Context,
    ref: SectionRef,
    number: Number,
    to: Annotated[int, typer.Option(metavar="N", help="Its new number.")],
    dry_run: DryRun = False,
    force: Force = False,
) -> None:
    """Move a block to another place in its section."""
    plan_id, section_id = anchor_ref(ref, "section")
    write(
        ctx,
        plan_id,
        lambda draft: move_block(draft, section_id, number, to),
        f"Moved block {number} of {plan_id}#{section_id} to {to}",
        dry_run=dry_run,
        force=force,
    )


@group.command("rm")
def remove(
    ctx: typer.Context,
    ref: SectionRef,
    number: Number,
    yes: Yes = False,
    dry_run: DryRun = False,
    force: Force = False,
) -> None:
    """Remove a block. A section keeps at least one."""
    plan_id, section_id = anchor_ref(ref, "section")
    if not dry_run:
        confirm(f"Remove block {number} of {plan_id}#{section_id}?", yes)
    write(
        ctx,
        plan_id,
        lambda draft: remove_block(draft, section_id, number),
        f"Removed block {number} of {plan_id}#{section_id}",
        dry_run=dry_run,
        force=force,
    )


def _options(
    text: str | None,
    title: str | None,
    tone: str | None,
    item: list[str] | None,
    ordered: bool | None,
    columns: str | None,
    row: list[str] | None,
    code: str | None,
    code_file: str | None,
    language: str | None,
    caption: str | None,
    diagram: str | None,
) -> dict[str, JsonValue]:
    """The options given, by name, as JSON values."""
    if code is not None and code_file is not None:
        raise typer.BadParameter("Give --code or --from, not both.")
    if code_file is not None:
        code = read_file(code_file)
    given: dict[str, JsonValue | None] = {
        "text": text,
        "title": title,
        "tone": tone,
        "item": list[JsonValue](item) if item else None,
        "ordered": ordered,
        "columns": list[JsonValue](_cells(columns)) if columns is not None else None,
        "row": [list[JsonValue](_cells(r)) for r in row] if row else None,
        "code": code.rstrip("\n") if code is not None else None,
        "language": language,
        "caption": caption,
        "ref": diagram,
    }
    return {name: value for name, value in given.items() if value is not None}


def _fields(
    block_type: str, options: dict[str, JsonValue], *, clearing: bool
) -> dict[str, JsonValue | None]:
    """Block fields from options, refusing options the type does not take."""
    fields: dict[str, JsonValue | None] = {}
    for name, value in options.items():
        key, types = FIELDS[name]
        if block_type not in types:
            flag = "--ordered" if name == "ordered" else f"--{name}"
            raise typer.BadParameter(
                f"{flag} does not apply to a {block_type} block; "
                f"it is for {', '.join(sorted(types))}."
            )
        if name in CLEARABLE and value == "":
            if not clearing:
                continue
            value = None
        fields[key] = value
    return fields


def _cells(text: str) -> list[str | None]:
    return [cell.strip() or None for cell in text.split("|")]


def _json_block(text: str) -> JsonObject:
    value = read_json(read_file(text) if text == "-" else text, "--json")
    if not isinstance(value, dict):
        raise typer.BadParameter("--json must be one block: a JSON object.")
    return value


def _type_of(ctx: typer.Context, plan_id: str, section_id: str, number: int) -> str:
    workspace = workspace_of(ctx)
    entry = workspace.catalog().loaded.get(plan_id)
    if entry is None:
        missing_plan(workspace, plan_id)
    section = next((s for s in entry.plan.sections if s.id == section_id), None)
    if section is None:
        fail(f"No section named '{section_id}'.")
    if not 1 <= number <= len(section.blocks):
        fail(
            f"Section '{section_id}' has {len(section.blocks)} blocks; "
            f"there is no block {number}."
        )
    return section.blocks[number - 1].type
