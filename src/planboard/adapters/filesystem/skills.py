"""Install and uninstall the agent skills planboard ships, in agents' skill folders.

Like the skills.sh CLI: a project install goes under the project, a global one under
the home folder. Symlinked, the skills are copied once to .agents/skills, which most
agents read, and every other agent's folder gets a relative symlink to that copy.
Copied, each agent's own folder gets the files.
"""

from __future__ import annotations

import os
import shutil
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from importlib.resources import as_file
from pathlib import Path
from typing import Literal

from ... import resources
from .agents import SHARED, Agent, expand

type How = Literal["copy", "link"]


@dataclass(frozen=True, slots=True)
class Placed:
    """The skills in one folder, and the agents that read that folder."""

    folder: Path
    agents: tuple[Agent, ...]
    how: How


def names() -> list[str]:
    return [skill.name for skill in resources.skills()]


def folder_of(
    agent: Agent, base: Path, *, user: bool, environ: Mapping[str, str] = os.environ
) -> Path:
    """An agent's skill folder: under the project base, or the home folder base."""
    return expand(agent.user, base, environ) if user else base / agent.project


def plan(
    agents: Iterable[Agent],
    base: Path,
    *,
    user: bool = False,
    copy: bool = False,
    environ: Mapping[str, str] = os.environ,
) -> list[Placed]:
    """Where an install puts the skills; base is the project, or home when user."""
    shared = base / SHARED
    # A symlinked install always starts with the shared copy the links point at.
    groups: dict[Path, tuple[Path, list[Agent]]] = {}
    if not copy:
        groups[shared.resolve()] = (shared, [])
    for agent in agents:
        # A shared agent reads the shared copy; a link from its own folder is noise.
        if agent.shared and not copy:
            folder = shared
        else:
            folder = folder_of(agent, base, user=user, environ=environ)
        groups.setdefault(folder.resolve(), (folder, []))[1].append(agent)
    return [
        Placed(
            folder, tuple(group), "copy" if copy or key == shared.resolve() else "link"
        )
        for key, (folder, group) in groups.items()
    ]


def write(placed: Iterable[Placed], base: Path) -> None:
    """Carry out a plan, replacing what an earlier install left."""
    shared = base / SHARED
    for item in placed:  # the shared copy comes first, before the links to it
        item.folder.mkdir(parents=True, exist_ok=True)
        for skill in resources.skills():
            target = item.folder / skill.name
            _delete(target)
            if item.how == "link":
                try:
                    target.symlink_to(os.path.relpath(shared / skill.name, item.folder))
                    continue
                except OSError:  # no symlinks, as on Windows without developer mode
                    pass
            with as_file(skill) as source:
                shutil.copytree(source, target)


def installed(
    agents: Iterable[Agent],
    base: Path,
    *,
    user: bool = False,
    environ: Mapping[str, str] = os.environ,
) -> list[Path]:
    """The planboard skills, copies or links, that these agents read under base.

    The shared copy is included only when an agent that reads it is chosen.
    """
    folders: dict[Path, Path] = {}
    for agent in agents:
        candidates = [folder_of(agent, base, user=user, environ=environ)]
        if agent.shared:
            candidates.append(base / SHARED)
        for folder in candidates:
            folders.setdefault(folder.resolve(), folder)
    return [
        folder / name
        for folder in folders.values()
        for name in names()
        if (folder / name).is_symlink() or (folder / name).exists()
    ]


def remove(
    paths: Iterable[Path],
    every: Iterable[Agent],
    base: Path,
    *,
    user: bool = False,
    environ: Mapping[str, str] = os.environ,
) -> list[Path]:
    """Delete skills, then links of every agent left pointing at nothing.

    Returns all it deleted. A skill folder this leaves empty is removed too.
    """
    removed: list[Path] = []
    for path in paths:
        _delete(path)
        removed.append(path)
    folders = {folder_of(agent, base, user=user, environ=environ) for agent in every}
    for folder in {*folders, base / SHARED}:
        for name in names():
            path = folder / name
            if path.is_symlink() and not path.exists():  # its target is gone
                path.unlink()
                removed.append(path)
    for folder in {path.parent for path in removed}:
        if folder.is_dir() and not folder.is_symlink() and not any(folder.iterdir()):
            folder.rmdir()
    return removed


def _delete(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)
