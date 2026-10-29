import json
from typing import Any

import pytest

from planboard.domain.draft import Draft
from planboard.domain.edits.blocks import (
    add_block,
    move_block,
    remove_block,
    set_block,
)
from planboard.domain.edits.diagrams import (
    add_diagram,
    remove_diagram,
    rename_diagram,
)
from planboard.domain.edits.document import Place
from planboard.domain.edits.errors import EditError, UnknownIdError
from planboard.domain.edits.plan import retarget_plan
from planboard.domain.edits.sections import (
    add_section,
    remove_section,
    rename_section,
    set_section,
)
from planboard.domain.edits.tasks import (
    add_task,
    move_task,
    remove_task,
    rename_task,
    set_task,
)
from planboard.domain.json import JsonObject
from tests.support import plan_document

TEXT: JsonObject = {"type": "text", "text": "See [the design](#design)."}


def draft(**overrides: Any) -> Draft:
    return Draft.from_document(plan_document(**overrides))


def tasks(**overrides: Any) -> Draft:
    return draft(
        tasks=[
            {"id": "first", "title": "First", "sections": ["design"]},
            {"id": "second", "title": "Second", "dependsOn": ["#first"]},
        ],
        **overrides,
    )


def data(value: object) -> Any:
    return json.loads(json.dumps(value))


def task_ids(target: Draft) -> list[str]:
    return [task["id"] for task in data(target.plan)["tasks"]]


def test_set_task_changes_and_clears_fields() -> None:
    target = tasks()

    set_task(target, "first", {"status": "blocked", "note": "Waiting."})
    set_task(target, "first", {"note": None})

    assert data(target.plan)["tasks"][0] == {
        "id": "first",
        "title": "First",
        "sections": ["design"],
        "status": "blocked",
    }
    assert target.validate("area/example").tasks[0].status == "blocked"


def test_set_task_rejects_an_unknown_task() -> None:
    with pytest.raises(UnknownIdError, match="No task named 'missing'"):
        set_task(tasks(), "missing", {"status": "done"})


def test_add_and_move_tasks_by_place() -> None:
    target = tasks()

    add_task(target, {"id": "zero", "title": "Zero"}, Place(before="first"))
    move_task(target, "second", Place(after="zero"))

    assert task_ids(target) == ["zero", "second", "first"]


def test_remove_task_refuses_while_another_depends_on_it() -> None:
    target = tasks()

    with pytest.raises(EditError, match="dependency of: second"):
        remove_task(target, "first")
    remove_task(target, "second")
    assert task_ids(target) == ["first"]


def test_add_section_refuses_a_taken_id() -> None:
    with pytest.raises(EditError, match="already a section or diagram id"):
        add_section(draft(), "flow", "Flow", "Words.", Place())


def test_rename_section_follows_tasks_and_links() -> None:
    target = tasks(sections=[{"id": "design", "title": "Design", "blocks": [TEXT]}])
    target.plan["diagrams"] = {}

    rename_section(target, "area/example", "design", "architecture")

    plan = target.validate("area/example")
    assert [section.id for section in plan.sections] == ["architecture"]
    assert plan.tasks[0].sections == ["architecture"]
    assert target.sections["architecture"]["blocks"] == [
        {"type": "text", "text": "See [the design](#architecture)."}
    ]


def test_remove_section_refuses_while_a_task_builds_it() -> None:
    with pytest.raises(EditError, match="built by: first"):
        remove_section(tasks(), "design")


def test_add_diagram_writes_a_file_and_shows_it() -> None:
    target = draft()

    add_diagram(
        target,
        "sequence",
        "A sequence.",
        "sequenceDiagram\n  a->>b: hi",
        inline=False,
        section="design",
        caption="Who talks.",
    )

    plan = target.validate("area/example")
    assert plan.diagrams["sequence"].file == "diagrams/sequence.mmd"
    assert target.diagram_files == {
        "diagrams/sequence.mmd": "sequenceDiagram\n  a->>b: hi\n"
    }
    assert data(target.sections["design"])["blocks"][-1] == {
        "type": "diagram",
        "ref": "#sequence",
        "caption": "Who talks.",
    }


