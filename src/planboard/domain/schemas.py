from __future__ import annotations

import json

from .json import JsonObject
from .layout import PLAN_SCHEMA, SECTION_SCHEMA
from .plan import PlanFile, SectionFile

MODELS: dict[str, type[PlanFile | SectionFile]] = {
    PLAN_SCHEMA: PlanFile,
    SECTION_SCHEMA: SectionFile,
}


def render(model: type[PlanFile | SectionFile]) -> str:
    document: JsonObject = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        **model.model_json_schema(by_alias=True),
    }
    return json.dumps(document, indent=2, ensure_ascii=False) + "\n"


def rendered() -> dict[str, str]:
    return {name: render(model) for name, model in MODELS.items()}
