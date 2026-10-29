from planboard.application import catalog
from planboard.application.workspace import Workspace
from planboard.domain import references
from tests.support import WritePlan

DESIGN = {"id": "design", "title": "Design"}


def problems(workspace: Workspace) -> list[str]:
    return [problem.message for problem in workspace.catalog().problems]


def test_a_valid_plan_has_no_problems(
    workspace: Workspace, write_plan: WritePlan
) -> None:
    write_plan("area/example")

    assert problems(workspace) == []


def test_reports_a_diagram_ref_that_does_not_resolve(
    workspace: Workspace, write_plan: WritePlan
) -> None:
    blocks = [
        {"type": "diagram", "ref": "#flow"},
        {"type": "diagram", "ref": "area/other#flow"},
    ]
    write_plan("area/example", sections=[{**DESIGN, "blocks": blocks}])

    assert problems(workspace) == ["'area/other#flow' does not resolve"]


def test_reuses_a_diagram_from_another_plan(
    workspace: Workspace, write_plan: WritePlan
) -> None:
    write_plan("area/source")
    blocks = [{"type": "diagram", "ref": "area/source#flow"}]
    write_plan("area/reuser", diagrams={}, sections=[{**DESIGN, "blocks": blocks}])

    snapshot = catalog.build(workspace.repository)
    resolved = snapshot.diagrams.resolve("area/source#flow", "area/reuser")

    assert problems(workspace) == []
    assert resolved.source == "flowchart LR\n  a --> b"
    assert resolved.plan_title == "Example"


def test_reads_a_diagram_file_and_reports_a_missing_one(
    workspace: Workspace, write_plan: WritePlan
) -> None:
    folder = write_plan(
        "area/example",
        diagrams={"flow": {"alt": "A flow.", "file": "diagrams/flow.mmd"}},
    )

    assert problems(workspace) == ["diagram 'flow': 'diagrams/flow.mmd' cannot be read"]

    (folder / "diagrams").mkdir()
    (folder / "diagrams" / "flow.mmd").write_text("flowchart LR\n  a --> b")
    assert problems(workspace) == []


def test_reports_a_diagram_that_is_never_shown(
    workspace: Workspace, write_plan: WritePlan
) -> None:
    text = [{"type": "text", "text": "No diagram here."}]
    write_plan("area/example", sections=[{**DESIGN, "blocks": text}])

    assert problems(workspace) == ["diagram 'flow' is never shown"]


def test_reports_a_section_file_the_plan_does_not_list(
    workspace: Workspace, write_plan: WritePlan
) -> None:
    folder = write_plan("area/example")
    (folder / "sections" / "stray.json").write_text("{}")

    assert problems(workspace) == [
        "'sections/stray.json' is not listed in plan.json sections"
    ]


def test_reports_a_dependency_cycle(
    workspace: Workspace, write_plan: WritePlan
) -> None:
    write_plan(
        "area/example",
        tasks=[
            {"id": "first", "title": "First", "dependsOn": ["#second"]},
            {"id": "second", "title": "Second", "dependsOn": ["#first"]},
        ],
    )

    assert any("dependency cycle" in message for message in problems(workspace))


def test_lists_todo_tasks_whose_dependencies_are_done(
    workspace: Workspace, write_plan: WritePlan
) -> None:
    write_plan(
        "area/example",
        tasks=[
            {"id": "first", "title": "First", "status": "done"},
            {"id": "second", "title": "Second", "dependsOn": ["#first"]},
            {"id": "third", "title": "Third", "dependsOn": ["#second"]},
        ],
    )

    ready = references.ready(catalog.build(workspace.repository).plans)

    assert [(plan_id, task.id) for plan_id, task in ready] == [
        ("area/example", "second")
    ]
