import pytest
from pydantic import ValidationError

from planboard.domain.plan import Plan
from tests.support import plan_document


def test_accepts_a_minimal_plan() -> None:
    plan = Plan.model_validate(plan_document())

    assert plan.anchors() == {"design", "flow"}


def test_a_diagram_needs_exactly_one_origin() -> None:
    both = {"alt": "A flow.", "source": "flowchart LR", "file": "a/flow.mmd"}

    with pytest.raises(ValidationError, match="either source or file"):
        Plan.model_validate(plan_document(diagrams={"flow": both}))


def test_section_and_diagram_ids_share_one_namespace() -> None:
    diagram = {"alt": "Clash.", "source": "flowchart LR"}

    with pytest.raises(ValidationError, match="duplicate section and diagram ids"):
        Plan.model_validate(plan_document(diagrams={"design": diagram}))


def test_a_task_names_only_known_diagrams() -> None:
    task = {"id": "build", "title": "Build", "diagrams": ["missing"]}

    with pytest.raises(ValidationError, match="unknown diagrams"):
        Plan.model_validate(plan_document(tasks=[task]))
