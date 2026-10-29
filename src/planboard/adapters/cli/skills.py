"""planboard skill install and uninstall: the skills.sh `add` and `remove` flows.

Without flags it asks, in order: which agents, project or global, symlink or copy, and
whether to go ahead. -y takes the defaults: the agents found (all when none is), the
project, and symlinks.
"""

from __future__ import annotations

import difflib
import sys
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from ..filesystem import skills
from ..filesystem.agents import AGENTS, Agent, detected
from . import completion
from .shared import DryRun, Yes, console, done, errors, fail, hint

group = typer.Typer(
    help="Install or uninstall the planboard skills for coding agents.",
    no_args_is_help=True,
)

FALLBACK = "claude-code,codex"  # suggested when no agent is found


@group.command()
def install(
    ctx: typer.Context,
    agent: Annotated[
        list[str] | None,
        typer.Option(
            "--agent",
            "-a",
            metavar="AGENTS",
            help="An agent, such as claude-code. Repeat it or comma-separate; "
            "* for all. Default: the agents found on this machine.",
            autocompletion=completion.agents,
            show_default=False,
        ),
    ] = None,
    user: Annotated[
        bool | None,
        typer.Option(
            "--global/--project",
            "-g/-p",
            help="Install in your home folder, for every project, or in this one. "
            "Asks when neither is given; -y picks the project.",
            show_default=False,
        ),
    ] = None,
    copy: Annotated[
        bool,
        typer.Option("--copy", help="Copy into each agent's folder; do not symlink."),
    ] = False,
    every: Annotated[
        bool,
        typer.Option(
            "--all", help="Install for every supported agent, without asking."
        ),
    ] = False,
    list_agents: Annotated[
        bool,
        typer.Option("--list", help="List the supported agents and their folders."),
    ] = False,
    yes: Yes = False,
    dry_run: DryRun = False,
) -> None:
    """Install the planboard skills for your coding agents.

    The skills are copied once to .agents/skills, which most agents read, and linked
    from the folders of the others, such as .claude/skills. Run it again after
    upgrading planboard to update them.
    """
    home = Path.home()
    found = detected(home)
    if list_agents:
        _print_agents(console, home, found)
        return
    ask = not (yes or every)
    if every:
        chosen = list(AGENTS.values())
    elif agent:
        chosen = _parse(",".join(agent))
    elif not ask:
        chosen = found or list(AGENTS.values())
    elif len(found) == 1:
        chosen = found
        errors.print(f"Installing for {found[0].label}", highlight=False)
    else:
        _need_terminal()
        _print_agents(errors, home, found, numbered=True)
        answer = typer.prompt(
            "Agents (numbers or names, comma-separated; * for all)",
            default=",".join(agent.name for agent in found) or FALLBACK,
            err=True,
        )
        chosen = _parse(answer)
    if user is None:
        user = ask and _pick("Scope", "project", "global") == "global"
    if len({agent.project for agent in chosen}) <= 1:
        copy = True  # every agent reads one folder: there is nothing to link
    elif not copy and ask:
        copy = _pick("Method", "symlink", "copy") == "copy"
    base = home if user else Path.cwd()
    placed = skills.plan(chosen, base, user=user, copy=copy)
    if dry_run or ask:
        for item in placed:
            labels = ", ".join(agent.label for agent in item.agents) or "shared copy"
            how = "symlink to .agents/skills" if item.how == "link" else "copy"
            folder = _short(item.folder, base, user=user)
            console.print(f"  {folder}  {labels}  ({how})", highlight=False)
    if dry_run:
        console.print("Dry run, nothing written.")
        return
    if ask:
        _need_terminal()
        if not typer.confirm("Install?", default=True, err=True):
            raise typer.Abort()
    skills.write(placed, base)
    for item in placed:
        done(ctx, f"{_short(item.folder, base, user=user)}  ({item.how})")
    hint(ctx, f"Skills: {', '.join(skills.names())}. Start a new agent session.")