def test_remove_diagram_drops_its_blocks_and_task_links() -> None:
    target = draft(
        diagrams={
            "flow": {"alt": "A flow.", "file": "diagrams/flow.mmd"},
            "other": {"alt": "Other.", "source": "flowchart LR"},
        },
        sections=[
            {
                "id": "design",
                "title": "Design",
                "blocks": [
                    {"type": "diagram", "ref": "#flow"},
                    {"type": "diagram", "ref": "#other"},
                ],
            }
        ],
        tasks=[{"id": "first", "title": "First", "diagrams": ["flow"]}],
    )

    remove_diagram(target, "area/example", "flow")

    plan = target.validate("area/example")
    assert list(plan.diagrams) == ["other"]
    assert plan.tasks[0].diagrams == []
    assert target.diagram_files == {"diagrams/flow.mmd": None}


def test_rename_task_follows_dependencies_in_its_plan() -> None:
    target = tasks()
    set_task(target, "second", {"dependsOn": ["area/example#first"]})

    rename_task(target, "area/example", "first", "start")

    assert task_ids(target) == ["start", "second"]
    assert data(target.plan)["tasks"][1]["dependsOn"] == ["area/example#start"]
    target.validate("area/example")


def test_rename_task_refuses_a_taken_id() -> None:
    with pytest.raises(EditError, match="already exists"):
        rename_task(tasks(), "area/example", "first", "second")


def test_rename_diagram_moves_its_file_blocks_tasks_and_links() -> None:
    target = draft(
        diagrams={"flow": {"alt": "A flow.", "file": "diagrams/flow.mmd"}},
        sections=[
            {
                "id": "design",
                "title": "Design",
                "blocks": [
                    {"type": "text", "text": "See [it](#flow)."},
                    {"type": "diagram", "ref": "area/example#flow"},
                ],
            }
        ],
        tasks=[{"id": "first", "title": "First", "diagrams": ["flow"]}],
    )
    target.diagram_sources["diagrams/flow.mmd"] = "flowchart LR\n"

    rename_diagram(target, "area/example", "flow", "main")

    plan = target.validate("area/example")
    assert plan.diagrams["main"].file == "diagrams/main.mmd"
    assert target.diagram_files == {
        "diagrams/main.mmd": "flowchart LR\n",
        "diagrams/flow.mmd": None,
    }
    assert data(target.sections["design"])["blocks"] == [
        {"type": "text", "text": "See [it](#main)."},
        {"type": "diagram", "ref": "area/example#main"},
    ]
    assert plan.tasks[0].diagrams == ["main"]


def test_blocks_are_added_changed_moved_and_removed_by_number() -> None:
    target = draft()

    add_block(target, "design", {"type": "heading", "text": "Shape"}, at=1)
    add_block(target, "design", TEXT)
    set_block(target, "design", 1, {"text": "Form"})
    move_block(target, "design", 3, 1)
    remove_block(target, "design", 3)

    assert data(target.sections["design"])["blocks"] == [
        TEXT,
        {"type": "heading", "text": "Form"},
    ]
    target.validate("area/example")


def test_a_block_number_out_of_range_is_refused() -> None:
    with pytest.raises(UnknownIdError, match="has 1 block; there is no block 2"):
        set_block(draft(), "design", 2, {"text": "x"})


def test_set_section_replaces_title_and_blocks() -> None:
    target = draft()

    set_section(target, "design", "Shape", [TEXT])

    section = target.validate("area/example").sections[0]
    assert (section.title, len(section.blocks)) == ("Shape", 1)


def test_retarget_plan_points_its_own_references_at_the_new_id() -> None:
    target = draft(
        summary="See [design](area/example#design) and [other](area/examples).",
        sections=[
            {
                "id": "design",
                "title": "Design",
                "blocks": [{"type": "diagram", "ref": "area/example#flow"}],
            }
        ],
        tasks=[
            {"id": "first", "title": "First"},
            {"id": "second", "title": "S", "dependsOn": ["area/example#first"]},
        ],
    )

    retarget_plan(target, "area/example", "area/moved")

    plan = target.validate("area/moved")
    assert plan.summary == "See [design](area/moved#design) and [other](area/examples)."
    assert plan.tasks[1].depends_on == ["area/moved#first"]
    assert data(target.sections["design"])["blocks"][0]["ref"] == "area/moved#flow"
