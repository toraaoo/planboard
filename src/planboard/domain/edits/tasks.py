from __future__ import annotations

from ..draft import Draft
from ..json import JsonObject, JsonValue
from .document import (
    Changes,
    Place,
    apply_changes,
    ids_of,
    index_of,
    position_of,
    rename_ref,
    strings_in,
    task_list,
)
from .errors import EditError


def set_task(draft: Draft, task_id: str, changes: Changes) -> None:
    tasks = task_list(draft)
    apply_changes(tasks[index_of(ids_of(tasks), task_id, "task")], changes)
    draft.plan["tasks"] = list[JsonValue](tasks)


def add_task(draft: Draft, task: JsonObject, place: Place) -> None:
    tasks = task_list(draft)
    task_id = str(task["id"])
    if task_id in ids_of(tasks):
        raise EditError(f"Task '{task_id}' already exists.")
    tasks.insert(position_of(ids_of(tasks), place), task)
    draft.plan["tasks"] = list[JsonValue](tasks)


def remove_task(draft: Draft, task_id: str) -> None:
    tasks = task_list(draft)
    index = index_of(ids_of(tasks), task_id, "task")
    waiting = [
        str(task["id"])
        for task in tasks
        if f"#{task_id}" in strings_in(task, "dependsOn")
    ]
    if waiting:
        raise EditError(f"'{task_id}' is a dependency of: {', '.join(waiting)}.")
    del tasks[index]
    draft.plan["tasks"] = list[JsonValue](tasks)


def move_task(draft: Draft, task_id: str, place: Place) -> None:
    tasks = task_list(draft)
    task = tasks.pop(index_of(ids_of(tasks), task_id, "task"))
    tasks.insert(position_of(ids_of(tasks), place), task)
    draft.plan["tasks"] = list[JsonValue](tasks)


def rename_task(draft: Draft, plan_id: str, old: str, new: str) -> None:
    """Change a task's id and the dependencies on it within the plan."""
    tasks = task_list(draft)
    index = index_of(ids_of(tasks), old, "task")
    if new in ids_of(tasks):
        raise EditError(f"Task '{new}' already exists.")
    tasks[index]["id"] = new
    for task in tasks:
        names = strings_in(task, "dependsOn")
        if names:
            task["dependsOn"] = [rename_ref(n, plan_id, old, new) for n in names]
    draft.plan["tasks"] = list[JsonValue](tasks)
