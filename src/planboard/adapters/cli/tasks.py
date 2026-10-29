from __future__ import annotations

from dataclasses import asdict
from typing import Annotated, Any

import typer

from ...application.catalog import Catalog
from ...domain import references
from ...domain.edits.tasks import (
    add_task,
    move_task,
    remove_task,
    rename_task,
    set_task,
)
from ...domain.ids import Ref
from ...domain.json import JsonObject
from ...domain.plan import TASK_STATUSES, Task, TaskStatus
from . import completion
from .render import terminal
from .shared import (
    CLEAR_HELP,
    LIST_HELP,
    WORD,
    After,
    Before,
    DryRun,
    Force,
    JsonFlag,
    PlanArg,
    Yes,
    anchor_ref,
    clearable,
    collect,
    confirm,
    console,
    fail,
    keep,
    listed,
    missing_plan,
    parse_ref,
    place,
    print_json,
    select_plans,
    workspace_of,
    write,
)

group = typer.Typer(help="Add, edit, move and track tasks.", no_args_is_help=True)

TaskRef = Annotated[
    str,
    typer.Argument(
        click_type=WORD,
        metavar="TASK",
        help="folder/plan#task",
        autocompletion=completion.anchors("task"),
    ),
]
Summary = Annotated[str | None, typer.Option(metavar="TEXT", help=CLEAR_HELP)]
Note = Annotated[
    str | None, typer.Option(metavar="TEXT", help=f"Why, when blocked. {CLEAR_HELP}")
]
DependsOn = Annotated[
    str | None,
    typer.Option(metavar="REFS", help=f"#task or folder/plan#task. {LIST_HELP}"),
]
Sections = Annotated[
    str | None, typer.Option(metavar="IDS", help=f"Section ids it builds. {LIST_HELP}")
]
Diagrams = Annotated[
    str | None, typer.Option(metavar="IDS", help=f"Diagram ids it builds. {LIST_HELP}")
]


PlanFilter = Annotated[
    str | None,
    typer.Argument(
        click_type=WORD,
        metavar="[PLAN]",
        help="folder/plan, or a folder for every plan in it",
        autocompletion=completion.plans,
    ),
]
Tag = Annotated[
    str | None,
    typer.Option(metavar="NAME", help="Only plans with this tag.", show_default=False),
]


def board(
    ctx: typer.Context,
    plan: PlanFilter = None,
    tag: Tag = None,
    status: Annotated[
        str | None,
        typer.Option(
            "--status",
            metavar="STATUSES",
            help="Only these columns, comma-separated: todo,doing,blocked,done.",
            show_default=False,
        ),
    ] = None,
    as_json: JsonFlag = False,
) -> None:
    """Show tasks by status, for every plan, one plan or a folder of plans."""
    snapshot = workspace_of(ctx).catalog()
    plan_ids = select_plans(ctx, snapshot, plan, tag)
    columns = _statuses(status)
    if not as_json:
        console.print(terminal.board(snapshot, plan_ids, columns))
        return
    plans = snapshot.plans
    print_json(
        [
            {
                "plan": plan_id,
                **task.model_dump(mode="json", exclude_none=True),
                "waitingOn": [
                    item.ref for item in references.waiting_on(plan_id, task, plans)
                ],
            }
            for plan_id in plan_ids
            for task in plans[plan_id].tasks
            if task.status in columns
        ]
    )


