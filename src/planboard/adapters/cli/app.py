from __future__ import annotations

from importlib.metadata import version
from pathlib import Path
from typing import Annotated

import typer

from ...config import DATA_ENV, ConfigError, discover
from . import blocks, diagrams, plans, project, sections, skills, tasks
from .shared import Session, console, errors, fail

EXAMPLES = """\
[bold]Examples[/bold]

[dim]# start a workspace, write a plan, read it[/dim]
planboard init
planboard new api/rate-limiting --title "Rate limiting"
planboard outline

[dim]# what to work on, and moving it on the board[/dim]
planboard next
planboard task status api/rate-limiting#middleware doing

[dim]# the web app, and your coding agents[/dim]
planboard serve
planboard skill install

Exit codes: 0 done, 1 refused or problems found, 2 wrong usage."""

app = typer.Typer(
    name="planboard",
    help="Implementation plans as JSON: read, edit, validate and track them.\n\n"
    "A reference is folder/plan, or folder/plan#id for a task, section or diagram.",
    epilog=EXAMPLES,
    no_args_is_help=True,
    rich_markup_mode="rich",
    pretty_exceptions_show_locals=False,
    context_settings={"help_option_names": ["-h", "--help"]},
)


def _print_version(value: bool) -> None:
    if value:
        console.print(f"planboard {version('planboard')}", highlight=False)
        raise typer.Exit()


@app.callback()
def configure(
    ctx: typer.Context,
    data: Annotated[
        Path | None,
        typer.Option(
            metavar="DIR",
            file_okay=False,
            help=f"Folder holding the plans. Also {DATA_ENV}. "
            "Default: the nearest planboard.toml, else your user data folder.",
            show_default=False,
        ),
    ] = None,
    quiet: Annotated[
        bool, typer.Option("--quiet", "-q", help="Print only data and errors.")
    ] = False,
    no_color: Annotated[
        bool, typer.Option("--no-color", help="Plain text. Also NO_COLOR.")
    ] = False,
    _version: Annotated[
        bool,
        typer.Option(
            "--version",
            callback=_print_version,
            is_eager=True,
            help="Print the version and exit.",
        ),
    ] = False,
) -> None:
    if no_color:
        console.no_color = errors.no_color = True
    try:
        settings = discover(data)
    except ConfigError as error:
        fail(str(error), "Fix or remove the file, or pass --data.")
    ctx.obj = Session(settings, quiet=quiet)


READ = "Read"
WRITE = "Write"
WORKSPACE = "Workspace"

app.command(rich_help_panel=READ)(plans.outline)
app.command(rich_help_panel=READ)(plans.show)
app.command(rich_help_panel=READ)(tasks.board)
app.command("next", rich_help_panel=READ)(tasks.ready)
app.command(rich_help_panel=READ)(plans.search)
app.command(rich_help_panel=READ)(project.validate)

app.command(rich_help_panel=WRITE)(plans.new)
app.add_typer(plans.group, name="plan", rich_help_panel=WRITE)
app.add_typer(tasks.group, name="task", rich_help_panel=WRITE)
app.add_typer(sections.group, name="section", rich_help_panel=WRITE)
app.add_typer(blocks.group, name="block", rich_help_panel=WRITE)
app.add_typer(diagrams.group, name="diagram", rich_help_panel=WRITE)

app.command(rich_help_panel=WORKSPACE)(project.init)
app.command(rich_help_panel=WORKSPACE)(project.where)
app.command(rich_help_panel=WORKSPACE)(project.serve)
app.command(rich_help_panel=WORKSPACE)(project.schema)
app.add_typer(skills.group, name="skill", rich_help_panel=WORKSPACE)


def main() -> None:
    app()
