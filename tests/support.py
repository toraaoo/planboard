import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from planboard.domain.draft import Draft
from planboard.domain.layout import PLAN_FILE, section_file

type WritePlan = Callable[..., Path]


def plan_document(**overrides: Any) -> dict[str, Any]:
    return {
        "title": "Example",
        "summary": "An example plan.",
        "diagrams": {"flow": {"alt": "A flow.", "source": "flowchart LR\n  a --> b"}},
        "sections": [
            {
                "id": "design",
                "title": "Design",
                "blocks": [{"type": "diagram", "ref": "#flow"}],
            }
        ],
        **overrides,
    }


def write_folder(folder: Path, document: dict[str, Any]) -> Path:
    draft = Draft.from_document(document)
    for section_id, section in draft.sections.items():
        path = folder / section_file(section_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(section), encoding="utf-8")
    (folder / PLAN_FILE).write_text(json.dumps(draft.plan), encoding="utf-8")
    return folder
