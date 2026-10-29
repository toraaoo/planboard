from __future__ import annotations

import json
import re
from collections.abc import Callable, Generator
from contextlib import contextmanager
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import as_file, files
from pathlib import Path
from typing import Any, TypeGuard
from urllib.parse import unquote, urlsplit

from ...application.ports import PlanNotFoundError
from ...application.workspace import Workspace
from ...domain.draft import InvalidPlanError
from ...domain.edits.errors import UnknownIdError
from ...domain.json import JsonObject, JsonValue
from ...domain.plan import TASK_STATUSES, TaskStatus

STATIC = files(__package__) / "static"
LOOPBACK_HOSTS = ("127.0.0.1", "localhost", "[::1]")

_TASK_PATH = re.compile(r"^/api/plans/(?P<plan>.+)/tasks/(?P<task>[^/]+)$")


class ApiError(Exception):
    def __init__(self, status: HTTPStatus, detail: object) -> None:
        super().__init__(status.phrase)
        self.status = status
        self.detail = detail


@contextmanager
def serving(
    workspace: Workspace,
    host: str,
    port: int,
    allowed_hosts: tuple[str, ...] | None,
) -> Generator[ThreadingHTTPServer]:
    """A server for the web app and its JSON API, closed on exit."""
    with as_file(STATIC) as static:
        server = create_server(workspace, host, port, allowed_hosts, static)
        try:
            yield server
        finally:
            server.server_close()


def create_server(
    workspace: Workspace,
    host: str,
    port: int,
    allowed_hosts: tuple[str, ...] | None,
    static: Path,
) -> ThreadingHTTPServer:
    attributes = {
        "workspace": workspace,
        "allowed_hosts": allowed_hosts,
        "static": str(static),
    }
    return ThreadingHTTPServer((host, port), type("Handler", (Handler,), attributes))


class Handler(SimpleHTTPRequestHandler):
    workspace: Workspace
    allowed_hosts: tuple[str, ...] | None
    static: str

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=self.static, **kwargs)

    def log_message(self, format: str, *args: Any) -> None:
        pass

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if not path.startswith("/api/"):
            if self._host_allowed():
                super().do_GET()
            return
        self._api(lambda: self._get(unquote(path)))

    def do_PATCH(self) -> None:
        self._api(lambda: self._patch(unquote(urlsplit(self.path).path)))

    def _get(self, path: str) -> object:
        if path == "/api/version":
            return {"version": self.workspace.version()}
        if path == "/api/plans":
            return self.workspace.plans()
        if path.startswith("/api/plans/"):
            plan_id = path.removeprefix("/api/plans/")
            try:
                return self.workspace.plan(plan_id)
            except PlanNotFoundError as error:
                raise _not_found(f"No plan named '{plan_id}'.") from error
        raise _not_found("No such endpoint.")

    def _patch(self, path: str) -> object:
        match = _TASK_PATH.match(path)
        if match is None:
            raise _not_found("No such endpoint.")
        plan_id, task_id = match["plan"], match["task"]
        status = self._read_json().get("status")
        if not _is_status(status):
            raise ApiError(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                f"status must be one of {', '.join(TASK_STATUSES)}.",
            )
        try:
            self.workspace.set_task_status(plan_id, task_id, status)
        except PlanNotFoundError as error:
            raise _not_found(f"No plan named '{plan_id}'.") from error
        except UnknownIdError as error:
            raise _not_found(str(error)) from error
        except InvalidPlanError as error:
            raise ApiError(
                HTTPStatus.CONFLICT,
                {
                    "message": "The plan file is invalid; fix it before moving tasks.",
                    "errors": error.errors,
                },
            ) from error
        return {"version": self.workspace.version()}

    def _read_json(self) -> JsonObject:
        if self.headers.get_content_type() != "application/json":
            raise ApiError(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "Send application/json.")
        length = int(self.headers.get("Content-Length") or 0)
        try:
            body: JsonValue = json.loads(self.rfile.read(length) or b"null")
        except ValueError as error:
            raise ApiError(HTTPStatus.BAD_REQUEST, "The body is not JSON.") from error
        if not isinstance(body, dict):
            raise ApiError(HTTPStatus.BAD_REQUEST, "The body must be an object.")
        return body

    def _host_allowed(self) -> bool:
        host = self.headers.get("Host") or ""
        if not host.endswith("]"):
            host = host.rsplit(":", 1)[0]
        if self.allowed_hosts is None or host in self.allowed_hosts:
            return True
        self._send_json(HTTPStatus.BAD_REQUEST, {"detail": "Invalid host header."})
        return False

    def _api(self, action: Callable[[], object]) -> None:
        if not self._host_allowed():
            return
        try:
            self._send_json(HTTPStatus.OK, action())
        except ApiError as error:
            self._send_json(error.status, {"detail": error.detail})

    def _send_json(self, status: HTTPStatus, body: object) -> None:
        data = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)


def _is_status(value: object) -> TypeGuard[TaskStatus]:
    return value in TASK_STATUSES


def _not_found(detail: str) -> ApiError:
    return ApiError(HTTPStatus.NOT_FOUND, detail)