@group.command()
def uninstall(
    ctx: typer.Context,
    agent: Annotated[
        list[str] | None,
        typer.Option(
            "--agent",
            "-a",
            metavar="AGENTS",
            help="Only this agent. Repeat it or comma-separate. Default: every agent.",
            autocompletion=completion.agents,
            show_default=False,
        ),
    ] = None,
    user: Annotated[
        bool,
        typer.Option(
            "--global/--project",
            "-g/-p",
            help="Remove them from your home folder, or from this project (default).",
            show_default=False,
        ),
    ] = False,
    yes: Yes = False,
    dry_run: DryRun = False,
) -> None:
    """Remove the planboard skills from your coding agents' folders.

    Removes only the skills planboard installs, and links left pointing at nothing.
    The shared copy in .agents/skills goes when every agent, or one that reads it, is
    chosen.
    """
    home = Path.home()
    base = home if user else Path.cwd()
    chosen = _parse(",".join(agent)) if agent else list(AGENTS.values())
    found = skills.installed(chosen, base, user=user)
    scope = "your home folder" if user else "this project"
    if not found:
        done(ctx, f"No planboard skills in {scope} for those agents")
        if not user:
            hint(ctx, "Installed globally? Run planboard skill uninstall -g.")
        return
    for path in found:
        console.print(f"  {_short(path, base, user=user)}", highlight=False)
    if dry_run:
        console.print("Dry run, nothing removed.")
        return
    if not yes:
        _need_terminal("Nothing removed", "Pass -y to remove them.")
        if not typer.confirm(f"Remove these from {scope}?", default=True, err=True):
            raise typer.Abort()
    removed = skills.remove(found, AGENTS.values(), base, user=user)
    done(ctx, f"Removed {len(removed)} skill{'' if len(removed) == 1 else 's'}")
    left = skills.installed(AGENTS.values(), base, user=user)
    if left:
        where = ", ".join(sorted({_short(p.parent, base, user=user) for p in left}))
        hint(ctx, f"Still installed for other agents in {where}.")


def _parse(text: str) -> list[Agent]:
    """Agents from names or list numbers, comma-separated; * means all of them."""
    numbers = {str(number): name for number, name in enumerate(AGENTS, 1)}
    names = [numbers.get(n.strip(), n.strip()) for n in text.split(",") if n.strip()]
    if "*" in names:
        return list(AGENTS.values())
    if not names:
        raise typer.BadParameter("Name at least one agent.")
    for name in names:
        if name not in AGENTS:
            close = difflib.get_close_matches(name, AGENTS, n=1)
            suggestion = f" Did you mean {close[0]}?" if close else ""
            raise typer.BadParameter(f"Unknown agent '{name}'.{suggestion}")
    return [AGENTS[name] for name in dict.fromkeys(names)]


def _pick(question: str, default: str, other: str) -> str:
    _need_terminal()
    answer = typer.prompt(f"{question} ({default}/{other})", default=default, err=True)
    if answer not in (default, other):
        raise typer.BadParameter(f"Answer {default} or {other}.")
    return answer


def _need_terminal(
    refused: str = "Nothing installed", fix: str = "Pass -a <agent> and -y, or --all."
) -> None:
    if not sys.stdin.isatty():
        fail(f"{refused}: a question needs a terminal to answer it.", fix)


def _print_agents(
    out: Console, home: Path, found: list[Agent], *, numbered: bool = False
) -> None:
    width = max(map(len, AGENTS))
    for number, agent in enumerate(AGENTS.values(), 1):
        mark = "●" if agent in found else " "
        prefix = f"  {number}  " if numbered else ""
        user = _short(skills.folder_of(agent, home, user=True), home, user=True)
        out.print(
            f"{prefix}{mark} {agent.name:<{width}}  {agent.project:<16}  {user}",
            highlight=False,
        )
    errors.print("● found on this machine", style="dim", highlight=False)


def _short(path: Path, base: Path, *, user: bool) -> str:
    try:
        relative = path.relative_to(base)
    except ValueError:
        return str(path)
    return f"~/{relative}" if user else str(relative)
