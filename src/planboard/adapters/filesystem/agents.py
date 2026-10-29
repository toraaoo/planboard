"""Coding agents and their skill folders, after the skills.sh CLI.

Each agent has a project folder, relative to the project, and a user one, under ~
(~/.config is XDG_CONFIG_HOME when set). An agent counts as installed when its detect
path exists: by default the folder that holds its user skills. Agents whose project
folder is .agents/skills share it, and read ~/.agents/skills globally too.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

SHARED = ".agents/skills"

# A folder an agent lets you move with an environment variable.
ROOTS = {
    "~/.config": "XDG_CONFIG_HOME",
    "~/.claude": "CLAUDE_CONFIG_DIR",
    "~/.codex": "CODEX_HOME",
}


@dataclass(frozen=True, slots=True)
class Agent:
    name: str
    label: str
    project: str
    user: str
    detect: str

    @property
    def shared(self) -> bool:
        return self.project == SHARED


def _agent(
    name: str, label: str, project: str, user: str, detect: str | None = None
) -> Agent:
    return Agent(name, label, project, user, detect or user.removesuffix("/skills"))


AGENTS = {
    agent.name: agent
    for agent in (
        _agent("claude-code", "Claude Code", ".claude/skills", "~/.claude/skills"),
        _agent("codex", "Codex", SHARED, f"~/{SHARED}", "~/.codex"),
        _agent("cursor", "Cursor", SHARED, "~/.cursor/skills"),
        _agent("gemini-cli", "Gemini CLI", SHARED, "~/.gemini/skills"),
        _agent("github-copilot", "GitHub Copilot", SHARED, "~/.copilot/skills"),
        _agent("opencode", "OpenCode", SHARED, "~/.config/opencode/skills"),
    )
}


def expand(path: str, home: Path, environ: Mapping[str, str] = os.environ) -> Path:
    """A ~ path as a real one, honouring the agent's environment variable."""
    for prefix, variable in ROOTS.items():
        if (path == prefix or path.startswith(prefix + "/")) and environ.get(variable):
            return Path(environ[variable].strip()) / path[len(prefix) :].lstrip("/")
    return home / path.removeprefix("~").lstrip("/")


def detected(home: Path, environ: Mapping[str, str] = os.environ) -> list[Agent]:
    """The agents whose config folder exists on this machine."""
    return [
        agent
        for agent in AGENTS.values()
        if expand(agent.detect, home, environ).exists()
    ]
