import datetime
import json
from pathlib import Path

import pytest

from planboard.adapters.filesystem.repository import FilePlanRepository
from planboard.application.ports import BrokenPlan, LoadedPlan, PlanExistsError
from planboard.domain.draft import Draft, InvalidPlanError
from tests.support import WritePlan, plan_document


def test_create_splits_a_plan_into_files_with_schema_links(data_dir: Path) -> None:
    repository = FilePlanRepository(data_dir, data_dir.parent / "schema")

    folder = repository.create("area/example", plan_document())

    plan = json.loads((folder / "plan.json").read_text())
    section = json.loads((folder / "sections" / "design.json").read_text())
    assert plan["sections"] == ["design"]
    assert plan["$schema"] == "../../../schema/plan.schema.json"
    assert section["$schema"] == "../../../../schema/section.schema.json"
    assert section["title"] == "Design"
    assert "id" not in section


def test_create_refuses_an_existing_plan(
    repository: FilePlanRepository, write_plan: WritePlan
) -> None:
    write_plan("area/example")

    with pytest.raises(PlanExistsError):
        repository.create("area/example", plan_document())


def test_finds_plans_by_folder_and_ignores_files_inside_a_plan(
    repository: FilePlanRepository, write_plan: WritePlan
) -> None:
    folder = write_plan("area/example")
    write_plan("area/example/sections/nested")
    (folder / "sections" / "plan.json").write_text("{}")

    assert repository.ids() == ["area/example"]


def test_names_the_file_a_load_error_comes_from(
    repository: FilePlanRepository, write_plan: WritePlan
) -> None:
    folder = write_plan("area/example")
    (folder / "sections" / "design.json").write_text('{"title": "Design"}')

    entry = repository.load("area/example")

    assert isinstance(entry, BrokenPlan)
    assert entry.errors == ("sections/design.json: blocks: Field required",)


def test_reports_a_listed_section_without_a_file(
    repository: FilePlanRepository, write_plan: WritePlan
) -> None:
    folder = write_plan("area/example")
    (folder / "sections" / "design.json").unlink()

    entry = repository.load("area/example")

    assert isinstance(entry, BrokenPlan)
    assert entry.errors == ("sections/design.json: cannot be read",)


def test_an_edit_rewrites_only_changed_files_and_stamps_the_date(
    repository: FilePlanRepository, write_plan: WritePlan
) -> None:
    folder = write_plan("area/example", tasks=[{"id": "first", "title": "First"}])
    section = folder / "sections" / "design.json"
    before = section.stat().st_mtime_ns

    def change(draft: Draft) -> None:
        draft.plan["title"] = "Renamed"

    plan = repository.edit("area/example", change).plan

    assert plan.title == "Renamed"
    assert plan.updated == datetime.date.today()
    assert section.stat().st_mtime_ns == before


def test_an_edit_that_would_break_the_plan_writes_nothing(
    repository: FilePlanRepository, write_plan: WritePlan
) -> None:
    folder = write_plan("area/example")
    original = (folder / "plan.json").read_text()

    def change(draft: Draft) -> None:
        draft.plan["status"] = "finished"

    with pytest.raises(InvalidPlanError):
        repository.edit("area/example", change)
    assert (folder / "plan.json").read_text() == original


def test_an_edit_deletes_removed_section_files(
    repository: FilePlanRepository, write_plan: WritePlan
) -> None:
    text = {"type": "text", "text": "Words."}
    folder = write_plan(
        "area/example",
        diagrams={},
        sections=[
            {"id": "design", "title": "Design", "blocks": [text]},
            {"id": "old", "title": "Old", "blocks": [text]},
        ],
    )

    def change(draft: Draft) -> None:
        draft.plan["sections"] = ["design"]
        del draft.sections["old"]

    repository.edit("area/example", change)

    assert not (folder / "sections" / "old.json").exists()
    assert isinstance(repository.load("area/example"), LoadedPlan)
