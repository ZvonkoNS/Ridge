"""GUI sidecar: JSON-RPC 2.0 over stdio, strict validation, full case workflow (M4 backend)."""

from __future__ import annotations

import base64
import io
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from PIL import Image

from ridge.case.identity import create_identity
from ridge.case.processing_record import check_exported_log
from ridge.case.reports import check_exported_report
from ridge.sidecar import handlers
from ridge.sidecar.handlers import Session
from ridge.sidecar.protocol import (
    APPLICATION_ERROR,
    INTERNAL_ERROR,
    INVALID_PARAMS,
    INVALID_REQUEST,
    MAX_MESSAGE_BYTES,
    METHOD_NOT_FOUND,
    PARSE_ERROR,
)
from ridge.sidecar.server import handle, main, serve
from tests.case_helpers import FAST_KDF, PASSPHRASE, MemoryKeyStore, future, new_case, photo_file


def call(session: Session, method: str, params: dict[str, Any] | None = None, request_id: int = 1) -> dict[str, Any]:
    message = {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": method,
        **({"params": params} if params is not None else {}),
    }
    reply: dict[str, Any] = json.loads(handle(json.dumps(message).encode(), session))
    assert reply["id"] == request_id
    return reply


def error_code(reply: dict[str, Any]) -> int:
    assert "error" in reply, reply
    return int(reply["error"]["code"])


@pytest.fixture
def keystore() -> MemoryKeyStore:
    return MemoryKeyStore()


@pytest.fixture
def case_dir(tmp_path: Path, keystore: MemoryKeyStore) -> Path:
    store = tmp_path / "store"
    create_identity(store, PASSPHRASE, keystore, FAST_KDF)
    return new_case(store, keystore)


@pytest.fixture
def session(keystore: MemoryKeyStore) -> Session:
    return Session(keystore_factory=lambda: keystore)


# ---------------------------------------------------------------- protocol


@pytest.mark.parametrize(
    ("raw", "code"),
    [
        (b"not json", PARSE_ERROR),
        (b"\xff\xfe", PARSE_ERROR),
        (b'{"jsonrpc":"2.0","id":1,"id":2,"method":"ridge.version"}', PARSE_ERROR),  # duplicate key
        (b'{"jsonrpc":"2.0","id":1,"method":"ridge.version","params":{"x":NaN}}', PARSE_ERROR),
        (b"[1, 2]", INVALID_REQUEST),  # batches are not supported
        (b'{"jsonrpc":"1.0","id":1,"method":"ridge.version"}', INVALID_REQUEST),
        (b'{"jsonrpc":"2.0","id":true,"method":"ridge.version"}', INVALID_REQUEST),
        (b'{"jsonrpc":"2.0","method":"ridge.version"}', INVALID_REQUEST),  # notifications are not supported
        (b'{"jsonrpc":"2.0","id":1,"method":"ridge.version","extra":1}', INVALID_REQUEST),
        (b'{"jsonrpc":"2.0","id":1,"method":"os.system"}', METHOD_NOT_FOUND),
        (b'{"jsonrpc":"2.0","id":1,"method":"case.items","params":[1]}', INVALID_PARAMS),
        (b'{"jsonrpc":"2.0","id":1,"method":"case.import","params":{}}', INVALID_PARAMS),
        (b'{"jsonrpc":"2.0","id":1,"method":"case.import","params":{"path":"a","x":1}}', INVALID_PARAMS),
        (b'{"jsonrpc":"2.0","id":1,"method":"preview.get","params":{"sha256":"a","max_side":true}}', INVALID_PARAMS),
    ],
)
def test_malformed_requests_are_refused(session: Session, raw: bytes, code: int) -> None:
    assert error_code(json.loads(handle(raw, session))) == code


def test_errors_echo_a_known_request_id(session: Session) -> None:
    reply = json.loads(handle(b'{"jsonrpc":"2.0","id":"r7","method":"nope"}', session))
    assert reply["id"] == "r7"


def test_version(session: Session) -> None:
    assert call(session, "ridge.version")["result"]["protocol"] == "ridge.sidecar/1"


def test_case_methods_need_an_unlocked_case(session: Session) -> None:
    reply = call(session, "case.items")
    assert error_code(reply) == APPLICATION_ERROR
    assert "no case is unlocked" in reply["error"]["message"]


@pytest.mark.parametrize(
    "params",
    [
        {"store": "relative/store", "case_id": "00000000-0000-0000-0000-000000000000", "passphrase": PASSPHRASE},
        {
            "store": "C:/store" if sys.platform == "win32" else "/store",
            "case_id": "../escape",
            "passphrase": PASSPHRASE,
        },
    ],
)
def test_unlock_rejects_unsafe_paths(session: Session, params: dict[str, Any]) -> None:
    assert error_code(call(session, "session.unlock", params)) == APPLICATION_ERROR


