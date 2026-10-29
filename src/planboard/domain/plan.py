from __future__ import annotations

import datetime
from collections import Counter
from typing import Literal, Self

from pydantic import Field, model_validator

from .base import Model
from .blocks import Block, DiagramBlock
from .ids import Inline, RefText, Slug

PlanStatus = Literal["draft", "approved", "archived"]
TaskStatus = Literal["todo", "doing", "blocked", "done"]
TASK_STATUSES: tuple[TaskStatus, ...] = ("todo", "doing", "blocked", "done")
PLAN_STATUSES: tuple[PlanStatus, ...] = ("draft", "approved", "archived")


class Diagram(Model):
    alt: str = Field(min_length=1, description="What the diagram shows, for readers.")
    source: str | None = Field(
        default=None, min_length=1, description="Mermaid source, for a few lines."
    )
    file: str | None = Field(
        default=None,
        pattern=r"^(?:[A-Za-z0-9_-][A-Za-z0-9_.-]*/)*[A-Za-z0-9_-][A-Za-z0-9_.-]*\.mmd$",
        description="A Mermaid file, relative to the plan folder: diagrams/<id>.mmd.",
    )

    @model_validator(mode="after")
    def _check_origin(self) -> Self:
        if (self.source is None) == (self.file is None):
            raise ValueError("a diagram takes either source or file")
        return self


class SectionContent(Model):
    title: str = Field(min_length=1)
    blocks: list[Block] = Field(min_length=1)


class SectionFile(SectionContent):
    schema_: str | None = Field(default=None, alias="$schema")


class Section(SectionContent):
    id: Slug


class Task(Model):
    id: Slug
    title: str = Field(min_length=1)
    status: TaskStatus = "todo"
    summary: Inline | None = None
    note: Inline | None = Field(
        default=None, description="Why the task is blocked, or anything else current."
    )
    depends_on: list[RefText] = Field(
        default_factory=list[RefText],
        description="Tasks or plans that must be done first: "
        "#task, folder/plan or folder/plan#task.",
    )
    sections: list[Slug] = Field(
        default_factory=list[Slug], description="Ids of the sections this task builds."
    )
    diagrams: list[Slug] = Field(
        default_factory=list[Slug], description="Ids of the diagrams this task builds."
    )


class PlanFields(Model):
    title: str = Field(min_length=1)
    summary: Inline
    status: PlanStatus = "draft"
    updated: datetime.date | None = None
    branch: str | None = None
    tags: list[Slug] = Field(default_factory=list[Slug])
    depends_on: list[RefText] = Field(
        default_factory=list[RefText],
        description="Plans or tasks this whole plan builds on.",
    )
    diagrams: dict[Slug, Diagram] = Field(
        default_factory=dict[Slug, Diagram],
        description="Diagrams by id. Show one with a diagram block, link to it as #id.",
    )
    tasks: list[Task] = Field(
        default_factory=list[Task], description="Board cards, in build order."
    )


class PlanFile(PlanFields):
    schema_: str | None = Field(default=None, alias="$schema")
    sections: list[Slug] = Field(
        min_length=1,
        description="Section ids in reading order; each is sections/<id>.json.",
    )


class Plan(PlanFields):
    sections: list[Section] = Field(min_length=1)

    @classmethod
    def assemble(cls, file: PlanFile, sections: list[Section]) -> Plan:
        fields = {name: getattr(file, name) for name in PlanFields.model_fields}
        return cls.model_validate({**fields, "sections": sections})

    @model_validator(mode="after")
    def _check_consistency(self) -> Self:
        section_ids = [section.id for section in self.sections]
        diagram_ids = list(self.diagrams)
        _require_unique("task", [task.id for task in self.tasks])
        _require_unique("section and diagram", section_ids + diagram_ids)
        for task in self.tasks:
            _require_known(task.id, "sections", task.sections, section_ids)
            _require_known(task.id, "diagrams", task.diagrams, diagram_ids)
        return self

    def task(self, task_id: str) -> Task | None:
        return next((task for task in self.tasks if task.id == task_id), None)

    def diagram_blocks(self) -> list[DiagramBlock]:
        return [
            block
            for section in self.sections
            for block in section.blocks
            if isinstance(block, DiagramBlock)
        ]

    def anchors(self) -> set[str]:
        return {section.id for section in self.sections} | set(self.diagrams)


def _require_known(task_id: str, kind: str, names: list[str], known: list[str]) -> None:
    unknown = [name for name in names if name not in known]
    if unknown:
        raise ValueError(f"task '{task_id}' names unknown {kind}: {unknown}")


def _require_unique(kind: str, ids: list[str]) -> None:
    duplicates = sorted(id_ for id_, count in Counter(ids).items() if count > 1)
    if duplicates:
        raise ValueError(f"duplicate {kind} ids: {duplicates}")
