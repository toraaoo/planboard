"""Find the plans: which folder a command reads and writes.

In order, the first that applies wins:

1. an explicit folder: --data on the command line, or PLANBOARD_DATA;
2. the nearest planboard.toml in the current folder or one of its parents;
3. the user's data folder, such as ~/.local/share/planboard on Linux.
"""

from __future__ import annotations

import os
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal

from platformdirs import user_data_path

CONFIG_FILE = "planboard.toml"
DATA_ENV = "PLANBOARD_DATA"
DEFAULT_PLANS = "plans"
DEFAULT_SCHEMAS = "plans/.schema"

type Origin = Literal["option", "environment", "config", "user"]


@dataclass(frozen=True, slots=True)
class Settings:
    plans: Path
    schemas: Path | None
    origin: Origin
    config: Path | None = None


class ConfigError(ValueError):
    pass


def discover(
    data: Path | None = None,
    *,
    start: Path | None = None,
    environ: Mapping[str, str] = os.environ,
) -> Settings:
    origin: Origin = "option"
    if data is None and environ.get(DATA_ENV):
        data, origin = Path(environ[DATA_ENV]), "environment"
    if data is not None:
        plans = data.expanduser().resolve()
        found = find_config(plans)
        if found is not None and found.plans == plans:
            return replace(found, origin=origin)
        return Settings(plans, None, origin)
    found = find_config((start or Path.cwd()).resolve())
    if found is not None:
        return found
    root = user_root()
    return Settings(root / DEFAULT_PLANS, root / DEFAULT_SCHEMAS, "user")


def user_root() -> Path:
    return user_data_path("planboard", appauthor=False)


def find_config(start: Path) -> Settings | None:
    for folder in (start, *start.parents):
        path = folder / CONFIG_FILE
        if path.is_file():
            return load(path)
    return None


def load(path: Path) -> Settings:
    try:
        document = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise ConfigError(f"{path}: {error}") from None
    unknown = sorted(document.keys() - {"plans", "schemas"})
    if unknown:
        raise ConfigError(f"{path}: unknown keys {', '.join(unknown)}")
    plans = document.get("plans", DEFAULT_PLANS)
    schemas = document.get("schemas", DEFAULT_SCHEMAS)
    if not isinstance(plans, str) or not isinstance(schemas, str):
        raise ConfigError(f"{path}: plans and schemas must be strings")
    root = path.parent.resolve()
    return Settings(root / plans, root / schemas, "config", path)


def write(
    root: Path, plans: str = DEFAULT_PLANS, schemas: str = DEFAULT_SCHEMAS
) -> Path:
    path = root / CONFIG_FILE
    if path.exists():
        raise FileExistsError(path)
    root.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# planboard workspace: paths are relative to this file.\n"
        f"plans = {_quoted(plans)}\n"
        f"schemas = {_quoted(schemas)}\n",
        encoding="utf-8",
    )
    return path


def _quoted(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'