def ready(
    ctx: typer.Context,
    plan: PlanFilter = None,
    tag: Tag = None,
    as_json: JsonFlag = False,
) -> None:
    """What to pick up: tasks in progress, then todo tasks whose dependencies are done.

    When nothing is ready, it shows what the waiting tasks wait on.
    """
    snapshot = workspace_of(ctx).catalog()
    plan_ids = set(select_plans(ctx, snapshot, plan, tag))
    plans = snapshot.plans
    readies = references.readies(plans)
    started = [item for item in references.in_progress(plans) if item[0] in plan_ids]
    ready_now = [item for item in references.ready(plans) if item[0] in plan_ids]
    waiting = [
        (plan_id, task)
        for plan_id in plans
        if plan_id in plan_ids and plans[plan_id].status != "archived"
        for task in plans[plan_id].tasks
        if task.status == "todo" and (plan_id, task) not in ready_now
    ]
    if not as_json:
        console.print(terminal.ready(snapshot, started, ready_now, waiting, readies))
        return

    def item(plan_id: str, task: Task) -> dict[str, Any]:
        return {
            "plan": plan_id,
            **task.model_dump(mode="json", exclude_none=True),
            "waitingOn": [
                found.ref for found in references.waiting_on(plan_id, task, plans)
            ],
            "readies": readies.get(str(Ref(plan_id, task.id)), []),
        }

    print_json(
        {
            "ready": [item(*pair) for pair in ready_now],
            "doing": [item(*pair) for pair in started if pair[1].status == "doing"],
            "blocked": [item(*pair) for pair in started if pair[1].status == "blocked"],
            "waiting": [item(*pair) for pair in waiting],
        }
    )


@group.command("show")
def show_task(ctx: typer.Context, ref: TaskRef, as_json: JsonFlag = False) -> None:
    """One task: its status, what it waits on, what needs it and what it builds."""
    plan_id, task_id = anchor_ref(ref, "task")
    snapshot = workspace_of(ctx).catalog()
    show_one(ctx, snapshot, plan_id, task_id, as_json=as_json)


def show_one(
    ctx: typer.Context,
    snapshot: Catalog,
    plan_id: str,
    task_id: str,
    *,
    as_json: bool,
) -> None:
    entry = snapshot.loaded.get(plan_id)
    if entry is None:
        missing_plan(workspace_of(ctx), plan_id)
    task = entry.plan.task(task_id)
    if task is None:
        fail(
            f"No task named '{task_id}' in {plan_id}.",
            f"Run planboard outline {plan_id} for its tasks.",
        )
    plans = snapshot.plans
    if not as_json:
        console.print(terminal.task(snapshot, plan_id, task))
        return
    resolved = references.resolve_all(plan_id, plans)
    print_json(
        {
            "plan": plan_id,
            "position": entry.plan.tasks.index(task) + 1,
            **task.model_dump(mode="json", exclude_none=True),
            "dependsOn": [asdict(resolved[text]) for text in task.depends_on],
            "waitingOn": [
                found.ref for found in references.waiting_on(plan_id, task, plans)
            ],
            "neededBy": references.needed_by(plan_id, task.id, plans),
            "readies": references.readies(plans).get(str(Ref(plan_id, task.id)), []),
        }
    )


def _statuses(text: str | None) -> list[TaskStatus]:
    if text is None:
        return list(TASK_STATUSES)
    names = [name.strip() for name in text.split(",") if name.strip()]
    chosen: list[TaskStatus] = [name for name in TASK_STATUSES if name in names]
    unknown = sorted(set(names) - set(chosen))
    if unknown or not chosen:
        raise typer.BadParameter(
            f"Unknown status {', '.join(unknown) or text!r}; "
            f"use {', '.join(TASK_STATUSES)}."
        )
    return chosen


@group.command()
def status(
    ctx: typer.Context,
    ref: TaskRef,
    new_status: Annotated[TaskStatus, typer.Argument(metavar="STATUS")],
    note: Note = None,
    dry_run: DryRun = False,
    force: Force = False,
) -> None:
    """Move a task to another column: todo, doing, blocked or done."""
    plan_id, task_id = anchor_ref(ref, "task")
    changes = collect(("status", new_status, keep), ("note", note, clearable))
    write(
        ctx,
        plan_id,
        lambda draft: set_task(draft, task_id, changes),
        f"{plan_id}#{task_id} is {new_status}",
        dry_run=dry_run,
        force=force,
    )


