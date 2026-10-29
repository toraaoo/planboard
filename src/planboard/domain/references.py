from __future__ import annotations

import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from typing import Literal

from .ids import Ref
from .json import JsonValue
from .plan import Plan, Task, TaskStatus

Progress = dict[TaskStatus, int]
RefState = Literal["done", "pending", "missing"]


@dataclass(frozen=True, slots=True)
class Problem:
    plan_id: str
    message: str


@dataclass(frozen=True, slots=True)
class Resolution:
    ref: str
    plan_id: str
    task_id: str | None
    title: str | None
    plan_title: str | None
    state: RefState


def progress(plan: Plan) -> Progress:
    counts: Progress = {"todo": 0, "doing": 0, "blocked": 0, "done": 0}
    for task in plan.tasks:
        counts[task.status] += 1
    return counts


def is_complete(plan: Plan) -> bool:
    return bool(plan.tasks) and all(task.status == "done" for task in plan.tasks)


def resolve(text: str, plan_id: str, plans: Mapping[str, Plan]) -> Resolution:
    ref = Ref.parse(text, plan_id)
    target = plans.get(ref.plan_id)
    if target is None:
        return Resolution(text, ref.plan_id, ref.anchor, None, None, "missing")
    if ref.anchor is None:
        state: RefState = "done" if is_complete(target) else "pending"
        return Resolution(text, ref.plan_id, None, target.title, target.title, state)
    task = target.task(ref.anchor)
    if task is None:
        return Resolution(text, ref.plan_id, ref.anchor, None, target.title, "missing")
    state = "done" if task.status == "done" else "pending"
    return Resolution(text, ref.plan_id, ref.anchor, task.title, target.title, state)


def waiting_on(plan_id: str, task: Task, plans: Mapping[str, Plan]) -> list[Resolution]:
    texts = [*plans[plan_id].depends_on, *task.depends_on]
    resolutions = [resolve(text, plan_id, plans) for text in texts]
    return [resolution for resolution in resolutions if resolution.state != "done"]


def ready(plans: Mapping[str, Plan]) -> list[tuple[str, Task]]:
    return [
        (plan_id, task)
        for plan_id, plan in plans.items()
        if plan.status != "archived"
        for task in plan.tasks
        if task.status == "todo" and not waiting_on(plan_id, task, plans)
    ]


def in_progress(plans: Mapping[str, Plan]) -> list[tuple[str, Task]]:
    """Doing, then blocked tasks, in plans that are not archived."""
    return [
        (plan_id, task)
        for wanted in ("doing", "blocked")
        for plan_id, plan in plans.items()
        if plan.status != "archived"
        for task in plan.tasks
        if task.status == wanted
    ]


def readies(plans: Mapping[str, Plan]) -> dict[str, list[str]]:
    """For each unfinished task, the todo tasks that wait on it alone."""
    found: dict[str, list[str]] = {}
    for plan_id, plan in plans.items():
        if plan.status == "archived":
            continue
        for task in plan.tasks:
            if task.status != "todo":
                continue
            waiting = waiting_on(plan_id, task, plans)
            if len(waiting) == 1 and waiting[0].task_id is not None:
                key = str(Ref(waiting[0].plan_id, waiting[0].task_id))
                found.setdefault(key, []).append(str(Ref(plan_id, task.id)))
    return found


def needed_by(plan_id: str, task_id: str, plans: Mapping[str, Plan]) -> list[str]:
    """Tasks and plans whose dependencies name this task, or its whole plan."""
    wanted = {str(Ref(plan_id, task_id)), plan_id}
    found: list[str] = []
    for other_id, other in plans.items():
        if other_id != plan_id and wanted & _targets(other.depends_on, other_id):
            found.append(other_id)
        for task in other.tasks:
            if other_id == plan_id and task.id == task_id:
                continue
            if str(Ref(plan_id, task_id)) in _targets(task.depends_on, other_id) or (
                other_id != plan_id and plan_id in _targets(task.depends_on, other_id)
            ):
                found.append(str(Ref(other_id, task.id)))
    return found


