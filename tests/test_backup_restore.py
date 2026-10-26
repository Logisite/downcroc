from __future__ import annotations

import io
import json
import sqlite3
import subprocess
import sys
import tarfile
from contextlib import closing
from pathlib import Path

import zstandard

from downcroc.runtime.fs import remove_tree
from tests.conftest import Stack
from tests.harness.campaigns import campaign_of, submit
from tests.harness.daemon import ROOT
from tests.harness.dispatch import dispatch_config
from tests.harness.logs import events
from tests.harness.replies import (
    account_address,
    deliver_reply,
    recipient_job,
    sync_and_wait,
)
from tests.harness.seed import until

TABLES = ("accounts", "batches", "jobs", "messages", "threads")


def _data(stack: Stack, root: Path | None = None) -> Path:
    base = root or (stack.daemon.data_home / "downcroc")
    return base / "downcroc.db"


def _counts(stack: Stack, root: Path | None = None) -> dict[str, int]:
    with closing(sqlite3.connect(_data(stack, root), timeout=10)) as connection:
        return {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in TABLES
        }


def _done(stack: Stack, batch_id: str, timeout: float = 60.0) -> None:
    until(
        lambda: stack.api.get(f"/api/batches/{batch_id}")["state"] == "done",
        timeout=timeout,
    )


def _populate(stack_factory) -> Stack:
    stack = stack_factory(
        accounts=["alice@local.test"],
        config_extra=dispatch_config(),
    )
    account = stack.accounts[0]
    to_address = account_address(stack, account)
    document = campaign_of(
        2,
        options={"approval": "auto"},
        routing={"mode": "fixed", "account": account},
    )
    batch = submit(stack, document, "backup-populate.json")
    _done(stack, batch["id"])
    job = recipient_job(batch, "person1@example.com")
    deliver_reply(
        stack.fakes,
        to_address=to_address,
        from_address="person1@example.com",
        subject="Re: Subject 1",
        message_id="reply-backup@example.com",
        in_reply_to=job["message_id"],
        references=(job["message_id"],),
    )
    sync_and_wait(stack, account, 1)
    return stack


def _backup(stack: Stack) -> tuple[Path, dict]:
    bundle = stack.root / "backup.dncbak"
    result = stack.api.post("/api/backups", {"path": str(bundle)})
    return bundle, result


def _cli(stack: Stack, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "downcroc", *args],
        cwd=ROOT,
        env=stack.daemon.environment(),
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def _plain(bundle: Path) -> bytes:
    with bundle.open("rb") as raw:
        reader = zstandard.ZstdDecompressor().stream_reader(raw)
        with reader:
            return reader.read()


def _rewrite(bundle: Path, name: str, payload: bytes) -> None:
    output = io.BytesIO()
    with tarfile.open(fileobj=io.BytesIO(_plain(bundle)), mode="r:") as source:
        members = []
        for member in source.getmembers():
            data = None
            if member.isfile():
                data = source.extractfile(member).read()
            if member.name == name:
                data = payload
                member.size = len(payload)
            members.append((member, data))
    with tarfile.open(fileobj=output, mode="w:") as archive:
        for member, data in members:
            if data is None:
                archive.addfile(member)
            else:
                member.size = len(data)
                archive.addfile(member, io.BytesIO(data))
    bundle.write_bytes(zstandard.ZstdCompressor().compress(output.getvalue()))


def _rewrite_manifest(bundle: Path, **changes: object) -> None:
    payload = _plain(bundle)
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:") as source:
        document = json.loads(source.extractfile("manifest.json").read())
    document.update(changes)
    encoded = (json.dumps(document, indent=2, sort_keys=True) + "\n").encode()
    _rewrite(bundle, "manifest.json", encoded)


def _assert_refused(result: subprocess.CompletedProcess[str], text: str) -> None:
    assert result.returncode == 1, result.stdout + result.stderr
    assert text in result.stdout + result.stderr


