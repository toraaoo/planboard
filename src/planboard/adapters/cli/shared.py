from __future__ import annotations

import difflib
import json
import sys
from collections.abc import Callable, Generator
from contextlib import contextmanager
from functools import cached_property
from pathlib import Path
from typing import Annotated, NoReturn

import typer
from rich.console import Console
from typer._click.core import Context, Parameter  # vendored click, typer>=0.27
from typer._click.types import StringParamType

from ...application.catalog import Catalog
from ...application.ports import (
    BreaksReferencesError,
    EditResult,
    PlanNotFoundError,
)
from ...application.workspace import Workspace
from ...bootstrap import workspace_for
from ...config import Settings
from ...domain.draft import Draft, InvalidPlanError
from ...domain.edits.document import Place
from ...domain.edits.errors import EditError
from ...domain.ids import Ref
from ...domain.json import JsonValue
from . import completion


class _Untyped(StringParamType):
    """A string argument without a <str> label in --help; its name says enough."""

    def get_metavar(self, param: Parameter, ctx: Context) -> str:
        return ""


WORD = _Untyped()

console = Console(soft_wrap=True)
errors = Console(stderr=True, soft_wrap=True)


class Session:
    """What the root callback resolved, shared by every command of one run."""

    def __init__(self, settings: Settings, *, quiet: bool = False) -> None:
        self.settings = settings
        self.quiet = quiet

    @cached_property
    def workspace(self) -> Workspace:
        return workspace_for(self.settings)


JsonFlag = Annotated[bool, typer.Option("--json", help="Print JSON instead.")]
DryRun = Annotated[
    bool,
    typer.Option(
        "--dry-run", "-n", help="Show what it would change, and change nothing."
    ),
]
Yes = Annotated[bool, typer.Option("--yes", "-y", help="Do not ask to confirm.")]
Force = Annotated[
    bool,
    typer.Option(
        "--force", help="Write even if it breaks references or links in any plan."
    ),
]
After = Annotated[
    str | None, typer.Option(metavar="ID", help="Place it after this id.")
]
Before = Annotated[
    str | None, typer.Option(metavar="ID", help="Place it before this id.")
]
PlanArg = Annotated[
    str,
    typer.Argument(
        metavar="PLAN",
        help="folder/plan",
        autocompletion=completion.plans,
        click_type=WORD,
    ),
]
LIST_HELP = "Comma-separated; an empty string clears it."
CLEAR_HELP = "An empty string clears it."


def session_of(ctx: typer.Context) -> Session:
    session = ctx.find_root().obj
    if not isinstance(session, Session):
        raise RuntimeError("the root callback did not set up the session")
    return session


def workspace_of(ctx: typer.Context) -> Workspace:
    return session_of(ctx).workspace


def fail(message: str, hint: str | None = None, code: int = 1) -> NoReturn:
    errors.print(f"[red]✗[/red] {message}", highlight=False, markup=True)
    if hint:
        errors.print(f"  {hint}", style="dim", highlight=False, markup=False)
    raise typer.Exit(code)


def done(ctx: typer.Context, message: str) -> None:
    if not session_of(ctx).quiet:
        errors.print(f"[green]✓[/green] {message}", highlight=False, soft_wrap=True)


def hint(ctx: typer.Context, message: str) -> None:
    if not session_of(ctx).quiet:
        errors.print(f"  {message}", style="dim", highlight=False, markup=False)


