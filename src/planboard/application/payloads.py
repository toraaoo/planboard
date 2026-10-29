from __future__ import annotations

from dataclasses import asdict
from typing import Any

from ..domain import references
from ..domain.json import JsonObject
from . import diagrams
from .catalog import Catalog
from .ports import LoadedPlan, PlanNotFoundError


def _folder(plan_id: str) -> str:
    return plan_id.rpartition("/")[0]


def _summary(entry: LoadedPlan, problems: list[str]) -> dict[str, Any]:
    plan = entry.plan
    return {
        "id": entry.id,
        "folder": _folder(entry.id),
        "title": plan.title,
        "summary": plan.summary,
        "status": plan.status,
        "tags": plan.tags,
        "updated": plan.updated.isoformat() if plan.updated else None,
        "tasks": [
            {"id": task.id, "title": task.title, "status": task.status}
            for task in plan.tasks
        ],
        "problems": problems,
    }


def list_plans(snapshot: Catalog) -> dict[str, Any]:
    return {
        "plans": [
            _summary(entry, snapshot.problems_for(plan_id))
            for plan_id, entry in snapshot.loaded.items()
        ],
        "broken": [
            {"id": entry.id, "folder": _folder(entry.id), "errors": list(entry.errors)}
            for entry in snapshot.broken.values()
        ],
    }


def get_plan(snapshot: Catalog, plan_id: str) -> dict[str, Any]:
    if plan_id in snapshot.broken:
        entry = snapshot.broken[plan_id]
        return {
            "kind": "broken",
            "id": plan_id,
            "path": f"{plan_id}/",
            "errors": list(entry.errors),
        }
    entry = snapshot.loaded.get(plan_id)
    if entry is None:
        raise PlanNotFoundError(plan_id)
    resolved = references.resolve_all(plan_id, snapshot.plans)
    document: JsonObject = entry.plan.model_dump(
        mode="json", exclude={"schema_", "diagrams"}, exclude_none=True
    )
    diagrams.inline_sources(document, plan_id, snapshot.diagrams)
    return {
        "kind": "plan",
        "id": plan_id,
        "folder": _folder(plan_id),
        "path": f"{plan_id}/",
        "plan": document,
        "resolved": {text: asdict(resolution) for text, resolution in resolved.items()},
        "dependents": [asdict(dependent) for dependent in snapshot.dependents(plan_id)],
        "problems": snapshot.problems_for(plan_id),
    }