def test_backup_wipe_restore_preserves_counts_and_queue(stack_factory) -> None:
    stack = _populate(stack_factory)
    before = _counts(stack)
    assert before["jobs"] == 2
    assert before["messages"] == 1

    bundle, result = _backup(stack)
    assert result["files"] > 0
    assert result["bytes"] > 0
    assert result["counts"] == before
    assert bundle.is_file()
    found = events(stack)
    assert found["backup.created"]
    assert found["backup.verified"][-1]["ok"] is True

    cli_bundle = stack.root / "cli.dncbak"
    result = _cli(stack, "backup", str(cli_bundle))
    assert result.returncode == 0, result.stdout + result.stderr
    assert cli_bundle.is_file()
    result = _cli(stack, "restore", str(bundle))
    assert result.returncode == 1
    assert "stop it" in result.stderr

    stack.daemon.stop()
    remove_tree(stack.daemon.data_home / "downcroc")
    remove_tree(stack.daemon.config_home / "downcroc")
    result = _cli(stack, "restore", str(bundle))
    assert result.returncode == 0, result.stdout + result.stderr
    assert not list(stack.daemon.data_home.glob("downcroc.bak-*"))

    stack.daemon.start(stack.fakes, preserve_config=True)
    assert stack.api.get("/api/vault")["state"] == "locked"
    stack.api.unlock()
    assert _counts(stack) == before

    sent = len(stack.fakes.sent())
    document = campaign_of(
        1,
        key="after-restore",
        options={"approval": "auto"},
        routing={"mode": "fixed", "account": stack.accounts[0]},
    )
    batch = submit(stack, document, "backup-after-restore.json")
    _done(stack, batch["id"])
    assert len(stack.fakes.sent()) == sent + 1

    found = events(stack)
    assert found["restore.staged"]
    assert found["restore.swapped"]


def test_tampered_bundle_is_refused_before_extraction(stack_factory) -> None:
    stack = _populate(stack_factory)
    stack.daemon.stop()
    bundle = stack.root / "backup.dncbak"
    result = _cli(stack, "backup", str(bundle))
    assert result.returncode == 0, result.stdout + result.stderr
    before = _counts(stack)

    _rewrite(bundle, "vault.enc", b"tampered vault")
    result = _cli(stack, "restore", str(bundle))
    _assert_refused(result, "vault.enc")

    assert _counts(stack) == before
    assert not list(stack.daemon.data_home.glob("downcroc.bak-*"))
    found = events(stack)
    assert found["backup.verify_failed"]
    assert found["restore.refused"][-1]["reason"]


def test_unknown_schema_revision_is_refused(stack_factory) -> None:
    stack = _populate(stack_factory)
    bundle, _ = _backup(stack)
    stack.daemon.stop()
    before = _counts(stack)

    _rewrite_manifest(bundle, schema_revision="deadbeef")
    result = _cli(stack, "restore", str(bundle))
    _assert_refused(result, "deadbeef")

    assert _counts(stack) == before
    assert not list(stack.daemon.data_home.glob("downcroc.bak-*"))
    refused = events(stack)["restore.refused"][-1]
    assert refused["revision"] == "deadbeef"
    assert refused["current"] != "none"


def test_pending_restore_resumes_on_next_start(stack_factory) -> None:
    stack = _populate(stack_factory)
    before = _counts(stack)
    bundle, _ = _backup(stack)

    pending = stack.api.post("/api/restore", {"path": str(bundle)})
    assert pending["status"] == "pending"
    assert pending["restart_required"] is True
    assert stack.daemon.wait_stopped() is not None
    marker = stack.daemon.state_home / "downcroc" / "restore.pending"
    assert marker.is_file()

    stack.daemon.start(stack.fakes, preserve_config=True)
    assert not marker.exists()
    assert stack.api.get("/api/vault")["state"] == "locked"
    stack.api.unlock()
    assert _counts(stack) == before
    previous = list(stack.daemon.data_home.glob("downcroc.bak-*"))
    assert len(previous) == 1
    found = events(stack)
    assert found["restore.resumed"]
    assert found["restore.swapped"]
    assert found["restore.swapped"][-1]["previous"] == str(previous[0])
