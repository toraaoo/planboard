from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from ..draft import Draft
from ..json import JsonObject, JsonValue
from .errors import EditError, UnknownIdError

type Changes = Mapping[str, JsonValue | None]


@dataclass(frozen=True, slots=True)
class Place:
    after: str | None = None
    before: str | None = None


def apply_changes(target: JsonObject, changes: Changes) -> None:
    for key, value in changes.items():
        if value is None:
            target.pop(key, None)
        else:
            target[key] = value


def position_of(ids: list[str], place: Place) -> int:
    if place.after is not None:
        return index_of(ids, place.after, "item") + 1
    if place.before is not None:
        return index_of(ids, place.before, "item")
    return len(ids)


def index_of(ids: list[str], wanted: str, kind: str) -> int:
    try:
        return ids.index(wanted)
    except ValueError:
        raise UnknownIdError(f"No {kind} named '{wanted}'.") from None


def require_free_anchor(draft: Draft, anchor: str) -> None:
    if anchor in strings_in(draft.plan, "sections") or anchor in diagram_map(draft):
        raise EditError(f"'{anchor}' is already a section or diagram id.")


def section_of(draft: Draft, section_id: str) -> JsonObject:
    section = draft.sections.get(section_id)
    if section is None:
        raise UnknownIdError(f"No section named '{section_id}'.")
    return section


def diagram_of(diagrams: dict[str, JsonObject], diagram_id: str) -> JsonObject:
    diagram = diagrams.get(diagram_id)
    if diagram is None:
        raise UnknownIdError(f"No diagram named '{diagram_id}'.")
    return diagram


def task_list(draft: Draft) -> list[JsonObject]:
    return objects_in(draft.plan.get("tasks"))


def diagram_map(draft: Draft) -> dict[str, JsonObject]:
    value = draft.plan.get("diagrams")
    if not isinstance(value, dict):
        return {}
    return {key: item for key, item in value.items() if isinstance(item, dict)}


def ids_of(items: list[JsonObject]) -> list[str]:
    return [str(item.get("id")) for item in items]


def objects_in(value: JsonValue) -> list[JsonObject]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def strings_in(target: JsonObject, key: str) -> list[str]:
    value = target.get(key)
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


_NOT_PROSE = frozenset({"source", "code"})


def map_prose(document: JsonObject, change: Callable[[str], str]) -> JsonObject:
    return {
        key: item if key in _NOT_PROSE else map_value(item, change)
        for key, item in document.items()
    }


def map_value(value: JsonValue, change: Callable[[str], str]) -> JsonValue:
    if isinstance(value, str):
        return change(value)
    if isinstance(value, list):
        return [map_value(item, change) for item in value]
    if isinstance(value, dict):
        return map_prose(value, change)
    return value


def relink_anchor(draft: Draft, plan_id: str, old: str, new: str) -> None:
    """Point [label](#old) and [label](plan#old) links in the plan at #new."""
    link = re.compile(rf"\]\(((?:{re.escape(plan_id)})?)#{re.escape(old)}\)")

    def relink(text: str) -> str:
        return link.sub(lambda match: f"]({match[1]}#{new})", text)

    draft.plan = map_prose(draft.plan, relink)
    for section_id, section in draft.sections.items():
        draft.sections[section_id] = map_prose(section, relink)


def rename_ref(text: str, plan_id: str, old: str, new: str) -> str:
    """#old or plan#old as #new or plan#new; any other reference unchanged."""
    if text == f"#{old}":
        return f"#{new}"
    if text == f"{plan_id}#{old}":
        return f"{plan_id}#{new}"
    return text
