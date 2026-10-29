from pathlib import Path
from typing import Any

import pytest

from planboard.adapters.filesystem.repository import FilePlanRepository
from planboard.application.workspace import Workspace
from tests.support import WritePlan, plan_document, write_folder


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    path = tmp_path / "data"
    path.mkdir()
    return path


@pytest.fixture
def repository(data_dir: Path) -> FilePlanRepository:
    return FilePlanRepository(data_dir)


@pytest.fixture
def workspace(repository: FilePlanRepository) -> Workspace:
    return Workspace(repository)


@pytest.fixture
def write_plan(data_dir: Path) -> WritePlan:
    def write(plan_id: str, **overrides: Any) -> Path:
        return write_folder(data_dir / plan_id, plan_document(**overrides))

    return write
