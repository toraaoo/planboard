from pathlib import Path

import pytest

from planboard import config
from planboard.config import ConfigError, discover


def test_an_explicit_folder_wins(tmp_path: Path) -> None:
    config.write(tmp_path)

    settings = discover(tmp_path / "elsewhere", start=tmp_path, environ={})

    assert settings.plans == (tmp_path / "elsewhere").resolve()
    assert settings.schemas is None
    assert settings.origin == "option"


def test_the_environment_comes_after_the_option(tmp_path: Path) -> None:
    environ = {config.DATA_ENV: str(tmp_path / "from-env")}

    assert discover(None, environ=environ).origin == "environment"
    assert discover(tmp_path, environ=environ).origin == "option"


def test_finds_the_nearest_config_in_a_parent_folder(tmp_path: Path) -> None:
    config.write(tmp_path, plans="data", schemas="schema")
    nested = tmp_path / "src" / "deep"
    nested.mkdir(parents=True)

    settings = discover(start=nested, environ={})

    assert settings.origin == "config"
    assert settings.plans == tmp_path.resolve() / "data"
    assert settings.schemas == tmp_path.resolve() / "schema"


def test_an_explicit_folder_keeps_the_schemas_of_its_workspace(
    tmp_path: Path,
) -> None:
    config.write(tmp_path)

    settings = discover(tmp_path / "plans", environ={})

    assert settings.schemas == tmp_path.resolve() / "plans" / ".schema"


def test_falls_back_to_the_user_data_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))

    settings = discover(start=tmp_path, environ={})

    assert settings.origin == "user"
    assert settings.plans == config.user_root() / "plans"


def test_rejects_unknown_keys(tmp_path: Path) -> None:
    (tmp_path / config.CONFIG_FILE).write_text('plans = "p"\nplan = "typo"\n')

    with pytest.raises(ConfigError, match="unknown keys plan"):
        discover(start=tmp_path, environ={})


def test_write_refuses_to_overwrite(tmp_path: Path) -> None:
    config.write(tmp_path)

    with pytest.raises(FileExistsError):
        config.write(tmp_path)
