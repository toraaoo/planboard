import json
import threading
from collections.abc import Iterator
from http.client import HTTPConnection
from typing import Any

import pytest

from planboard.adapters.web.server import LOOPBACK_HOSTS, serving
from planboard.application.workspace import Workspace
from tests.support import WritePlan


@pytest.fixture
def connection(workspace: Workspace) -> Iterator[HTTPConnection]:
    with serving(workspace, "127.0.0.1", 0, LOOPBACK_HOSTS) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        yield HTTPConnection("127.0.0.1", server.server_address[1])
        server.shutdown()


def request(
    connection: HTTPConnection,
    method: str,
    path: str,
    body: object = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, Any]:
    data = None if body is None else json.dumps(body)
    sent = {"Content-Type": "application/json", **(headers or {})}
    connection.request(method, path, body=data, headers=sent)
    response = connection.getresponse()
    return response.status, json.loads(response.read() or b"null")


def test_serves_a_plan_with_its_diagrams_resolved(
    connection: HTTPConnection, write_plan: WritePlan
) -> None:
    write_plan("area/example")

    status, body = request(connection, "GET", "/api/plans/area/example")

    block = body["plan"]["sections"][0]["blocks"][0]
    assert status == 200
    assert body["path"] == "area/example/"
    assert "diagrams" not in body["plan"]
    assert block["diagram"]["source"] == "flowchart LR\n  a --> b"
    assert block["diagram"]["alt"] == "A flow."


def test_answers_404_for_an_unknown_plan(connection: HTTPConnection) -> None:
    status, _ = request(connection, "GET", "/api/plans/area/missing")

    assert status == 404


def test_moves_a_task(connection: HTTPConnection, write_plan: WritePlan) -> None:
    write_plan("area/example", tasks=[{"id": "first", "title": "First"}])

    path = "/api/plans/area/example/tasks/first"
    status, _ = request(connection, "PATCH", path, {"status": "doing"})
    _, body = request(connection, "GET", "/api/plans/area/example")

    assert status == 200
    assert body["plan"]["tasks"][0]["status"] == "doing"


def test_rejects_an_unknown_status(
    connection: HTTPConnection, write_plan: WritePlan
) -> None:
    write_plan("area/example", tasks=[{"id": "first", "title": "First"}])

    path = "/api/plans/area/example/tasks/first"
    status, _ = request(connection, "PATCH", path, {"status": "later"})

    assert status == 422


def test_answers_404_for_an_unknown_task(
    connection: HTTPConnection, write_plan: WritePlan
) -> None:
    write_plan("area/example", tasks=[{"id": "first", "title": "First"}])

    path = "/api/plans/area/example/tasks/missing"
    status, _ = request(connection, "PATCH", path, {"status": "done"})

    assert status == 404


def test_rejects_a_foreign_host_header(connection: HTTPConnection) -> None:
    status, _ = request(
        connection, "GET", "/api/plans", headers={"Host": "attacker.example"}
    )

    assert status == 400
