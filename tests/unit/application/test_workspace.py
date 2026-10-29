import json
from pathlib import Path

import pytest

from planboard.application.ports import BreaksReferencesError, PlanExistsError
from planboard.application.workspace import Workspace
from planboard.domain.edits.errors import EditError
from planboard.domain.edits.tasks import remove_task, set_task
from tests.support import WritePlan

BASE = [{"id": "base", "title": "Base"}]
USER = [{"id": "use", "title": "Use", "dependsOn": ["area/base#base"]}]


@pytest.fixture
def linked(write_plan: WritePlan) -> None:
    write_plan("area/base", tasks=BASE)
    write_plan("area/user", tasks=USER)


@pytest.mark.usefixtures("linked")
def test_an_edit_that_breaks_another_plan_is_refused(
    workspace: Workspace, data_dir: Path
) -> None:
    before = (data_dir / "area/base/plan.json").read_text()

    with pytest.raises(BreaksReferencesError) as refused:
        workspace.edit("area/base", lambda draft: remove_task(draft, "base"))

    assert [(p.plan_id, p.message) for p in refused.value.problems] == [
        ("area/user", "'area/base#base' does not resolve")
    ]
    assert (data_dir / "area/base/plan.json").read_text() == before


@pytest.mark.usefixtures("linked")
def test_force_writes_a_breaking_edit(workspace: Workspace) -> None:
    workspace.edit("area/base", lambda draft: remove_task(draft, "base"), force=True)

    assert [p.message for p in workspace.problems()] == [
        "'area/base#base' does not resolve"
    ]


def test_a_dependency_cycle_is_refused(
    workspace: Workspace, write_plan: WritePlan
) -> None:
    write_plan(
        "area/a",
        tasks=[
            {"id": "x", "title": "X"},
            {"id": "y", "title": "Y", "dependsOn": ["#x"]},
        ],
    )

    with pytest.raises(BreaksReferencesError, match="cycle"):
        workspace.edit("area/a", lambda d: set_task(d, "x", {"dependsOn": ["#y"]}))


@pytest.mark.usefixtures("linked")
def test_existing_problems_do_not_block_an_edit(workspace: Workspace) -> None:
    workspace.edit("area/base", lambda draft: remove_task(draft, "base"), force=True)

    workspace.edit("area/user", lambda d: set_task(d, "use", {"title": "Used"}))


def test_move_plan_moves_the_folder_and_its_own_references(
    workspace: Workspace, write_plan: WritePlan, data_dir: Path
) -> None:
    write_plan(
        "area/old",
        tasks=[
            {"id": "a", "title": "A"},
            {"id": "b", "title": "B", "dependsOn": ["area/old#a"]},
        ],
    )

    workspace.move_plan("area/old", "other/new")

    assert not (data_dir / "area").exists()
    plan = json.loads((data_dir / "other/new/plan.json").read_text())
    assert plan["tasks"][1]["dependsOn"] == ["other/new#a"]
    assert workspace.problems() == []


@pytest.mark.usefixtures("linked")
def test_move_plan_is_refused_while_another_plan_refers_to_it(
    workspace: Workspace, data_dir: Path
) -> None:
    with pytest.raises(BreaksReferencesError):
        workspace.move_plan("area/base", "area/moved")

    assert (data_dir / "area/base/plan.json").is_file()


@pytest.mark.usefixtures("linked")
def test_move_plan_refuses_a_taken_or_nested_id(workspace: Workspace) -> None:
    with pytest.raises(PlanExistsError):
        workspace.move_plan("area/user", "area/base")
    with pytest.raises(EditError, match="inside itself"):
        workspace.move_plan("area/user", "area/user/deeper")


@pytest.mark.usefixtures("linked")
def test_remove_plan_is_refused_while_referred_to(
    workspace: Workspace, data_dir: Path
) -> None:
    with pytest.raises(BreaksReferencesError):
        workspace.remove_plan("area/base")

    removed = workspace.remove_plan("area/user")

    assert "plan.json" in removed
    assert not (data_dir / "area/user").exists()
    assert (data_dir / "area/base").exists()


def test_create_plan_dry_run_writes_nothing(
    workspace: Workspace, data_dir: Path
) -> None:
    workspace.create_plan("area/new", fields={"tags": ["core"]}, dry_run=True)

    assert not (data_dir / "area").exists()
