"""The commands added for blocks, renames, plan moves, search and filters."""

import json
from pathlib import Path

from typer.testing import CliRunner

from planboard.adapters.cli.app import app
from tests.support import WritePlan

runner = CliRunner()

TASKS = [
    {"id": "first", "title": "First", "status": "doing"},
    {"id": "second", "title": "Second", "dependsOn": ["#first"]},
]


def run(data_dir: Path, *args: str, stdin: str | None = None) -> tuple[int, str]:
    result = runner.invoke(app, ["--data", str(data_dir), *args], input=stdin)
    return result.exit_code, result.output


def blocks(folder: Path, section: str = "design") -> list[dict[str, object]]:
    document = json.loads((folder / "sections" / f"{section}.json").read_text())
    return document["blocks"]


def test_next_shows_work_in_progress_when_nothing_is_ready(
    data_dir: Path, write_plan: WritePlan
) -> None:
    write_plan("area/example", tasks=TASKS)

    code, output = run(data_dir, "next", "--json")

    found = json.loads(output)
    assert code == 0
    assert found["ready"] == []
    assert [t["id"] for t in found["doing"]] == ["first"]
    assert found["doing"][0]["readies"] == ["area/example#second"]
    assert found["waiting"][0]["waitingOn"] == ["#first"]

    code, output = run(data_dir, "next")
    assert "In progress" in output
    assert "finishing it readies #second" in output


def test_next_and_board_filter_by_folder_and_tag(
    data_dir: Path, write_plan: WritePlan
) -> None:
    write_plan("area/example", tasks=TASKS, tags=["core"])
    write_plan("other/plan", tasks=[{"id": "solo", "title": "Solo"}])

    _, output = run(data_dir, "next", "other", "--json")
    assert [t["id"] for t in json.loads(output)["ready"]] == ["solo"]
    _, output = run(data_dir, "board", "--tag", "core", "--status", "todo", "--json")
    assert [t["id"] for t in json.loads(output)] == ["second"]
    code, _ = run(data_dir, "board", "--status", "later")
    assert code == 2


def test_outline_filters_plans_by_tag(data_dir: Path, write_plan: WritePlan) -> None:
    write_plan("area/example", tags=["core"])
    write_plan("other/plan")

    _, output = run(data_dir, "outline", "--tag", "core", "--json")

    assert [plan["id"] for plan in json.loads(output)["plans"]] == ["area/example"]


def test_task_show_reports_dependencies_both_ways(
    data_dir: Path, write_plan: WritePlan
) -> None:
    write_plan("area/example", tasks=TASKS)

    code, output = run(data_dir, "task", "show", "area/example#first", "--json")

    shown = json.loads(output)
    assert code == 0
    assert (shown["position"], shown["neededBy"]) == (1, ["area/example#second"])
    code, output = run(data_dir, "show", "area/example#second")
    assert code == 0
    assert "#first (pending)" in output


def test_block_commands_edit_a_section(data_dir: Path, write_plan: WritePlan) -> None:
    folder = write_plan("area/example")

    run(data_dir, "block", "add", "area/example#design", "text", "--text", "Hi.")
    run(
        data_dir,
        "block",
        "add",
        "area/example#design",
        "list",
        "--item",
        "a",
        "--item",
        "b",
        "--ordered",
        "--at",
        "1",
    )
    run(data_dir, "block", "set", "area/example#design", "3", "--text", "Hello.")
    code, output = run(data_dir, "block", "list", "area/example#design")

    assert code == 0
    assert "list" in output
    assert blocks(folder) == [
        {"type": "list", "items": ["a", "b"], "ordered": True},
        {"type": "diagram", "ref": "#flow"},
        {"type": "text", "text": "Hello."},
    ]


def test_block_add_takes_a_table_and_json(
    data_dir: Path, write_plan: WritePlan
) -> None:
    folder = write_plan("area/example")

    run(
        data_dir,
        "block",
        "add",
        "area/example#design",
        "table",
        "--columns",
        "Name | Why",
        "--row",
        "A | ",
    )
    run(
        data_dir,
        "block",
        "add",
        "area/example#design",
        "--json",
        "-",
        stdin='{"type": "heading", "text": "End"}',
    )

    assert blocks(folder)[1:] == [
        {"type": "table", "columns": ["Name", "Why"], "rows": [["A", None]]},
        {"type": "heading", "text": "End"},
    ]


def test_a_block_option_for_another_type_is_a_usage_error(
    data_dir: Path, write_plan: WritePlan
) -> None:
    write_plan("area/example")

    code, output = run(
        data_dir, "block", "add", "area/example#design", "text", "--title", "No"
    )

    assert code == 2
    assert "does not apply to a text block" in output


def test_section_set_from_replaces_its_blocks(
    data_dir: Path, write_plan: WritePlan
) -> None:
    folder = write_plan("area/example")
    section = {"title": "Shape", "blocks": [{"type": "diagram", "ref": "#flow"}]}

    code, _ = run(
        data_dir,
        "section",
        "set",
        "area/example#design",
        "--from",
        "-",
        stdin=json.dumps(section),
    )

    assert code == 0
    assert json.loads((folder / "sections/design.json").read_text())["title"] == "Shape"


def test_a_write_that_breaks_another_plan_needs_force(
    data_dir: Path, write_plan: WritePlan
) -> None:
    write_plan("area/base", tasks=[{"id": "base", "title": "Base"}])
    write_plan(
        "area/user", tasks=[{"id": "u", "title": "U", "dependsOn": ["area/base#base"]}]
    )

    code, output = run(data_dir, "task", "rename", "area/base#base", "root")
    assert code == 1
    assert "would break references" in output

    code, _ = run(data_dir, "task", "rename", "area/base#base", "root", "--force")
    assert code == 0


def test_plan_mv_and_rm(data_dir: Path, write_plan: WritePlan) -> None:
    write_plan("area/example")

    code, _ = run(data_dir, "plan", "mv", "area/example", "area/moved")
    assert code == 0
    code, output = run(data_dir, "plan", "rm", "area/moved", "--dry-run")
    assert "would remove area/moved/plan.json" in output
    code, _ = run(data_dir, "plan", "rm", "area/moved", "-y")
    assert code == 0
    assert not (data_dir / "area").exists()


def test_search_is_fuzzy_and_exits_1_without_a_match(
    data_dir: Path, write_plan: WritePlan
) -> None:
    write_plan("area/example", tasks=TASKS)

    code, output = run(data_dir, "search", "secnd", "--json")
    assert code == 0
    assert json.loads(output)[0]["ref"] == "area/example#second"
    code, _ = run(data_dir, "search", "xyzzy")
    assert code == 1


def test_new_sets_fields_and_has_a_dry_run(data_dir: Path) -> None:
    code, _ = run(
        data_dir, "new", "area/fresh", "--summary", "Why.", "--tags", "a,b", "--dry-run"
    )
    assert code == 0
    assert not (data_dir / "area").exists()

    run(data_dir, "new", "area/fresh", "--summary", "Why.", "--tags", "a,b")
    plan = json.loads((data_dir / "area/fresh/plan.json").read_text())
    assert (plan["summary"], plan["tags"]) == ("Why.", ["a", "b"])
