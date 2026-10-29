from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from pydantic import ValidationError

from .json import JsonObject, JsonValue
from .layout import PLAN_FILE, section_file
from .plan import Plan, PlanFile, Section, SectionFile


@dataclass(slots=True)
class Draft:
    plan: JsonObject
    sections: dict[str, JsonObject]
    diagram_files: dict[str, str | None] = field(default_factory=dict[str, str | None])
    """Diagram files to write, by name; None removes one."""
    diagram_sources: dict[str, str] = field(default_factory=dict[str, str])
    """The plan's diagram files as they are stored, by name. Read only."""

    @classmethod
    def from_document(cls, document: JsonObject) -> Draft:
        sections: dict[str, JsonObject] = {}
        raw = document.get("sections")
        for section in raw if isinstance(raw, list) else []:
            if isinstance(section, dict) and isinstance(
                section_id := section.get("id"), str
            ):
                sections[section_id] = {
                    key: value for key, value in section.items() if key != "id"
                }
        plan: JsonObject = {**document, "sections": list[JsonValue](sections)}
        plan.pop("$schema", None)
        return cls(plan, sections)

    def validate(self, plan_id: str) -> Plan:
        def read_section(section_id: str) -> JsonObject:
            section = self.sections.get(section_id)
            if section is None:
                raise InvalidPlanError(
                    plan_id, (f"{section_file(section_id)}: missing",)
                )
            return section

        return assemble(plan_id, self.plan, read_section)


class InvalidPlanError(ValueError):
    def __init__(self, plan_id: str, errors: tuple[str, ...]) -> None:
        super().__init__(f"{plan_id}: {'; '.join(errors)}")
        self.errors = errors


def assemble(
    plan_id: str, document: JsonObject, read_section: Callable[[str], JsonObject]
) -> Plan:
    file = plan_file(plan_id, document)
    sections: list[Section] = []
    errors: list[str] = []
    for section_id in file.sections:
        try:
            content = SectionFile.model_validate(read_section(section_id))
            sections.append(
                Section(id=section_id, title=content.title, blocks=content.blocks)
            )
        except InvalidPlanError as error:
            errors.extend(error.errors)
        except ValidationError as error:
            errors.extend(format_errors(error, section_file(section_id)))
    if errors:
        raise InvalidPlanError(plan_id, tuple(errors))
    try:
        return Plan.assemble(file, sections)
    except ValidationError as error:
        raise InvalidPlanError(plan_id, format_errors(error, PLAN_FILE)) from error


def plan_file(plan_id: str, document: JsonObject) -> PlanFile:
    try:
        return PlanFile.model_validate(document)
    except ValidationError as error:
        raise InvalidPlanError(plan_id, format_errors(error, PLAN_FILE)) from error


def format_errors(error: ValidationError, file: str | None = None) -> tuple[str, ...]:
    prefix = f"{file}: " if file else ""
    return tuple(
        f"{prefix}{'.'.join(str(part) for part in issue['loc']) or '(root)'}: "
        f"{issue['msg']}"
        for issue in error.errors()
    )
