from __future__ import annotations

import datetime
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .. import resources
from ..domain import references
from ..domain.edits.errors import EditError
from ..domain.edits.plan import retarget_plan
from ..domain.edits.tasks import set_task
from ..domain.ids import is_plan_id
from ..domain.json import JsonObject, JsonValue
from ..domain.plan import Plan, Task, TaskStatus
from ..domain.references import Problem
from ..domain.search import Hit, search
from . import catalog, payloads
from .catalog import Catalog
from .ports import (
    BreaksReferencesError,
    Change,
    Check,
    EditResult,
    PlanNotFoundError,
    PlanRepository,
)


class Workspace:
    """Every use case of planboard, over one repository of plans.

    The CLI, the web app and library callers all go through this class.
    """

    def __init__(self, repository: PlanRepository) -> None:
        self.repository = repository

    @property
    def root(self) -> Path:
        return self.repository.root

    def catalog(self) -> Catalog:
        """Every plan loaded at once, with the problems across them."""
        return catalog.build(self.repository)

    def version(self) -> str:
        return self.repository.version()

    def problems(self) -> list[Problem]:
        return self.catalog().all_problems()

    def ready(self) -> list[tuple[str, Task]]:
        """Todo tasks whose dependencies are all done."""
        return references.ready(self.catalog().plans)

    def plans(self) -> dict[str, Any]:
        return payloads.list_plans(self.catalog())

    def plan(self, plan_id: str) -> dict[str, Any]:
        return payloads.get_plan(self.catalog(), plan_id)

    def search(self, query: str) -> list[Hit]:
        """Plans, tasks, sections and diagrams whose text contains the query."""
        return search(self.catalog().plans, query)

    def create_plan(
        self,
        plan_id: str,
        title: str | None = None,
        template: str = "feature",
        *,
        fields: Mapping[str, JsonValue] | None = None,
        dry_run: bool = False,
    ) -> Path:
        if not is_plan_id(plan_id):
            raise ValueError(f"'{plan_id}' must be kebab-case segments joined by /.")
        document: JsonObject = {
            **resources.template(template),
            "title": title or plan_id.rpartition("/")[2].replace("-", " ").capitalize(),
            **(fields or {}),
            "updated": datetime.date.today().isoformat(),
        }
        return self.repository.create(plan_id, document, dry_run=dry_run)

    def edit(
        self,
        plan_id: str,
        change: Change,
        *,
        dry_run: bool = False,
        force: bool = False,
    ) -> EditResult:
        """Apply a change to a plan. Nothing is written if the result is invalid,
        or, unless forced, if it breaks a reference in any plan."""
        check = None if force else self._guard(plan_id)
        return self.repository.edit(plan_id, change, dry_run=dry_run, check=check)

    def move_plan(
        self, plan_id: str, new_id: str, *, dry_run: bool = False, force: bool = False
    ) -> EditResult:
        """Give a plan a new id, and point its references to itself at it."""
        if not is_plan_id(new_id):
            raise EditError(f"'{new_id}' must be kebab-case segments joined by /.")
        if new_id == plan_id:
            raise EditError(f"{plan_id} already has that id.")
        old, new = plan_id.split("/"), new_id.split("/")
        if new[: len(old)] == old or old[: len(new)] == new:
            raise EditError("A plan cannot move inside itself, nor around itself.")
        check = None if force else self._guard(plan_id, new_id)
        return self.repository.move(
            plan_id,
            new_id,
            lambda draft: retarget_plan(draft, plan_id, new_id),
            dry_run=dry_run,
            check=check,
        )

    def remove_plan(
        self, plan_id: str, *, dry_run: bool = False, force: bool = False
    ) -> tuple[str, ...]:
        """Delete a plan folder. Refused, unless forced, while anything refers to it."""
        if not force:
            snapshot = self.catalog()
            if plan_id not in snapshot.loaded and plan_id not in snapshot.broken:
                raise PlanNotFoundError(plan_id)
            plans = {k: v for k, v in snapshot.plans.items() if k != plan_id}
            _refuse_new(_reference_problems(snapshot.plans), plans, {})
        return self.repository.remove(plan_id, dry_run=dry_run)

    def _guard(self, plan_id: str, new_id: str | None = None) -> Check:
        """A check that refuses a changed plan which breaks references anywhere."""
        plans = self.catalog().plans
        before = _reference_problems(plans)
        others = {k: v for k, v in plans.items() if k != plan_id}
        renamed = {new_id: plan_id} if new_id else {}

        def check(plan: Plan) -> None:
            _refuse_new(before, {**others, new_id or plan_id: plan}, renamed)

        return check

    def set_task_status(
        self, plan_id: str, task_id: str, status: TaskStatus
    ) -> EditResult:
        return self.edit(
            plan_id, lambda draft: set_task(draft, task_id, {"status": status})
        )


def _reference_problems(plans: Mapping[str, Plan]) -> list[Problem]:
    return [*references.check(plans), *references.unresolved_diagrams(plans)]


def _refuse_new(
    before: list[Problem], plans: Mapping[str, Plan], renamed: Mapping[str, str]
) -> None:
    """Raise if plans have reference problems that were not there before."""
    known = set(before)
    new = tuple(
        problem
        for problem in _reference_problems(plans)
        if Problem(renamed.get(problem.plan_id, problem.plan_id), problem.message)
        not in known
    )
    if new:
        raise BreaksReferencesError(new)
