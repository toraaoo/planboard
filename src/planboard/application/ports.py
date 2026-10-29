from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from ..domain.draft import Draft
from ..domain.json import JsonObject
from ..domain.plan import Plan
from ..domain.references import Problem

type Change = Callable[[Draft], None]
type Check = Callable[[Plan], None]
"""Runs on the changed plan before anything is written; raises to refuse it."""


@dataclass(frozen=True, slots=True)
class LoadedPlan:
    id: str
    path: Path
    plan: Plan


@dataclass(frozen=True, slots=True)
class BrokenPlan:
    id: str
    path: Path
    errors: tuple[str, ...]


PlanEntry = LoadedPlan | BrokenPlan


@dataclass(frozen=True, slots=True)
class EditResult:
    plan: Plan
    written: tuple[str, ...]
    removed: tuple[str, ...]


class PlanNotFoundError(LookupError):
    pass


class PlanExistsError(FileExistsError):
    pass


class UnreadableDiagramError(ValueError):
    pass


class BreaksReferencesError(ValueError):
    """A change would leave references or links, in any plan, that do not resolve."""

    def __init__(self, problems: tuple[Problem, ...]) -> None:
        super().__init__("; ".join(f"{p.plan_id}: {p.message}" for p in problems))
        self.problems = problems


class PlanRepository(Protocol):
    """Where plans live. The application reads and writes plans only through this."""

    @property
    def root(self) -> Path: ...

    def ids(self) -> list[str]: ...

    def load(self, plan_id: str) -> PlanEntry: ...

    def load_all(self) -> list[PlanEntry]: ...

    def unlisted_sections(self, entry: LoadedPlan) -> list[str]: ...

    def read_diagram(self, entry: LoadedPlan, file: str) -> str:
        """The source of a diagram file; UnreadableDiagramError if it has none."""
        ...

    def version(self) -> str:
        """Changes whenever a plan file changes."""
        ...

    def create(
        self, plan_id: str, document: JsonObject, *, dry_run: bool = False
    ) -> Path: ...

    def edit(
        self,
        plan_id: str,
        change: Change,
        *,
        dry_run: bool = False,
        check: Check | None = None,
    ) -> EditResult:
        """Apply a change and write it, or with dry_run only report what it would."""
        ...

    def move(
        self,
        plan_id: str,
        new_id: str,
        change: Change,
        *,
        dry_run: bool = False,
        check: Check | None = None,
    ) -> EditResult:
        """Give a plan a new id, applying change to it on the way."""
        ...

    def remove(self, plan_id: str, *, dry_run: bool = False) -> tuple[str, ...]:
        """Delete a plan; the files it removed, or would."""
        ...
