from __future__ import annotations

from ..draft import Draft
from ..json import JsonValue
from .document import (
    Place,
    index_of,
    position_of,
    relink_anchor,
    require_free_anchor,
    section_of,
    strings_in,
    task_list,
)
from .errors import EditError


def add_section(
    draft: Draft,
    section_id: str,
    title: str,
    text: str | None,
    place: Place,
    blocks: list[JsonValue] | None = None,
) -> None:
    order = strings_in(draft.plan, "sections")
    require_free_anchor(draft, section_id)
    order.insert(position_of(order, place), section_id)
    draft.plan["sections"] = list[JsonValue](order)
    draft.sections[section_id] = {
        "title": title,
        "blocks": blocks if blocks is not None else [{"type": "text", "text": text}],
    }


def set_section(
    draft: Draft,
    section_id: str,
    title: str | None = None,
    blocks: list[JsonValue] | None = None,
) -> None:
    section = section_of(draft, section_id)
    if title is not None:
        section["title"] = title
    if blocks is not None:
        section["blocks"] = blocks


def remove_section(draft: Draft, section_id: str) -> None:
    order = strings_in(draft.plan, "sections")
    index_of(order, section_id, "section")
    building = [
        str(task["id"])
        for task in task_list(draft)
        if section_id in strings_in(task, "sections")
    ]
    if building:
        raise EditError(f"'{section_id}' is built by: {', '.join(building)}.")
    order.remove(section_id)
    draft.plan["sections"] = list[JsonValue](order)
    del draft.sections[section_id]


def move_section(draft: Draft, section_id: str, place: Place) -> None:
    order = strings_in(draft.plan, "sections")
    order.pop(index_of(order, section_id, "section"))
    order.insert(position_of(order, place), section_id)
    draft.plan["sections"] = list[JsonValue](order)


def rename_section(draft: Draft, plan_id: str, old: str, new: str) -> None:
    order = strings_in(draft.plan, "sections")
    index = index_of(order, old, "section")
    require_free_anchor(draft, new)
    order[index] = new
    draft.plan["sections"] = list[JsonValue](order)
    draft.sections[new] = draft.sections.pop(old)
    tasks = task_list(draft)
    for task in tasks:
        names = strings_in(task, "sections")
        if old in names:
            task["sections"] = [new if name == old else name for name in names]
    draft.plan["tasks"] = list[JsonValue](tasks)
    relink_anchor(draft, plan_id, old, new)
