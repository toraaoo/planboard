"""Implementation plans as JSON: a document, a kanban board and a dependency graph.

Use it as a library through a Workspace::

    import planboard

    workspace = planboard.open_workspace()
    for plan_id, task in workspace.ready():
        print(f"{plan_id}#{task.id}", task.title)
"""

from __future__ import annotations

from importlib.metadata import version

from .application.ports import (
    BreaksReferencesError,
    EditResult,
    PlanExistsError,
    PlanNotFoundError,
)
from .application.workspace import Workspace
from .bootstrap import open_workspace
from .domain.draft import Draft, InvalidPlanError
from .domain.edits.errors import EditError
from .domain.plan import Plan, Section, Task

__version__ = version("planboard")

__all__ = [
    "BreaksReferencesError",
    "Draft",
    "EditError",
    "EditResult",
    "InvalidPlanError",
    "Plan",
    "PlanExistsError",
    "PlanNotFoundError",
    "Section",
    "Task",
    "Workspace",
    "__version__",
    "open_workspace",
]
