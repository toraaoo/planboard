import json
from pathlib import Path

from typer.testing import CliRunner

from planboard.adapters.cli.app import app
from tests.support import WritePlan

runner = CliRunner()

TASKS = [
    {"id": "first", "title": "First", "status": "done"},
    {"id": "second", "title": "Second", "dependsOn": ["#first"]},
]


def run(data_dir: Path, *args: str) -> tuple[int, str]:
    result = runner.invoke(app, ["--data", str(data_dir), *args])
    return result.exit_code, result.output


def test_task_status_writes_the_plan(data_dir: Path, write_plan: WritePlan) -> None:
    folder = write_plan("area/example", tasks=TASKS)

    code, output = run(
        data_dir, "task", "status", "area/example#second", "blocked", "--note", "Why."
    )

    plan = json.loads((folder / "plan.json").read_text())
    assert code == 0
    assert "area/example#second is blocked" in output
    assert plan["tasks"][1]["status"] == "blocked"
    assert plan["tasks"][1]["note"] == "Why."


def test_a_reference_without_a_task_is_a_usage_error(
    data_dir: Path, write_plan: WritePlan
) -> None:
    write_plan("area/example", tasks=TASKS)

    code, _ = run(data_dir, "task", "status", "area/example", "done")

    assert code == 2


def test_a_refused_edit_exits_1(data_dir: Path, write_plan: WritePlan) -> None:
    write_plan("area/example", tasks=TASKS)

    code, _ = run(data_dir, "task", "rm", "area/example#first")

    assert code == 1


def test_outline_json_maps_files_and_waiting_tasks(
    data_dir: Path, write_plan: WritePlan
) -> None:
    write_plan("area/example", tasks=TASKS)

    code, output = run(data_dir, "outline", "area/example", "--json")

    outline = json.loads(output)
    assert code == 0
    assert outline["sections"][0]["file"] == "sections/design.json"
    assert [task["waitingOn"] for task in outline["tasks"]] == [[], []]


def test_next_lists_ready_tasks(data_dir: Path, write_plan: WritePlan) -> None:
    write_plan("area/example", tasks=TASKS)

    code, output = run(data_dir, "next", "--json")

    assert code == 0
    assert [(t["plan"], t["id"]) for t in json.loads(output)["ready"]] == [
        ("area/example", "second")
    ]


def test_show_renders_one_section(data_dir: Path, write_plan: WritePlan) -> None:
    write_plan("area/example", tasks=TASKS)

    code, output = run(data_dir, "show", "area/example#design")

    assert code == 0
    assert "Design" in output
    assert "a --> b" in output


def test_validate_exits_1_on_problems(data_dir: Path, write_plan: WritePlan) -> None:
    write_plan(
        "area/example", tasks=[{"id": "first", "title": "F", "dependsOn": ["#x"]}]
    )

    code, output = run(data_dir, "validate", "--json")

    assert code == 1
    assert json.loads(output)["valid"] is False


def test_new_writes_a_plan_folder(data_dir: Path) -> None:
    code, _ = run(data_dir, "new", "area/fresh", "--title", "Fresh")

    assert code == 0
    assert (data_dir / "area" / "fresh" / "plan.json").is_file()
    code, _ = run(data_dir, "validate")
    assert code == 0


def test_version_prints_the_installed_version() -> None:
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert result.output.startswith("planboard ")


def test_dry_run_lists_files_and_writes_nothing(
    data_dir: Path, write_plan: WritePlan
) -> None:
    folder = write_plan("area/example", tasks=TASKS)
    before = (folder / "plan.json").read_text()

    code, output = run(
        data_dir, "task", "status", "area/example#second", "doing", "--dry-run"
    )

    assert code == 0
    assert "would write  area/example/plan.json" in output
    assert (folder / "plan.json").read_text() == before


def test_quiet_drops_the_confirmation(data_dir: Path, write_plan: WritePlan) -> None:
    write_plan("area/example", tasks=TASKS)

    code, output = run(
        data_dir, "--quiet", "task", "status", "area/example#second", "doing"
    )

    assert code == 0
    assert output == ""


def test_an_unknown_plan_suggests_a_close_one(
    data_dir: Path, write_plan: WritePlan
) -> None:
    write_plan("area/example", tasks=TASKS)

    code, output = run(data_dir, "outline", "area/exmple")

    assert code == 1
    assert "Did you mean area/example?" in output


def test_rm_skips_the_prompt_without_a_terminal(
    data_dir: Path, write_plan: WritePlan
) -> None:
    write_plan("area/example", tasks=TASKS)

    code, _ = run(data_dir, "task", "rm", "area/example#second")

    assert code == 0
