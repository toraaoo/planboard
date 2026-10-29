"""The CLI end to end: start a workspace, find it from a subfolder, edit a plan."""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

import planboard
from planboard.adapters.cli.app import app

runner = CliRunner()


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.delenv("PLANBOARD_DATA", raising=False)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    monkeypatch.chdir(tmp_path)
    return tmp_path


def run(*args: str) -> tuple[int, str]:
    result = runner.invoke(app, list(args))
    return result.exit_code, result.output


def test_init_then_work_from_a_subfolder(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert run("init")[0] == 0
    (project / "src" / "deep").mkdir(parents=True)
    monkeypatch.chdir(project / "src" / "deep")

    assert run("new", "area/first", "--title", "First")[0] == 0
    code, output = run("where", "--json")

    assert code == 0
    assert json.loads(output)["plans"] == str(project.resolve() / "plans")
    plan = json.loads((project / "plans" / "area" / "first" / "plan.json").read_text())
    assert plan["$schema"] == "../../.schema/plan.schema.json"
    assert (project / "plans" / ".schema" / "plan.schema.json").is_file()
    assert run("validate")[0] == 0


def test_init_refuses_an_existing_workspace(project: Path) -> None:
    run("init")

    code, output = run("init")

    assert code == 1
    assert "already exists" in output


def test_without_a_workspace_plans_go_to_the_user_folder(project: Path) -> None:
    code, output = run("where", "--json")

    assert code == 0
    assert json.loads(output)["from"] == "user"
    assert str(project / "xdg") in json.loads(output)["plans"]


def test_the_library_opens_the_same_workspace(project: Path) -> None:
    run("init")
    run("new", "area/first")

    workspace = planboard.open_workspace()

    assert list(workspace.catalog().loaded) == ["area/first"]
    assert [task.id for _, task in workspace.ready()] == ["first-step"]
