import json
from pathlib import Path

from planboard.adapters.filesystem import schemas
from planboard.adapters.filesystem.repository import FilePlanRepository
from planboard.domain.draft import Draft
from tests.support import WritePlan, plan_document


def test_write_all_then_nothing_is_stale(tmp_path: Path) -> None:
    written = schemas.write_all(tmp_path)

    assert sorted(path.name for path in written) == [
        "plan.schema.json",
        "section.schema.json",
    ]
    assert schemas.stale(tmp_path) == []
    assert schemas.write_all(tmp_path) == []


def test_a_write_adds_missing_schema_files(data_dir: Path) -> None:
    schema_dir = data_dir / ".schema"
    repository = FilePlanRepository(data_dir, schema_dir)

    folder = repository.create("area/example", plan_document())

    assert schemas.stale(schema_dir) == []
    plan = json.loads((folder / "plan.json").read_text())
    assert plan["$schema"] == "../../.schema/plan.schema.json"


def test_a_dry_run_reports_files_and_writes_nothing(
    repository: FilePlanRepository, write_plan: WritePlan
) -> None:
    folder = write_plan("area/example")
    before = (folder / "plan.json").read_text()

    def change(draft: Draft) -> None:
        draft.sections["design"]["title"] = "Renamed"

    result = repository.edit("area/example", change, dry_run=True)

    assert result.written == ("plan.json", "sections/design.json")
    assert result.removed == ()
    assert result.plan.sections[0].title == "Renamed"
    assert (folder / "plan.json").read_text() == before
