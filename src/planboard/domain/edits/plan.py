from __future__ import annotations

import re

from ..draft import Draft
from ..json import JsonValue
from .document import Changes, apply_changes, map_prose, objects_in, task_list


def set_plan(draft: Draft, changes: Changes) -> None:
    apply_changes(draft.plan, changes)


def retarget_plan(draft: Draft, old_id: str, new_id: str) -> None:
    """Point the plan's references to itself, written as old_id, at new_id."""

    def retarget(text: str) -> str:
        if text == old_id or text.startswith(f"{old_id}#"):
            return new_id + text[len(old_id) :]
        return text

    link = re.compile(rf"\]\({re.escape(old_id)}(?=[#)])")

    def relink(text: str) -> str:
        return link.sub(f"]({new_id}", text)

    for target in [draft.plan, *task_list(draft)]:
        refs = target.get("dependsOn")
        if isinstance(refs, list):
            target["dependsOn"] = [
                retarget(ref) if isinstance(ref, str) else ref for ref in refs
            ]
    draft.plan["tasks"] = list[JsonValue](task_list(draft))
    for section_id, section in draft.sections.items():
        for block in objects_in(section.get("blocks")):
            ref = block.get("ref")
            if block.get("type") == "diagram" and isinstance(ref, str):
                block["ref"] = retarget(ref)
        draft.sections[section_id] = map_prose(section, relink)
    draft.plan = map_prose(draft.plan, relink)