def print_json(value: object) -> None:
    sys.stdout.write(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def parse_ref(text: str) -> Ref:
    try:
        ref = Ref.parse(text, "")
    except ValueError:
        raise typer.BadParameter(f"'{text}' is not a plan reference.") from None
    if not ref.plan_id:
        raise typer.BadParameter(f"'{text}' must start with the plan: folder/plan.")
    return ref


def anchor_ref(text: str, kind: str) -> tuple[str, str]:
    ref = parse_ref(text)
    if ref.anchor is None:
        raise typer.BadParameter(f"'{text}' must name a {kind}: folder/plan#{kind}.")
    return ref.plan_id, ref.anchor


def place(after: str | None, before: str | None, *, required: bool = False) -> Place:
    if after is not None and before is not None:
        raise typer.BadParameter("Give --after or --before, not both.")
    if required and after is None and before is None:
        raise typer.BadParameter("Give --after or --before.")
    return Place(after=after, before=before)


type Convert = Callable[[str], JsonValue | None]


def collect(*fields: tuple[str, str | None, Convert]) -> dict[str, JsonValue | None]:
    changes = {
        key: convert(value) for key, value, convert in fields if value is not None
    }
    if not changes:
        raise typer.BadParameter("Nothing to change: give at least one option.")
    return changes


def keep(text: str) -> JsonValue | None:
    return text


def clearable(text: str) -> JsonValue | None:
    return text or None


def listed(text: str) -> JsonValue | None:
    return [item.strip() for item in text.split(",") if item.strip()] or None


def read_source(source: str | None, source_file: str | None) -> str | None:
    if source is not None and source_file is not None:
        raise typer.BadParameter("Give --source or --from, not both.")
    if source_file is None:
        return source
    return read_file(source_file)


def read_file(name: str) -> str:
    """A file's text; - is stdin."""
    if name == "-":
        return sys.stdin.read()
    try:
        return Path(name).read_text(encoding="utf-8")
    except OSError as error:
        raise typer.BadParameter(f"Cannot read {name}: {error}") from None


def read_json(text: str, what: str) -> JsonValue:
    try:
        value: JsonValue = json.loads(text)
    except ValueError as error:
        raise typer.BadParameter(f"{what} is not valid JSON: {error}") from None
    return value


def select_plans(
    ctx: typer.Context,
    snapshot: Catalog,
    plan: str | None,
    tag: str | None = None,
) -> list[str]:
    """Plan ids, all or one plan or one folder's, keeping those with the tag."""
    plan_ids = list(snapshot.loaded)
    if plan is not None:
        plan_ids = [p for p in plan_ids if p == plan or p.startswith(f"{plan}/")]
        if not plan_ids:
            missing_plan(workspace_of(ctx), plan)
    if tag is not None:
        plan_ids = [p for p in plan_ids if tag in snapshot.loaded[p].plan.tags]
    return plan_ids


def confirm(question: str, yes: bool) -> None:
    """Ask before a removal, only when someone is at the terminal to answer."""
    if yes or not sys.stdin.isatty():
        return
    if not typer.confirm(question, default=False, err=True):
        raise typer.Abort()


def missing_plan(workspace: Workspace, plan_id: str) -> NoReturn:
    close = difflib.get_close_matches(plan_id, workspace.repository.ids(), n=1)
    suggestion = f"Did you mean {close[0]}?" if close else None
    fail(
        f"No plan named '{plan_id}'.",
        suggestion or "Run planboard outline for the list.",
    )


def write(
    ctx: typer.Context,
    plan_id: str,
    change: Callable[[Draft], None],
    message: str,
    *,
    dry_run: bool = False,
    force: bool = False,
) -> EditResult:
    workspace = workspace_of(ctx)
    with refusals(workspace, plan_id):
        result = workspace.edit(plan_id, change, dry_run=dry_run, force=force)
    if dry_run:
        console.print(f"Dry run, nothing written. {plan_id} stays valid.")
        for name in result.written:
            console.print(f"  would write  {plan_id}/{name}", highlight=False)
        for name in result.removed:
            console.print(f"  would remove {plan_id}/{name}", highlight=False)
        return result
    done(ctx, message)
    warn_problems(workspace)
    return result


@contextmanager
def refusals(workspace: Workspace, plan_id: str) -> Generator[None]:
    """Turn a refused write into a message and exit 1."""
    try:
        yield
    except PlanNotFoundError:
        missing_plan(workspace, plan_id)
    except EditError as error:
        fail(str(error))
    except InvalidPlanError as error:
        lines = "\n".join(f"  {line}" for line in error.errors)
        fail(f"Nothing written; {plan_id} would be invalid:\n{lines}")
    except BreaksReferencesError as error:
        width = max(len(problem.plan_id) for problem in error.problems)
        lines = "\n".join(
            f"  {problem.plan_id:<{width}}  {problem.message}"
            for problem in error.problems
        )
        fail(
            f"Nothing written; it would break references:\n{lines}",
            "Change those plans first, or pass --force.",
        )


def warn_problems(workspace: Workspace) -> None:
    problems = workspace.problems()
    if problems:
        errors.print("[yellow]![/yellow] planboard validate reports:", highlight=False)
        for problem in problems:
            errors.print(
                f"  {problem.plan_id}  {problem.message}", highlight=False, markup=False
            )
