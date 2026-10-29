"""Shell completion for plan references, folder/plan and folder/plan#id, and agents."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import typer

from ...application.ports import LoadedPlan
from ...bootstrap import open_workspace
from ..filesystem.agents import AGENTS

type Completer = Callable[[typer.Context, str], list[tuple[str, str]]]


def plans(ctx: typer.Context, incomplete: str) -> list[tuple[str, str]]:
    return [
        (entry.id, entry.plan.title)
        for entry in _loaded(ctx)
        if entry.id.startswith(incomplete)
    ]


def agents(incomplete: str) -> list[tuple[str, str]]:
    return [
        (name, agent.label)
        for name, agent in AGENTS.items()
        if name.startswith(incomplete)
    ]


def anchors(kind: str) -> Completer:
    """Complete folder/plan, then the tasks, sections or diagrams after the #."""

    def complete(ctx: typer.Context, incomplete: str) -> list[tuple[str, str]]:
        if "#" not in incomplete:
            return [(f"{plan_id}#", title) for plan_id, title in plans(ctx, incomplete)]
        found: list[tuple[str, str]] = []
        for entry in _loaded(ctx):
            for anchor, title in _anchors(entry, kind):
                ref = f"{entry.id}#{anchor}"
                if ref.startswith(incomplete):
                    found.append((ref, title))
        return found

    return complete


def _anchors(entry: LoadedPlan, kind: str) -> list[tuple[str, str]]:
    plan = entry.plan
    if kind == "task":
        return [(task.id, f"{task.status} · {task.title}") for task in plan.tasks]
    if kind == "diagram":
        return [(diagram_id, d.alt) for diagram_id, d in plan.diagrams.items()]
    sections = [(section.id, section.title) for section in plan.sections]
    if kind == "section":
        return sections
    return sections + [(diagram_id, d.alt) for diagram_id, d in plan.diagrams.items()]


def _loaded(ctx: typer.Context) -> list[LoadedPlan]:
    data = ctx.find_root().params.get("data")
    try:
        workspace = open_workspace(Path(data) if data else None)
        return list(workspace.catalog().loaded.values())
    except Exception:
        return []
