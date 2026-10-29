"""The composition root: wires the filesystem adapter into the application."""

from __future__ import annotations

from pathlib import Path

from .adapters.filesystem.repository import FilePlanRepository
from .application.workspace import Workspace
from .config import Settings, discover


def open_workspace(data: Path | None = None, *, start: Path | None = None) -> Workspace:
    """The workspace for a plans folder, or the one found from start (the cwd)."""
    return workspace_for(discover(data, start=start))


def workspace_for(settings: Settings) -> Workspace:
    return Workspace(FilePlanRepository(settings.plans, settings.schemas))
