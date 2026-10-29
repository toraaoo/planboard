from __future__ import annotations

import threading
import webbrowser
from pathlib import Path
from typing import Annotated

import typer

from ... import config
from ..filesystem import schemas
from ..web.server import LOOPBACK_HOSTS, serving
from .shared import (
    JsonFlag,
    console,
    done,
    fail,
    hint,
    print_json,
    session_of,
    workspace_of,
)

ORIGINS = {
    "option": "--data",
    "environment": config.DATA_ENV,
    "config": config.CONFIG_FILE,
    "user": "user data folder (no planboard.toml found)",
}


def init(
    ctx: typer.Context,
    folder: Annotated[
        Path,
        typer.Argument(file_okay=False, help="Where to start the workspace."),
    ] = Path(),
    plans: Annotated[
        str,
        typer.Option(metavar="DIR", help="Plans folder, relative to the workspace."),
    ] = config.DEFAULT_PLANS,
    schema_dir: Annotated[
        str,
        typer.Option(
            "--schemas", metavar="DIR", help="JSON Schema folder, relative to it."
        ),
    ] = config.DEFAULT_SCHEMAS,
) -> None:
    """Start a workspace: planboard.toml, a plans folder and its JSON Schemas.

    Every command run in this folder, or below it, then uses these plans.
    """
    try:
        path = config.write(folder, plans, schema_dir)
    except FileExistsError:
        fail(f"{folder / config.CONFIG_FILE} already exists.", "Run planboard where.")
    settings = config.load(path)
    settings.plans.mkdir(parents=True, exist_ok=True)
    if settings.schemas is not None:
        schemas.write_all(settings.schemas)
    done(ctx, f"Created {path}")
    hint(ctx, 'Next: planboard new <folder/plan> --title "…"')


def where(ctx: typer.Context, as_json: JsonFlag = False) -> None:
    """Show which plans folder commands use, and why."""
    settings = session_of(ctx).settings
    rows = {
        "plans": str(settings.plans),
        "schemas": str(settings.schemas) if settings.schemas else None,
        "config": str(settings.config) if settings.config else None,
        "from": settings.origin,
    }
    if as_json:
        print_json(rows)
        return
    console.print(f"plans    {rows['plans']}", highlight=False)
    console.print(
        f"schemas  {rows['schemas'] or '(none: $schema links are off)'}",
        highlight=False,
    )
    console.print(f"from     {ORIGINS[settings.origin]}", highlight=False)
    if settings.origin == "user":
        hint(ctx, "Run planboard init to keep plans with a project instead.")


def validate(ctx: typer.Context, as_json: JsonFlag = False) -> None:
    """Check every plan, reference, link and diagram. Exits 1 on problems."""
    workspace = workspace_of(ctx)
    snapshot = workspace.catalog()
    problems = snapshot.all_problems()
    if as_json:
        print_json(
            {
                "valid": not problems,
                "plans": len(snapshot.loaded) + len(snapshot.broken),
                "problems": [
                    {"plan": problem.plan_id, "message": problem.message}
                    for problem in problems
                ],
            }
        )
        if problems:
            raise typer.Exit(1)
        return
    if not problems:
        count = len(snapshot.loaded)
        done(ctx, f"{count} plan{'' if count == 1 else 's'} valid in {workspace.root}")
        return
    width = max(len(problem.plan_id) for problem in problems)
    for problem in problems:
        console.print(
            f"{problem.plan_id:<{width}}  {problem.message}",
            markup=False,
            highlight=False,
        )
    fail(f"{len(problems)} problem{'' if len(problems) == 1 else 's'}")


def serve(
    ctx: typer.Context,
    host: Annotated[
        str,
        typer.Option(
            metavar="ADDRESS",
        ),
    ] = "127.0.0.1",
    port: Annotated[
        int,
        typer.Option(
            metavar="NUMBER",
        ),
    ] = 8765,
    open_browser: Annotated[
        bool, typer.Option("--open/--no-open", help="Open a browser tab.")
    ] = True,
) -> None:
    """Serve the web app: document, board and dependency graph."""
    loopback = host in LOOPBACK_HOSTS
    allowed = LOOPBACK_HOSTS if loopback else None
    url = f"http://{'localhost' if loopback else host}:{port}"
    try:
        with serving(workspace_of(ctx), host, port, allowed) as server:
            console.print(f"● planboard on {url}  ctrl+c to stop", highlight=False)
            if open_browser:
                threading.Timer(0.8, webbrowser.open, args=(url,)).start()
            server.serve_forever()
    except OSError as error:
        fail(f"Cannot listen on {host}:{port}: {error.strerror}", "Try --port.")
    except KeyboardInterrupt:
        pass


def schema(
    ctx: typer.Context,
    check: Annotated[
        bool, typer.Option(help="Fail if the files are out of date.")
    ] = False,
) -> None:
    """Regenerate the workspace's JSON Schemas from the installed models."""
    folder = session_of(ctx).settings.schemas
    if folder is None:
        fail(
            "This plans folder has no schema folder.",
            f"Set schemas in {config.CONFIG_FILE}, or run planboard init.",
        )
    if check:
        stale = schemas.stale(folder)
        if stale:
            fail(f"{', '.join(map(str, stale))} out of date", "Run planboard schema.")
        done(ctx, f"Schemas in {folder} are up to date")
        return
    changed = schemas.write_all(folder)
    for path in changed:
        done(ctx, f"Wrote {path}")
    if not changed:
        done(ctx, f"Schemas in {folder} are up to date")
