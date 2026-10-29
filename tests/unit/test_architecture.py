"""Imports point inward: adapters → application → domain, never back out."""

import ast
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[2] / "src" / "planboard"

FORBIDDEN = {
    "domain": ("application", "adapters", "bootstrap", "config", "resources"),
    "application": ("adapters", "bootstrap", "config"),
    "adapters.filesystem": ("adapters.cli", "adapters.web", "bootstrap", "config"),
    "adapters.web": ("adapters.cli", "adapters.filesystem", "bootstrap", "config"),
}
FRAMEWORKS = {
    "domain": ("typer", "rich", "http", "platformdirs"),
    "application": ("typer", "rich", "http", "platformdirs"),
}


def _layer(path: Path) -> str:
    parts = path.relative_to(PACKAGE).with_suffix("").parts
    return ".".join(parts[:2]) if parts[0] == "adapters" else parts[0]


def _imports(path: Path) -> set[str]:
    module = path.relative_to(PACKAGE).with_suffix("").parts
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom):
            if node.level:
                base = ".".join(module[: len(module) - node.level])
                targets = (
                    [node.module]
                    if node.module
                    else [alias.name for alias in node.names]
                )
                found.update(f"{base}.{target}".strip(".") for target in targets)
            else:
                found.add(f"external:{node.module}")
        elif isinstance(node, ast.Import):
            found.update(f"external:{alias.name}" for alias in node.names)
    return found


MODULES = sorted(PACKAGE.rglob("*.py"))


@pytest.mark.parametrize("path", MODULES, ids=lambda p: str(p.relative_to(PACKAGE)))
def test_imports_point_inward(path: Path) -> None:
    layer = _layer(path)
    imports = _imports(path)
    for banned in FORBIDDEN.get(layer, ()):
        hits = [
            name for name in imports if name == banned or name.startswith(banned + ".")
        ]
        assert not hits, f"{layer} must not import {banned}: {hits}"
    for framework in FRAMEWORKS.get(layer, ()):
        hits = [
            name
            for name in imports
            if name == f"external:{framework}"
            or name.startswith(f"external:{framework}.")
        ]
        assert not hits, f"{layer} must not import {framework}: {hits}"
