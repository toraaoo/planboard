from __future__ import annotations

from dataclasses import dataclass

from ..domain import references
from ..domain.ids import Ref
from ..domain.layout import PLAN_FILE
from ..domain.plan import Plan
from ..domain.references import Problem
from . import diagrams
from .diagrams import DiagramResolver
from .ports import BrokenPlan, LoadedPlan, PlanRepository


@dataclass(frozen=True, slots=True)
class Catalog:
    loaded: dict[str, LoadedPlan]
    broken: dict[str, BrokenPlan]
    problems: tuple[Problem, ...]
    diagrams: DiagramResolver

    @property
    def plans(self) -> dict[str, Plan]:
        return {plan_id: entry.plan for plan_id, entry in self.loaded.items()}

    def all_problems(self) -> list[Problem]:
        """Load errors of broken plans, then problems across loaded plans."""
        broken = [
            Problem(plan_id, error)
            for plan_id, entry in self.broken.items()
            for error in entry.errors
        ]
        return [*broken, *self.problems]

    def problems_for(self, plan_id: str) -> list[str]:
        return [
            problem.message for problem in self.problems if problem.plan_id == plan_id
        ]

    def dependents(self, plan_id: str) -> list[Dependent]:
        plans = self.plans
        found: list[Dependent] = []
        for other_id, other in plans.items():
            if other_id == plan_id:
                continue
            for task in [None, *other.tasks]:
                texts = other.depends_on if task is None else task.depends_on
                for text in texts:
                    target = Ref.parse(text, other_id)
                    if target.plan_id == plan_id:
                        found.append(
                            Dependent(
                                plan_id=other_id,
                                plan_title=other.title,
                                task_id=task.id if task else None,
                                title=task.title if task else other.title,
                                target=target.anchor,
                            )
                        )
        return found


@dataclass(frozen=True, slots=True)
class Dependent:
    plan_id: str
    plan_title: str
    task_id: str | None
    title: str
    target: str | None


def build(repository: PlanRepository) -> Catalog:
    loaded: dict[str, LoadedPlan] = {}
    broken: dict[str, BrokenPlan] = {}
    for entry in repository.load_all():
        if isinstance(entry, LoadedPlan):
            loaded[entry.id] = entry
        else:
            broken[entry.id] = entry
    plans = {plan_id: entry.plan for plan_id, entry in loaded.items()}
    resolver = DiagramResolver(loaded, repository.read_diagram)
    unlisted = [
        Problem(plan_id, f"'{name}' is not listed in {PLAN_FILE} sections")
        for plan_id, entry in loaded.items()
        for name in repository.unlisted_sections(entry)
    ]
    problems = [*references.check(plans), *diagrams.check(resolver), *unlisted]
    return Catalog(loaded, broken, tuple(problems), resolver)
