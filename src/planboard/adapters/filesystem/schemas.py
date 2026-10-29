from __future__ import annotations

from pathlib import Path

from ...domain import schemas
from .files import write_text


def write_all(folder: Path) -> list[Path]:
    """Write every JSON Schema into folder, returning the files it changed."""
    changed: list[Path] = []
    for name, text in schemas.rendered().items():
        path = folder / name
        if _current(path) != text:
            write_text(path, text)
            changed.append(path)
    return changed


def write_missing(folder: Path) -> None:
    for name, text in schemas.rendered().items():
        if not (folder / name).exists():
            write_text(folder / name, text)


def stale(folder: Path) -> list[Path]:
    """The schema files in folder that are missing or differ from the models."""
    return [
        folder / name
        for name, text in schemas.rendered().items()
        if _current(folder / name) != text
    ]


def _current(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
