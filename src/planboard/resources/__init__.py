"""Files shipped inside the package, read through importlib.resources."""

from __future__ import annotations

import json
from importlib.resources import files
from importlib.resources.abc import Traversable

from ..domain.json import JsonObject, JsonValue


def template(name: str = "feature") -> JsonObject:
    text = (files(__package__) / "templates" / f"{name}.json").read_text("utf-8")
    document: JsonValue = json.loads(text)
    if not isinstance(document, dict):
        raise ValueError(f"template '{name}' must hold a JSON object")
    return document


def skills() -> list[Traversable]:
    """The agent skill folders planboard ships, one per skill name."""
    folder = files(__package__) / "skills"
    return sorted(
        (entry for entry in folder.iterdir() if entry.is_dir()),
        key=lambda entry: entry.name,
    )