def test_wrong_passphrase(session: Session, case_dir: Path) -> None:
    params = {"store": str(case_dir.parent), "case_id": case_dir.name, "passphrase": "not the right passphrase"}
    reply = call(session, "session.unlock", params)
    assert "wrong passphrase" in reply["error"]["message"]


# ---------------------------------------------------------------- workflow


def test_full_workflow(session: Session, case_dir: Path, tmp_path: Path) -> None:
    unlocked = call(
        session, "session.unlock", {"store": str(case_dir.parent), "case_id": case_dir.name, "passphrase": PASSPHRASE}
    )
    assert unlocked["result"]["reference"] == "KT-2026-0001"
    photo = photo_file(tmp_path / "in")
    evidence = call(session, "case.import", {"path": str(photo.resolve())})["result"]
    assert evidence["role"] == "evidence"

    job = call(session, "job.run", {"evidence": evidence["sha256"], "minutiae": True, "ruler": [0, 0, 200, 0, 10]})[
        "result"
    ]
    assert job["export"]["scale"]["method"] == "ruler"
    roles = {o["role"] for o in job["outputs"]}
    assert roles == {"print", "export", "minutiae"}

    print_sha = next(o["sha256"] for o in job["outputs"] if o["role"] == "print")
    shown = call(session, "preview.get", {"sha256": print_sha, "max_side": 128})["result"]
    assert max(shown["width"], shown["height"]) <= 128
    assert base64.b64decode(shown["png_base64"]).startswith(b"\x89PNG")
    minutiae_sha = next(o["sha256"] for o in job["outputs"] if o["role"] == "minutiae")
    assert error_code(call(session, "preview.get", {"sha256": minutiae_sha})) == APPLICATION_ERROR
    assert error_code(call(session, "preview.get", {"sha256": print_sha, "max_side": 99999})) == APPLICATION_ERROR

    dest = tmp_path / "out.png"
    assert call(session, "case.export", {"sha256": print_sha, "dest": str(dest.resolve())})["result"]["exported"]
    assert dest.is_file()
    assert error_code(call(session, "case.export", {"sha256": print_sha, "dest": "relative.png"})) == APPLICATION_ERROR

    assert call(session, "case.verify")["result"]["ok"] is True
    assert len(call(session, "case.items")["result"]) == 4

    (listed,) = call(session, "case.jobs")["result"]
    assert (listed["job_id"], listed["result"]) == (job["job_id"], "ok")
    shown_report = call(session, "report.get", {"job_id": job["job_id"][:8]})["result"]
    assert shown_report["verified"] is True
    assert shown_report["report"]["export"]["scale"]["method"] == "ruler"
    assert error_code(call(session, "report.get", {"job_id": "../../x"})) == APPLICATION_ERROR
    again = call(session, "job.reproduce", {"job_id": job["job_id"]})["result"]
    assert (again["identical"], again["original_job"]) == (True, job["job_id"])
    report_dest = (tmp_path / "report.json").resolve()
    saved = call(session, "report.export", {"job_id": job["job_id"], "dest": str(report_dest)})["result"]
    assert saved["signature"] == f"{report_dest}.sig"
    assert check_exported_report(report_dest, expected_key_id=saved["key_id"]).job_id == job["job_id"]
    assert error_code(call(session, "report.export", {"job_id": job["job_id"], "dest": "r.json"})) == APPLICATION_ERROR
    candidate = tmp_path / "candidate.png"
    Image.fromarray(np.full((100, 80), 128, np.uint8)).save(candidate, dpi=(500, 500))
    reference = call(session, "case.import_reference", {"path": str(candidate.resolve()), "source": "NAFIS 1"})
    assert (reference["result"]["role"], reference["result"]["source"]) == ("reference", "NAFIS 1")
    export_sha = next(o["sha256"] for o in job["outputs"] if o["role"] == "export")
    sheet_dest = str((tmp_path / "sheet.png").resolve())
    params = {"export": export_sha, "reference": reference["result"]["sha256"], "dest": sheet_dest}
    assert call(session, "compare.export", params)["result"]["reference_ppi_source"] == "file"
    assert error_code(call(session, "compare.export", params)) == APPLICATION_ERROR  # no silent overwrite
    record = (tmp_path / "record.json").resolve()
    logged = call(session, "log.export", {"dest": str(record)})["result"]
    assert check_exported_log(record, expected_key_id=logged["key_id"]).entries == logged["entries"]
    assert call(session, "session.lock")["result"] == {"locked": True}
    assert not (case_dir / "LOCK").exists()


