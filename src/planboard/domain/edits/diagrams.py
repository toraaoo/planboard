from __future__ import annotations

from ..draft import Draft
from ..json import JsonObject, JsonValue
from ..layout import diagram_file
from .document import (
    diagram_map,
    diagram_of,
    objects_in,
    relink_anchor,
    rename_ref,
    require_free_anchor,
    section_of,
    strings_in,
    task_list,
)


def add_diagram(
    draft: Draft,
    diagram_id: str,
    alt: str,
    source: str,
    *,
    inline: bool,
    section: str | None,
    caption: str | None,
) -> None:
    require_free_anchor(draft, diagram_id)
    diagrams = diagram_map(draft)
    if inline:
        diagrams[diagram_id] = {"alt": alt, "source": source.strip()}
    else:
        name = diagram_file(diagram_id)
        diagrams[diagram_id] = {"alt": alt, "file": name}
        draft.diagram_files[name] = _with_newline(source)
    draft.plan["diagrams"] = dict[str, JsonValue](diagrams)
    if section is not None:
        block: JsonObject = {"type": "diagram", "ref": f"#{diagram_id}"}
        if caption:
            block["caption"] = caption
        target = section_of(draft, section)
        target["blocks"] = [*objects_in(target.get("blocks")), block]


def set_diagram(
    draft: Draft, diagram_id: str, alt: str | None, source: str | None
) -> None:
    diagrams = diagram_map(draft)
    diagram = diagram_of(diagrams, diagram_id)
    if alt is not None:
        diagram["alt"] = alt
    if source is not None:
        file = diagram.get("file")
        if isinstance(file, str):
            draft.diagram_files[file] = _with_newline(source)
        else:
            diagram["source"] = source.strip()
    draft.plan["diagrams"] = dict[str, JsonValue](diagrams)


def remove_diagram(draft: Draft, plan_id: str, diagram_id: str) -> None:
    diagrams = diagram_map(draft)
    file = diagram_of(diagrams, diagram_id).get("file")
    if isinstance(file, str):
        draft.diagram_files[file] = None
    del diagrams[diagram_id]
    draft.plan["diagrams"] = dict[str, JsonValue](diagrams)
    refs = {f"#{diagram_id}", f"{plan_id}#{diagram_id}"}
    for section in draft.sections.values():
        section["blocks"] = [
            block
            for block in objects_in(section.get("blocks"))
            if not (block.get("type") == "diagram" and block.get("ref") in refs)
        ]
    tasks = task_list(draft)
    for task in tasks:
        names = strings_in(task, "diagrams")
        if diagram_id in names:
            task["diagrams"] = [name for name in names if name != diagram_id]
    draft.plan["tasks"] = list[JsonValue](tasks)


def rename_diagram(draft: Draft, plan_id: str, old: str, new: str) -> None:
    """Change a diagram's id: its file, the blocks that show it, tasks and #links."""
    diagrams = diagram_map(draft)
    diagram = diagram_of(diagrams, old)
    require_free_anchor(draft, new)
    file = diagram.get("file")
    source = draft.diagram_sources.get(file) if isinstance(file, str) else None
    if isinstance(file, str) and file == diagram_file(old) and source is not None:
        diagram["file"] = diagram_file(new)
        draft.diagram_files[diagram_file(new)] = source
        draft.diagram_files[file] = None
    draft.plan["diagrams"] = {
        (new if key == old else key): value for key, value in diagrams.items()
    }
    for section in draft.sections.values():
        blocks = objects_in(section.get("blocks"))
        for block in blocks:
            ref = block.get("ref")
            if block.get("type") == "diagram" and isinstance(ref, str):
                block["ref"] = rename_ref(ref, plan_id, old, new)
        section["blocks"] = list[JsonValue](blocks)
    tasks = task_list(draft)
    for task in tasks:
        names = strings_in(task, "diagrams")
        if old in names:
            task["diagrams"] = [new if name == old else name for name in names]
    draft.plan["tasks"] = list[JsonValue](tasks)
    relink_anchor(draft, plan_id, old, new)


def _with_newline(source: str) -> str:
    return source.rstrip() + "\n"
