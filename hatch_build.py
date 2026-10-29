"""Build the web app into the package before Hatchling collects its files.

The wheel serves the built app from planboard/adapters/web/static so it works
offline. Building from the repository runs `bun run build` in frontend/; the
sdist ships the built files and no frontend/, so a wheel built from it needs
no JavaScript toolchain.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

STATIC_INDEX = Path("src/planboard/adapters/web/static/index.html")


class FrontendBuildHook(BuildHookInterface[Any]):
    PLUGIN_NAME = "custom"

    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        root = Path(self.root)
        frontend = root / "frontend"
        index = root / STATIC_INDEX
        if version == "editable" or os.environ.get("PLANBOARD_SKIP_FRONTEND"):
            return
        if not (frontend / "package.json").is_file():
            if not index.is_file():
                raise RuntimeError(
                    f"{STATIC_INDEX} is missing and there is no frontend/."
                )
            return
        bun = shutil.which("bun")
        if bun is None:
            raise RuntimeError(
                "Building planboard from the repository needs bun for the web app: "
                "https://bun.sh. Set PLANBOARD_SKIP_FRONTEND=1 to package the "
                "already built files instead."
            )
        self.app.display_info("Building the web app with bun")
        subprocess.run([bun, "install", "--frozen-lockfile"], cwd=frontend, check=True)
        subprocess.run([bun, "run", "build"], cwd=frontend, check=True)
        if not index.is_file():
            raise RuntimeError(f"The web app build did not produce {STATIC_INDEX}.")