def _targets(texts: list[str], plan_id: str) -> set[str]:
    return {str(Ref.parse(text, plan_id)) for text in texts}


def plan_refs(plan: Plan) -> Iterator[str]:
    yield from plan.depends_on
    for task in plan.tasks:
        yield from task.depends_on


def resolve_all(plan_id: str, plans: Mapping[str, Plan]) -> dict[str, Resolution]:
    return {text: resolve(text, plan_id, plans) for text in plan_refs(plans[plan_id])}


def check(plans: Mapping[str, Plan]) -> list[Problem]:
    problems: list[Problem] = []
    for plan_id, plan in plans.items():
        for text in plan_refs(plan):
            if resolve(text, plan_id, plans).state == "missing":
                problems.append(Problem(plan_id, f"'{text}' does not resolve"))
        for href in links(plan):
            if not link_resolves(href, plan_id, plans):
                problems.append(Problem(plan_id, f"link '{href}' does not resolve"))
    problems.extend(_cycles(plans))
    return problems


def unresolved_diagrams(plans: Mapping[str, Plan]) -> list[Problem]:
    """Diagram blocks whose ref names no diagram, without reading any file."""
    problems: list[Problem] = []
    for plan_id, plan in plans.items():
        for block in plan.diagram_blocks():
            ref = Ref.parse(block.ref, plan_id)
            target = plans.get(ref.plan_id)
            if target is None or (ref.anchor or "") not in target.diagrams:
                problems.append(Problem(plan_id, f"'{block.ref}' does not resolve"))
    return problems


_LINK = re.compile(r"\[[^\]]+\]\(([^)\s]+)\)")
_EXTERNAL = re.compile(r"^(?:https?:|mailto:)")
_NOT_PROSE = frozenset({"source", "code"})


def links(plan: Plan) -> Iterator[str]:
    for text in _prose(plan.model_dump(mode="json")):
        for match in _LINK.finditer(text):
            if not _EXTERNAL.match(match[1]):
                yield match[1]


def link_resolves(href: str, plan_id: str, plans: Mapping[str, Plan]) -> bool:
    try:
        ref = Ref.parse(href, plan_id)
    except ValueError:
        return False
    target = plans.get(ref.plan_id)
    return target is not None and (ref.anchor is None or ref.anchor in target.anchors())


def _prose(value: JsonValue) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from _prose(item)
    elif isinstance(value, dict):
        for key, item in value.items():
            if key not in _NOT_PROSE:
                yield from _prose(item)


def _edges(plans: Mapping[str, Plan]) -> dict[str, set[str]]:
    edges: dict[str, set[str]] = {}
    for plan_id, plan in plans.items():
        plan_node = str(Ref(plan_id, None))
        plan_deps = {str(Ref.parse(text, plan_id)) for text in plan.depends_on}
        edges.setdefault(plan_node, set()).update(plan_deps)
        for task in plan.tasks:
            task_node = str(Ref(plan_id, task.id))
            edges[plan_node].add(task_node)
            task_deps = {str(Ref.parse(text, plan_id)) for text in task.depends_on}
            edges.setdefault(task_node, set()).update(task_deps | plan_deps)
    return edges


def _cycles(plans: Mapping[str, Plan]) -> list[Problem]:
    edges = _edges(plans)
    visiting: set[str] = set()
    finished: set[str] = set()
    problems: list[Problem] = []

    def visit(node: str, trail: list[str]) -> None:
        if node in finished:
            return
        if node in visiting:
            loop = [*trail[trail.index(node) :], node]
            problems.append(
                Problem(
                    Ref.parse(node, "").plan_id, f"dependency cycle: {' → '.join(loop)}"
                )
            )
            return
        visiting.add(node)
        for target in sorted(edges.get(node, ())):
            visit(target, [*trail, node])
        visiting.discard(node)
        finished.add(node)

    for node in sorted(edges):
        visit(node, [])
    return problems
