from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass

from ..domain.ids import Ref
from ..domain.json import JsonObject, JsonValue
from ..domain.plan import Diagram
from ..domain.references import Problem
from .ports import LoadedPlan, UnreadableDiagramError

type ReadDiagram = Callable[[LoadedPlan, str], str]


@dataclass(frozen=True, slots=True)
class ResolvedDiagram:
    plan_id: str
    diagram_id: str
    plan_title: str | None
    alt: str | None
    file: str | None
    source: str | None
    error: str | None = None


class DiagramResolver:
    def __init__(self, plans: Mapping[str, LoadedPlan], read: ReadDiagram) -> None:
        self.plans = plans
        self._read = read

    def find(self, text: str, plan_id: str) -> tuple[LoadedPlan, Diagram] | None:
        ref = Ref.parse(text, plan_id)
        entry = self.plans.get(ref.plan_id)
        diagram = entry.plan.diagrams.get(ref.anchor or "") if entry else None
        return (entry, diagram) if entry and diagram else None

    def resolve(self, text: str, plan_id: str) -> ResolvedDiagram:
        ref = Ref.parse(text, plan_id)
        found = self.find(text, plan_id)
        if found is None:
            return ResolvedDiagram(
                ref.plan_id,
                ref.anchor or "",
                None,
                None,
                None,
                None,
                f"'{text}' does not resolve",
            )
        entry, diagram = found
        source, error = self.source(entry, diagram)
        return ResolvedDiagram(
            ref.plan_id,
            ref.anchor or "",
            entry.plan.title,
            diagram.alt,
            diagram.file,
            source,
            error,
        )

    def source(
        self, entry: LoadedPlan, diagram: Diagram
    ) -> tuple[str | None, str | None]:
        if diagram.file is None:
            return diagram.source, None
        try:
            source = self._read(entry, diagram.file)
        except UnreadableDiagramError as error:
            return None, str(error)
        if not source.strip():
            return None, f"'{diagram.file}' is empty"
        return source, None


def check(resolver: DiagramResolver) -> list[Problem]:
    problems: list[Problem] = []
    for plan_id, entry in resolver.plans.items():
        shown: set[str] = set()
        for block in entry.plan.diagram_blocks():
            ref = Ref.parse(block.ref, plan_id)
            if ref.plan_id == plan_id and ref.anchor:
                shown.add(ref.anchor)
            if resolver.find(block.ref, plan_id) is None:
                problems.append(Problem(plan_id, f"'{block.ref}' does not resolve"))
        for diagram_id, diagram in entry.plan.diagrams.items():
            _, error = resolver.source(entry, diagram)
            if error:
                problems.append(Problem(plan_id, f"diagram '{diagram_id}': {error}"))
            if diagram_id not in shown:
                problems.append(
                    Problem(plan_id, f"diagram '{diagram_id}' is never shown")
                )
    return problems


def inline_sources(
    document: JsonObject, plan_id: str, resolver: DiagramResolver
) -> None:
    for section in _objects(document.get("sections")):
        for block in _objects(section.get("blocks")):
            ref = block.get("ref")
            if block.get("type") == "diagram" and isinstance(ref, str):
                block["diagram"] = {
                    key: value
                    for key, value in asdict(resolver.resolve(ref, plan_id)).items()
                    if value is not None
                }


def _objects(value: JsonValue) -> list[JsonObject]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]