def test_serve_handles_a_stream_and_oversized_lines(session: Session, case_dir: Path) -> None:
    lines = [
        b"x" * (MAX_MESSAGE_BYTES + 10) + b"\n",  # oversized: refused, the stream stays in sync
        b"\n",  # blank lines are ignored
        json.dumps({"jsonrpc": "2.0", "id": 2, "method": "ridge.version"}).encode() + b"\n",
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "session.unlock",
                "params": {"store": str(case_dir.parent), "case_id": case_dir.name, "passphrase": PASSPHRASE},
            }
        ).encode()
        + b"\n",
    ]
    stdout = io.BytesIO()
    assert serve(io.BytesIO(b"".join(lines)), stdout, session) == 0
    replies = [json.loads(line) for line in stdout.getvalue().splitlines()]
    assert [r.get("id") for r in replies] == [None, 2, 3]
    assert replies[0]["error"]["code"] in (INVALID_REQUEST, PARSE_ERROR)
    assert not (case_dir / "LOCK").exists()  # end of input locks the case


def test_internal_errors_are_answered_safely(session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(session: Session, params: dict[str, Any]) -> None:
        raise RuntimeError("secret detail")

    monkeypatch.setitem(handlers.METHODS, "ridge.version", (broken, {}))
    reply = call(session, "ridge.version")
    assert error_code(reply) == INTERNAL_ERROR
    assert "secret detail" not in reply["error"]["message"]


def test_main_uses_binary_stdio(monkeypatch: pytest.MonkeyPatch) -> None:
    request = json.dumps({"jsonrpc": "2.0", "id": 9, "method": "ridge.version"}).encode() + b"\n"
    stdin, stdout = io.TextIOWrapper(io.BytesIO(request)), io.TextIOWrapper(io.BytesIO())
    monkeypatch.setattr(sys, "stdin", stdin)
    monkeypatch.setattr(sys, "stdout", stdout)
    assert main() == 0
    stdout.flush()
    assert json.loads(stdout.buffer.getvalue())["id"] == 9


def test_idle_session_locks_itself(keystore: MemoryKeyStore, case_dir: Path) -> None:
    now = [1000.0]
    session = Session(keystore_factory=lambda: keystore, idle_timeout_s=60.0, clock=lambda: now[0])
    unlock = {"store": str(case_dir.parent), "case_id": case_dir.name, "passphrase": PASSPHRASE}
    assert "result" in call(session, "session.unlock", unlock)
    now[0] += 30
    assert call(session, "session.status")["result"]["unlocked"] is True  # activity resets the timer
    now[0] += 59
    assert "result" in call(session, "case.items")
    now[0] += 61
    reply = call(session, "case.items")
    assert "no case is unlocked" in reply["error"]["message"]
    assert not (case_dir / "LOCK").exists()  # the case lock was released


def test_first_run_creates_identity_and_case(keystore: MemoryKeyStore, tmp_path: Path) -> None:
    session = Session(keystore_factory=lambda: keystore, kdf_params=FAST_KDF)
    store = str((tmp_path / "new-store").resolve())
    identity = call(session, "identity.create", {"store": store, "passphrase": PASSPHRASE})["result"]
    assert len(identity["key_id"]) == 16
    params = {
        "store": store,
        "reference": "KT-2026-9",
        "legal_basis": "synthetic",
        "retention_until": future().isoformat(),
        "passphrase": PASSPHRASE,
    }
    case_id = call(session, "case.create", params)["result"]["case_id"]
    unlocked = call(session, "session.unlock", {"store": store, "case_id": case_id, "passphrase": PASSPHRASE})
    assert unlocked["result"]["reference"] == "KT-2026-9"
    for bad in ({"retention_until": "next year"}, {"store": "relative"}, {"passphrase": "wrong passphrase 123"}):
        assert error_code(call(session, "case.create", params | bad)) == APPLICATION_ERROR
    assert error_code(call(session, "identity.create", {"store": store, "passphrase": PASSPHRASE})) == APPLICATION_ERROR


def test_unreadable_metadata_leaves_nothing_unlocked(session: Session, case_dir: Path) -> None:
    meta = case_dir / "meta.enc"
    meta.write_bytes(meta.read_bytes()[:-1] + bytes([meta.read_bytes()[-1] ^ 1]))
    params = {"store": str(case_dir.parent), "case_id": case_dir.name, "passphrase": PASSPHRASE}
    assert error_code(call(session, "session.unlock", params)) == APPLICATION_ERROR
    assert call(session, "session.status")["result"]["unlocked"] is False
    assert not (case_dir / "LOCK").exists()  # the case lock was released
