from __future__ import annotations

PLAN_FILE = "plan.json"
SECTIONS_DIR = "sections"
DIAGRAMS_DIR = "diagrams"
PLAN_SCHEMA = "plan.schema.json"
SECTION_SCHEMA = "section.schema.json"


def section_file(section_id: str) -> str:
    return f"{SECTIONS_DIR}/{section_id}.json"


def diagram_file(diagram_id: str) -> str:
    return f"{DIAGRAMS_DIR}/{diagram_id}.mmd"
