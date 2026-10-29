from typing import Any

from planboard.domain import references
from planboard.domain.plan import Plan
from tests.support import plan_document


def plan(*tasks: dict[str, Any], **overrides: Any) -> Plan:
    return Plan.model_validate(plan_document(tasks=list(tasks), **overrides))


def test_readies_names_the_todo_tasks_one_task_holds_back() -> None:
    plans = {
        "area/a": plan(
            {"id": "base", "title": "Base", "status": "doing"},
            {"id": "next", "title": "Next", "dependsOn": ["#base"]},
            {"id": "later", "title": "Later", "dependsOn": ["#base", "#next"]},
        ),
        "area/b": plan({"id": "use", "title": "Use", "dependsOn": ["area/a#base"]}),
    }

    assert references.readies(plans) == {"area/a#base": ["area/a#next", "area/b#use"]}


def test_needed_by_finds_tasks_and_plans_in_any_plan() -> None:
    plans = {
        "area/a": plan(
            {"id": "base", "title": "Base"},
            {"id": "next", "title": "Next", "dependsOn": ["#base"]},
        ),
        "area/b": plan(
            {"id": "use", "title": "Use", "dependsOn": ["area/a#base"]},
            depends_on=["area/a"],
        ),
    }

    assert references.needed_by("area/a", "base", plans) == [
        "area/a#next",
        "area/b",
        "area/b#use",
    ]


def test_in_progress_lists_doing_before_blocked_and_skips_archived() -> None:
    plans = {
        "area/a": plan(
            {"id": "stuck", "title": "Stuck", "status": "blocked"},
            {"id": "busy", "title": "Busy", "status": "doing"},
        ),
        "area/old": plan(
            {"id": "busy", "title": "Busy", "status": "doing"}, status="archived"
        ),
    }

    found = [(plan_id, task.id) for plan_id, task in references.in_progress(plans)]
    assert found == [("area/a", "busy"), ("area/a", "stuck")]


def test_unresolved_diagrams_checks_block_refs_without_files() -> None:
    blocks = [{"type": "diagram", "ref": "area/gone#flow"}]
    plans = {
        "area/a": plan(sections=[{"id": "design", "title": "D", "blocks": blocks}])
    }

    problems = references.unresolved_diagrams(plans)
    assert [p.message for p in problems] == ["'area/gone#flow' does not resolve"]
