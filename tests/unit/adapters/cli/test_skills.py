from pathlib import Path

import pytest
from typer.testing import CliRunner

from planboard.adapters.cli import skills
from planboard.adapters.cli.app import app

runner = CliRunner()


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "home"
    path.mkdir()
    monkeypatch.setenv("HOME", str(path))
    for variable in ("XDG_CONFIG_HOME", "CLAUDE_CONFIG_DIR", "CODEX_HOME"):
        monkeypatch.delenv(variable, raising=False)
    return path


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "project"
    path.mkdir()
    monkeypatch.chdir(path)
    return path


def test_install_into_the_project_by_default(home: Path, project: Path) -> None:
    result = runner.invoke(app, ["skill", "install", "-a", "claude-code,codex", "-y"])

    assert result.exit_code == 0
    assert (project / ".agents" / "skills" / "planboard" / "SKILL.md").is_file()
    assert (project / ".claude" / "skills" / "planboard-next").is_symlink()
    assert not (home / ".claude").exists()


def test_global_installs_into_the_home_folder(home: Path, project: Path) -> None:
    (home / ".claude").mkdir()

    result = runner.invoke(app, ["skill", "install", "-g", "-y"])

    assert result.exit_code == 0
    assert (home / ".claude" / "skills" / "planboard" / "SKILL.md").is_file()
    assert list(project.iterdir()) == []


def test_yes_without_any_agent_found_installs_for_all(
    home: Path, project: Path
) -> None:
    result = runner.invoke(app, ["skill", "install", "-y"])

    assert result.exit_code == 0
    assert (project / ".agents" / "skills" / "planboard").is_dir()
    assert (project / ".claude" / "skills" / "planboard").is_symlink()


def test_questions_without_a_terminal_install_nothing(
    home: Path, project: Path
) -> None:
    result = runner.invoke(app, ["skill", "install", "-a", "codex"])

    assert result.exit_code == 1
    assert "needs a terminal" in result.output
    assert list(project.iterdir()) == []


def test_the_questions_pick_agents_scope_and_method(
    home: Path, project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(skills, "_need_terminal", lambda: None)

    result = runner.invoke(
        app, ["skill", "install"], input="1,cursor\nglobal\ncopy\ny\n"
    )

    assert result.exit_code == 0, result.output
    assert (home / ".claude" / "skills" / "planboard" / "SKILL.md").is_file()
    assert (home / ".cursor" / "skills" / "planboard" / "SKILL.md").is_file()
    assert not (home / ".claude" / "skills" / "planboard").is_symlink()


def test_an_unknown_agent_is_a_usage_error(home: Path, project: Path) -> None:
    result = runner.invoke(app, ["skill", "install", "-a", "claude", "-y"])

    assert result.exit_code == 2
    assert "Did you mean claude-code?" in result.output


def test_list_shows_both_folders(home: Path) -> None:
    result = runner.invoke(app, ["skill", "install", "--list"])

    assert result.exit_code == 0
    assert ".claude/skills" in result.output
    assert "~/.config/opencode/skills" in result.output


def test_uninstall_removes_the_skills_and_their_links(
    home: Path, project: Path
) -> None:
    runner.invoke(app, ["skill", "install", "-a", "claude-code,codex", "-y"])

    result = runner.invoke(app, ["skill", "uninstall", "-y"])

    assert result.exit_code == 0
    assert not (project / ".agents" / "skills").exists()
    assert not (project / ".claude" / "skills").exists()


def test_uninstall_one_agent_keeps_the_shared_copy(home: Path, project: Path) -> None:
    runner.invoke(app, ["skill", "install", "-a", "claude-code,codex", "-y"])

    result = runner.invoke(app, ["skill", "uninstall", "-a", "claude-code", "-y"])

    assert result.exit_code == 0
    assert not (project / ".claude" / "skills").exists()
    assert (project / ".agents" / "skills" / "planboard" / "SKILL.md").is_file()


def test_uninstall_dry_run_and_nothing_installed(home: Path, project: Path) -> None:
    result = runner.invoke(app, ["skill", "uninstall", "-y"])
    assert result.exit_code == 0
    assert "No planboard skills" in result.output

    runner.invoke(app, ["skill", "install", "-a", "codex", "-y"])
    result = runner.invoke(app, ["skill", "uninstall", "--dry-run"])
    assert ".agents/skills/planboard" in result.output
    assert (project / ".agents" / "skills" / "planboard").is_dir()


def test_uninstall_leaves_other_skills_alone(home: Path, project: Path) -> None:
    runner.invoke(app, ["skill", "install", "-a", "codex", "-y"])
    (project / ".agents" / "skills" / "mine").mkdir()

    runner.invoke(app, ["skill", "uninstall", "-y"])

    assert [p.name for p in (project / ".agents" / "skills").iterdir()] == ["mine"]
