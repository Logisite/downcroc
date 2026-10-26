from __future__ import annotations

import http.client
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

from tests.conftest import Stack

ROOT = Path(__file__).resolve().parents[1]
PROTECTED_GETS = (
    "/api/status",
    "/api/vault",
    "/api/accounts",
    "/api/config",
    "/api/config/schema",
    "/api/providers",
    "/api/batches",
    "/api/jobs",
    "/api/failed",
    "/api/stats/summary",
    "/api/messages",
    "/api/threads",
    "/api/events",
    "/api/backups",
)


def _token(stack: Stack) -> str:
    path = stack.daemon.state_home / "downcroc" / "daemon.token"
    return path.read_text(encoding="ascii").strip()


def _request(
    stack: Stack,
    path: str,
    *,
    token: str | None = None,
    host: str | None = None,
    origin: str | None = None,
    method: str = "GET",
) -> tuple[int, bytes]:
    headers: dict[str, str] = {}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    if host is not None:
        headers["Host"] = host
    if origin is not None:
        headers["Origin"] = origin
    connection = http.client.HTTPConnection("127.0.0.1", stack.daemon.port, timeout=10)
    try:
        connection.request(method, path, headers=headers)
        response = connection.getresponse()
        return response.status, response.read()
    finally:
        connection.close()


def _cli(stack: Stack, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "downcroc", *args],
        cwd=ROOT,
        env=stack.daemon.environment(),
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )


def _json(stack: Stack, *args: str) -> dict:
    result = _cli(stack, *args)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_health_is_public_and_every_other_api_route_requires_a_token(
    stack_factory,
) -> None:
    stack = stack_factory()
    status, body = _request(stack, "/api/health")
    assert status == 200
    assert json.loads(body)["status"] == "ok"

    for path in PROTECTED_GETS:
        status, body = _request(stack, path)
        assert status == 401, path
        payload = json.loads(body)
        assert payload["error"] == "unauthorized"
        assert payload["status"] == 401


def test_malformed_and_wrong_tokens_are_rejected(stack_factory) -> None:
    stack = stack_factory()
    token = _token(stack)
    invalid = (
        "wrong",
        "Bearer",
        "Bearer ",
        "Bearer wrong",
        "Bearer a b",
        f"Basic {token}",
        f"bearer {token} extra",
    )
    for value in invalid:
        status, _ = _request(
            stack,
            "/api/status",
            token=None,
        )
        assert status == 401
        connection = http.client.HTTPConnection(
            "127.0.0.1", stack.daemon.port, timeout=10
        )
        try:
            connection.request(
                "GET",
                "/api/status",
                headers={"Authorization": value},
            )
            assert connection.getresponse().status == 401
        finally:
            connection.close()
    status, _ = _request(stack, "/api/status", token=token)
    assert status == 200


def test_host_and_origin_are_validated(stack_factory) -> None:
    stack = stack_factory()
    token = _token(stack)
    port = stack.daemon.port
    status, body = _request(stack, "/api/status", token=token, host="evil.example")
    assert status == 403
    assert json.loads(body)["error"] == "forbidden_host"

    for origin in ("http://evil.example", "null", f"https://127.0.0.1:{port}"):
        status, body = _request(
            stack,
            "/api/status",
            token=token,
            origin=origin,
        )
        assert status == 403, origin
        assert json.loads(body)["error"] == "forbidden_origin"

    for host, origin in (
        (f"127.0.0.1:{port}", None),
        (f"localhost:{port}", None),
        (f"127.0.0.1:{port}", f"http://127.0.0.1:{port}"),
        (f"localhost:{port}", f"http://localhost:{port}"),
    ):
        status, _ = _request(
            stack,
            "/api/status",
            token=token,
            host=host,
            origin=origin,
        )
        assert status == 200, (host, origin)


def test_token_rotates_on_restart_and_the_old_token_is_rejected(
    stack_factory,
) -> None:
    stack = stack_factory()
    first = _token(stack)
    stack.daemon.stop()
    stack.daemon.start(stack.fakes, preserve_config=True)
    second = _token(stack)
    assert second != first
    assert _request(stack, "/api/status", token=first)[0] == 401
    assert _request(stack, "/api/status", token=second)[0] == 200


def test_docs_are_disabled_and_openapi_still_exports(stack_factory) -> None:
    stack = stack_factory()
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert _request(stack, path)[0] == 404
    result = _cli(stack, "openapi")
    assert result.returncode == 0, result.stderr
    document = json.loads(result.stdout)
    assert "/api/status" in document["paths"]
    assert "/openapi.json" not in document["paths"]
    assert _token(stack) not in result.stdout


def test_auth_status_reports_presence_and_acceptance_without_the_secret(
    stack_factory,
) -> None:
    stack = stack_factory()
    token = _token(stack)
    report = _json(stack, "auth", "status", "--json")
    assert report["state"] == "running"
    assert report["token_present"] is True
    assert report["accepted"] is True
    assert token not in json.dumps(report)

    path = stack.daemon.state_home / "downcroc" / "daemon.token"
    path.unlink()
    missing = _json(stack, "auth", "status", "--json")
    assert missing["state"] == "running"
    assert missing["token_present"] is False
    assert missing["accepted"] is False
    assert token not in json.dumps(missing)


def test_token_file_is_readable_only_by_its_owner(stack_factory) -> None:
    stack = stack_factory()
    path = stack.daemon.state_home / "downcroc" / "daemon.token"
    if os.name != "nt":
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
        return
    completed = subprocess.run(
        ["icacls", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    output = completed.stdout.lower()
    assert "builtin\\users" not in output
    assert "everyone" not in output
    assert "(f)" in output
