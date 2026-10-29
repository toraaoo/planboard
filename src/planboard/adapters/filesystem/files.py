from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from ...domain.json import JsonObject, JsonValue


class UnreadableFileError(ValueError):
    pass


def read_object(path: Path) -> JsonObject:
    try:
        document: JsonValue = json.loads(path.read_text(encoding="utf-8"))
    except OSError:
        raise UnreadableFileError("cannot be read") from None
    except ValueError as error:
        raise UnreadableFileError(f"not valid JSON: {error}") from None
    if not isinstance(document, dict):
        raise UnreadableFileError("the top level must be an object")
    return document


def inside(folder: Path, name: str) -> Path:
    path = (folder / name).resolve()
    if not path.is_relative_to(folder.resolve()):
        raise ValueError(f"'{name}' is outside {folder}")
    return path


def write_json(path: Path, document: JsonObject) -> None:
    write_text(path, json.dumps(document, indent=2, ensure_ascii=False) + "\n")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise
