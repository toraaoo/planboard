import os
import re
from pathlib import Path
from typing import Any

from planboard import resources
from planboard.adapters.filesystem import skills
from planboard.adapters.filesystem.agents import AGENTS, Agent, detected, expand

NAMES = skills.names()
CLAUDE, CODEX, CURSOR = AGENTS["claude-code"], AGENTS["codex"], AGENTS["cursor"]


def install(agents: list[Agent], base: Path, **options: Any) -> list[skills.Placed]:
    placed = skills.plan(agents, base, **options)
    skills.write(placed, base)
    return placed


def test_every_shipped_skill_is_named_after_its_folder() -> None:
    assert "planboard" in NAMES
    for skill in resources.skills():
        text = (skill / "SKILL.md").read_text(encoding="utf-8")
        assert re.search(rf"^name: {re.escape(skill.name)}$", text, re.MULTILINE)
        assert re.search(r"^description: ", text, re.MULTILINE)


def test_a_project_install_copies_once_and_links_claude(tmp_path: Path) -> None:
    placed = install([CLAUDE, CODEX], tmp_path, environ={})

    shared = tmp_path / ".agents" / "skills"
    link = tmp_path / ".claude" / "skills" / "planboard"
    assert [(item.folder, item.how) for item in placed] == [
        (shared, "copy"),
        (tmp_path / ".claude" / "skills", "link"),
    ]
    assert sorted(path.name for path in shared.iterdir()) == NAMES
    assert link.is_symlink()
    assert os.readlink(link) == os.path.join(
        "..", "..", ".agents", "skills", "planboard"
    )
    assert (link / "SKILL.md").is_file()


def test_a_global_install_skips_the_folders_of_shared_agents(tmp_path: Path) -> None:
    install([CLAUDE, CURSOR], tmp_path, user=True, environ={})

    assert (tmp_path / ".agents" / "skills" / "planboard" / "SKILL.md").is_file()
    assert (tmp_path / ".claude" / "skills" / "planboard").is_symlink()
    assert not (tmp_path / ".cursor").exists()


def test_a_global_copy_writes_each_agent_folder(tmp_path: Path) -> None:
    install([CURSOR], tmp_path, user=True, environ={}, copy=True)

    target = tmp_path / ".cursor" / "skills" / "planboard"
    assert (target / "SKILL.md").is_file()
    assert not target.is_symlink()
    assert not (tmp_path / ".agents").exists()


def test_a_project_copy_writes_the_shared_folder_once(tmp_path: Path) -> None:
    placed = install([CODEX, CURSOR], tmp_path, copy=True)

    assert [(item.folder, len(item.agents)) for item in placed] == [
        (tmp_path / ".agents" / "skills", 2)
    ]
    assert (tmp_path / ".agents" / "skills" / "planboard" / "SKILL.md").is_file()


def test_install_replaces_an_earlier_install(tmp_path: Path) -> None:
    stale = tmp_path / ".claude" / "skills" / "planboard" / "old.md"
    stale.parent.mkdir(parents=True)
    stale.write_text("old")

    install([CLAUDE], tmp_path)

    assert not stale.exists()
    assert (tmp_path / ".claude" / "skills" / "planboard").is_symlink()


def test_a_folder_that_links_to_the_shared_one_keeps_the_copy(tmp_path: Path) -> None:
    shared = tmp_path / ".agents" / "skills"
    shared.mkdir(parents=True)
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "skills").symlink_to(shared)

    install([CLAUDE], tmp_path)

    assert (shared / "planboard" / "SKILL.md").is_file()
    assert not (shared / "planboard").is_symlink()


def test_a_plan_writes_nothing(tmp_path: Path) -> None:
    placed = skills.plan([CLAUDE], tmp_path)

    assert len(placed) == 2
    assert list(tmp_path.iterdir()) == []


def test_an_environment_variable_moves_an_agent_folder(tmp_path: Path) -> None:
    environ = {"CLAUDE_CONFIG_DIR": str(tmp_path / "claude")}

    assert (
        expand("~/.claude/skills", tmp_path, environ) == tmp_path / "claude" / "skills"
    )
    assert (
        expand("~/.cursor/skills", tmp_path, environ) == tmp_path / ".cursor" / "skills"
    )


def test_detected_finds_agents_by_their_config_folder(tmp_path: Path) -> None:
    (tmp_path / ".codex").mkdir()
    (tmp_path / ".config" / "opencode").mkdir(parents=True)

    assert [agent.name for agent in detected(tmp_path, {})] == ["codex", "opencode"]
