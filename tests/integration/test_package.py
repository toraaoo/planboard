"""Build the wheel and check that it carries everything the installed tool needs."""

import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.skipif(shutil.which("uv") is None, reason="needs uv")


@pytest.fixture(scope="module")
def wheel(tmp_path_factory: pytest.TempPathFactory) -> zipfile.ZipFile:
    out = tmp_path_factory.mktemp("dist")
    subprocess.run(
        ["uv", "build", "--wheel", "--out-dir", str(out), str(ROOT)],
        check=True,
        capture_output=True,
    )
    return zipfile.ZipFile(next(out.glob("planboard-*.whl")))


def test_the_wheel_ships_package_data(wheel: zipfile.ZipFile) -> None:
    names = set(wheel.namelist())

    assert "planboard/py.typed" in names
    assert "planboard/resources/templates/feature.json" in names
    assert "planboard/resources/skills/planboard/SKILL.md" in names
    assert "planboard/adapters/web/static/index.html" in names
    assert any(
        name.startswith("planboard/adapters/web/static/assets/mermaid")
        for name in names
    )
    assert any(name.endswith(".woff2") for name in names)


def test_the_wheel_ships_no_plans_or_tests(wheel: zipfile.ZipFile) -> None:
    names = wheel.namelist()

    assert not [name for name in names if name.startswith(("data/", "tests/"))]


def test_the_wheel_declares_the_console_script(wheel: zipfile.ZipFile) -> None:
    entry_points = next(n for n in wheel.namelist() if n.endswith("entry_points.txt"))

    assert (
        "planboard = planboard.adapters.cli.app:main"
        in wheel.read(entry_points).decode()
    )