@group.command()
def add(
    ctx: typer.Context,
    plan: PlanArg,
    task_id: Annotated[
        str, typer.Argument(click_type=WORD, metavar="ID", help="kebab-case id")
    ],
    title: Annotated[
        str,
        typer.Option(
            metavar="TEXT",
        ),
    ],
    status: Annotated[TaskStatus | None, typer.Option()] = None,
    summary: Summary = None,
    note: Note = None,
    depends_on: DependsOn = None,
    sections: Sections = None,
    diagrams: Diagrams = None,
    after: After = None,
    before: Before = None,
    dry_run: DryRun = False,
    force: Force = False,
) -> None:
    """Add a task, at the end of the build order unless placed."""
    plan_id = parse_ref(plan).plan_id
    position = place(after, before)
    fields = collect(
        ("id", task_id, keep),
        ("title", title, keep),
        ("status", status, keep),
        ("summary", summary, clearable),
        ("note", note, clearable),
        ("dependsOn", depends_on, listed),
        ("sections", sections, listed),
        ("diagrams", diagrams, listed),
    )
    task: JsonObject = {k: v for k, v in fields.items() if v is not None}
    write(
        ctx,
        plan_id,
        lambda draft: add_task(draft, task, position),
        f"Added {plan_id}#{task_id}",
        dry_run=dry_run,
        force=force,
    )


@group.command("set")
def set_fields(
    ctx: typer.Context,
    ref: TaskRef,
    title: Annotated[
        str | None,
        typer.Option(
            metavar="TEXT",
        ),
    ] = None,
    summary: Summary = None,
    note: Note = None,
    depends_on: DependsOn = None,
    sections: Sections = None,
    diagrams: Diagrams = None,
    dry_run: DryRun = False,
    force: Force = False,
) -> None:
    """Change a task's title, summary, note, dependencies or what it builds."""
    plan_id, task_id = anchor_ref(ref, "task")
    changes = collect(
        ("title", title, keep),
        ("summary", summary, clearable),
        ("note", note, clearable),
        ("dependsOn", depends_on, listed),
        ("sections", sections, listed),
        ("diagrams", diagrams, listed),
    )
    write(
        ctx,
        plan_id,
        lambda draft: set_task(draft, task_id, changes),
        f"Updated {plan_id}#{task_id}",
        dry_run=dry_run,
        force=force,
    )


@group.command()
def move(
    ctx: typer.Context,
    ref: TaskRef,
    after: After = None,
    before: Before = None,
    dry_run: DryRun = False,
    force: Force = False,
) -> None:
    """Change a task's place in the build order."""
    plan_id, task_id = anchor_ref(ref, "task")
    position = place(after, before, required=True)
    write(
        ctx,
        plan_id,
        lambda draft: move_task(draft, task_id, position),
        f"Moved {plan_id}#{task_id}",
        dry_run=dry_run,
        force=force,
    )


@group.command("rm")
def remove(
    ctx: typer.Context,
    ref: TaskRef,
    yes: Yes = False,
    dry_run: DryRun = False,
    force: Force = False,
) -> None:
    """Remove a task. Refused while another task, in any plan, depends on it."""
    plan_id, task_id = anchor_ref(ref, "task")
    if not dry_run:
        confirm(f"Remove {plan_id}#{task_id}?", yes)
    write(
        ctx,
        plan_id,
        lambda draft: remove_task(draft, task_id),
        f"Removed {plan_id}#{task_id}",
        dry_run=dry_run,
        force=force,
    )


@group.command()
def rename(
    ctx: typer.Context,
    ref: TaskRef,
    new_id: Annotated[
        str, typer.Argument(click_type=WORD, metavar="ID", help="kebab-case id")
    ],
    dry_run: DryRun = False,
    force: Force = False,
) -> None:
    """Change a task's id and the dependencies on it in its plan.

    Refused while another plan depends on the old id, unless --force.
    """
    plan_id, task_id = anchor_ref(ref, "task")
    write(
        ctx,
        plan_id,
        lambda draft: rename_task(draft, plan_id, task_id, new_id),
        f"Renamed {plan_id}#{task_id} to #{new_id}",
        dry_run=dry_run,
        force=force,
    )
