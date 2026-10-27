from __future__ import annotations

import http.client
import json
import tarfile
from pathlib import Path

import zstandard

from tests.conftest import Stack


def _token(stack: Stack) -> str:
    path = stack.daemon.state_home / "downcroc" / "daemon.token"
    return path.read_text(encoding="ascii").strip()


def _request(stack: Stack, path: str, token: str | None) -> tuple[int, bytes]:
    headers = {} if token is None else {"Authorization": f"Bearer {token}"}
    connection = http.client.HTTPConnection("127.0.0.1", stack.daemon.port, timeout=10)
    try:
        connection.request("GET", path, headers=headers)
        response = connection.getresponse()
        return response.status, response.read()
    finally:
        connection.close()


def _scan(root: Path, secrets: tuple[str, ...], excluded: Path) -> None:
    for path in root.rglob("*"):
        if not path.is_file() or path == excluded or path.name == "daemon.lock":
            continue
        data = path.read_bytes()
        for secret in secrets:
            assert secret.encode() not in data, path


def _bundle_text(bundle: Path, secrets: tuple[str, ...]) -> None:
    with (
        bundle.open("rb") as raw,
        zstandard.ZstdDecompressor().stream_reader(raw) as reader,
        tarfile.open(fileobj=reader, mode="r|") as archive,
    ):
        for member in archive:
            for secret in secrets:
                assert secret not in member.name
            if not member.isfile():
                continue
            extracted = archive.extractfile(member)
            payload = b"" if extracted is None else extracted.read()
            for secret in secrets:
                assert secret.encode() not in payload, member.name


def test_token_never_reaches_logs_errors_or_backups(
    stack_factory,
    tmp_path: Path,
) -> None:
    stack = stack_factory()
    token = _token(stack)
    status, body = _request(stack, "/api/status", token=None)
    assert status == 401
    assert token.encode() not in body
    assert b"authorization" not in body.lower()
    status, body = _request(stack, "/api/status", token=token)
    assert status == 200

    token_path = stack.daemon.state_home / "downcroc" / "daemon.token"
    _scan(stack.daemon.root, (token,), token_path)
    logs = stack.daemon.data_home / "downcroc" / "logs" / "downcroc.jsonl"
    text = logs.read_text(encoding="utf-8")
    assert token not in text
    assert "authorization" not in text.lower()

    bundle = tmp_path / "leak-check.tar.zst"
    created = stack.api.post(
        "/api/backups",
        {"path": str(bundle), "include_logs": True},
    )
    assert created["path"] == str(bundle)
    _bundle_text(bundle, (token,))
    assert token not in json.dumps(created)
