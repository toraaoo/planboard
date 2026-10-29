from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict
from typing import Any

from ....application.catalog import Catalog
from ....application.ports import LoadedPlan
from ....domain import references
from ....domain.layout import PLAN_FILE, section_file


def overview(snapshot: Catalog) -> str:
    rows: list[tuple[str, ...]] = []
    for plan_id, entry in snapshot.loaded.items():
        plan = entry.plan
        done = references.progress(plan)["done"]
        problems = len(snapshot.problems_for(plan_id))
        note = f"  ({_count(problems, 'problem')})" if problems else ""
        rows.append(
            (plan_id, plan.status, f"{done}/{len(plan.tasks)} done", plan.title + note)
        )
    for plan_id, broken in snapshot.broken.items():
        errors = _count(len(broken.errors), "error")
        rows.append((plan_id, "broken", errors, "run planboard validate"))
    return "\n".join(_table(rows)) if rows else "No plans yet."


def plan_outline(snapshot: Catalog, entry: LoadedPlan) -> str:
    plan = entry.plan
    resolved = references.resolve_all(entry.id, snapshot.plans)
    facts = [plan.status]
    if plan.updated:
        facts.append(f"updated {plan.updated.isoformat()}")
    if plan.branch:
        facts.append(f"branch {plan.branch}")
    if plan.tags:
        facts.append(f"tags {', '.join(plan.tags)}")
    lines = [
        f"{entry.id}  {plan.title}",
        " · ".join(facts),
        f"{entry.path}/{PLAN_FILE}",
        "",
        plan.summary,
    ]
    if plan.depends_on:
        lines += ["", f"Depends on  {_refs(plan.depends_on, resolved)}"]

    lines += ["", "Sections"]
    lines += _table(
        [
            (section.id, section_file(section.id), _count(len(section.blocks), "block"))
            for section in plan.sections
        ],
        indent=2,
    )

    if plan.diagrams:
        lines += ["", "Diagrams"]
        lines += _table(
            [
                (diagram_id, diagram.file or "inline in plan.json")
                for diagram_id, diagram in plan.diagrams.items()
            ],
            indent=2,
        )

    if plan.tasks:
        lines += ["", "Tasks"]
        for number, task in enumerate(plan.tasks, start=1):
            lines.append(f"  {number}. {task.id}  [{task.status}]  {task.title}")
            if task.depends_on:
                lines.append(f"       after {_refs(task.depends_on, resolved)}")
            if task.sections or task.diagrams:
                lines.append(
                    f"       builds {', '.join(task.sections + task.diagrams)}"
                )
            if task.note:
                lines.append(f"       note {task.note}")

    dependents = snapshot.dependents(entry.id)
    if dependents:
        lines += ["", "Depended on by"]
        lines += [
            f"  {dependent.plan_id}"
            + (f"#{dependent.task_id}" if dependent.task_id else "")
            + (f" → #{dependent.target}" if dependent.target else "")
            for dependent in dependents
        ]

    problems = snapshot.problems_for(entry.id)
    if problems:
        lines += ["", "Problems"]
        lines += [f"  {problem}" for problem in problems]
    return "\n".join(lines)


def plan_json(snapshot: Catalog, entry: LoadedPlan) -> dict[str, Any]:
    plan = entry.plan
    plans = snapshot.plans
    resolved = references.resolve_all(entry.id, plans)
    return {
        "id": entry.id,
        "path": str(entry.path),
        **plan.model_dump(
            mode="json",
            include={"title", "summary", "status", "updated", "branch", "tags"},
        ),
        "dependsOn": [asdict(resolved[text]) for text in plan.depends_on],
        "sections": [
            {
                "id": section.id,
                "title": section.title,
                "file": section_file(section.id),
                "blocks": len(section.blocks),
            }
            for section in plan.sections
        ],
        "diagrams": [
            {"id": diagram_id, "file": diagram.file, "alt": diagram.alt}
            for diagram_id, diagram in plan.diagrams.items()
        ],
        "tasks": [
            {
                **task.model_dump(mode="json", exclude_none=True),
                "waitingOn": [
                    item.ref for item in references.waiting_on(entry.id, task, plans)
                ],
            }
            for task in plan.tasks
        ],
        "dependents": [asdict(item) for item in snapshot.dependents(entry.id)],
        "problems": snapshot.problems_for(entry.id),
    }


def _refs(texts: Sequence[str], resolved: dict[str, references.Resolution]) -> str:
    return ", ".join(f"{text} ({resolved[text].state})" for text in texts)


def _count(number: int, noun: str) -> str:
    return f"{number} {noun}{'' if number == 1 else 's'}"


def _table(rows: Sequence[tuple[str, ...]], indent: int = 0) -> list[str]:
    widths = [max(len(row[column]) for row in rows) for column in range(len(rows[0]))]
    return [
        " " * indent
        + "  ".join(
            cell.ljust(width) for cell, width in zip(row, widths, strict=True)
        ).rstrip()
        for row in rows
    ]
