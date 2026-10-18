"""Workstation check: read-only, names what to fix, never shows the device secret."""

from __future__ import annotations

import json
import os
import platform
import sys
import uuid
from pathlib import Path
from typing import Any

import pytest

from ridge.case import cli_common, workstation
from ridge.case.cli import main
from ridge.case.identity import create_identity, public_identity
from ridge.case.jobs import environment
from ridge.case.key_register import SCHEMA as REGISTER_SCHEMA
from ridge.case.keys import DEVICE_SECRET_NAME, b64
from ridge.case.limits import FILE
from ridge.case.limits import SCHEMA as LIMITS_SCHEMA
from ridge.case.workstation import Finding, check_workstation
from ridge.sidecar.handlers import Session
from ridge.sidecar.server import handle
from tests.case_helpers import FAST_KDF, PASSPHRASE, MemoryKeyStore, new_case


def levels(found: list[Finding]) -> dict[str, list[str]]:
    by_topic: dict[str, list[str]] = {}
    for f in found:
        by_topic.setdefault(f.topic, []).append(f.level)
    return by_topic


def snapshot(root: Path) -> dict[str, bytes]:
    return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def test_a_new_store_has_notes_but_no_problems(tmp_path: Path) -> None:
    root = tmp_path / "store"
    root.mkdir()
    keystore = MemoryKeyStore()
    found = levels(check_workstation(root, keystore))
    assert found["OS keystore"] == ["note"]  # created with the identity, not by the check
    assert found["Identity"] == ["note"]
    assert found["Store"] == ["ok"]
    assert found["Limits of use"] == ["note"]
    assert keystore.values == {}  # nothing was created


def test_a_working_store_is_ok_and_nothing_is_written(tmp_path: Path) -> None:
    root = tmp_path / "store"
    keystore = MemoryKeyStore()
    create_identity(root, PASSPHRASE, keystore, FAST_KDF)
    new_case(root, keystore)
    before = snapshot(root)
    found = check_workstation(root, keystore)
    assert snapshot(root) == before
    by_topic = {f.topic: f for f in found}
    assert by_topic["Identity"].text == f"examiner signing key {public_identity(root)[0]}"
    assert "1 active" in by_topic["Store"].text
    assert "not shown" in by_topic["OS keystore"].text
    secret = keystore.values[DEVICE_SECRET_NAME]
    assert all(secret.hex() not in f.text and b64(secret) not in f.text for f in found)
    assert {f.level for f in found if f.topic != "Limits of use"} == {"ok"}


@pytest.mark.parametrize(("secret", "words"), [(None, "cannot be opened here"), (b"short", "malformed")])
def test_a_missing_or_malformed_device_secret_is_a_problem(tmp_path: Path, secret: bytes | None, words: str) -> None:
    root = tmp_path / "store"
    keystore = MemoryKeyStore()
    create_identity(root, PASSPHRASE, keystore, FAST_KDF)
    if secret is None:
        keystore.values.clear()
    else:
        keystore.values[DEVICE_SECRET_NAME] = secret
    (finding,) = [f for f in check_workstation(root, keystore) if f.topic == "OS keystore"]
    assert finding.level == "problem"
    assert words in finding.text


class BrokenKeyStore(MemoryKeyStore):
    def get(self, name: str) -> bytes | None:
        raise OSError("no keyring back end")


def test_an_unreadable_keystore_or_store_is_reported_not_raised(tmp_path: Path) -> None:
    by_topic = {f.topic: f for f in check_workstation(tmp_path / "missing", BrokenKeyStore())}
    assert by_topic["OS keystore"].level == "problem"
    assert "OSError" in by_topic["OS keystore"].text
    assert by_topic["Store"].level == "problem"


def test_limits_name_the_architecture_and_the_nfiq2_minimum(tmp_path: Path) -> None:
    root = tmp_path / "store"
    root.mkdir()
    limits: dict[str, Any] = {
        "schema": LIMITS_SCHEMA,
        "source": "VR-2027-01",
        "architectures": ["no-such-cpu"],
        "min_nfiq2": 30,
    }

    def check() -> list[Finding]:
        return [f for f in check_workstation(root, MemoryKeyStore()) if f.topic == "Limits of use"]

    (root / FILE).write_text(json.dumps(limits), encoding="utf-8")
    found = check()
    assert [f.level for f in found] == ["note", "problem", "note"]  # unsigned, wrong CPU, NFIQ 2 minimum
    assert "VR-2027-01, not signed" in found[0].text
    assert platform.machine() in found[1].text
    limits["architectures"] = [platform.machine()]
    (root / FILE).write_text(json.dumps(limits), encoding="utf-8")
    assert [f.level for f in check()] == ["note", "note"]
    (root / FILE).write_text("{", encoding="utf-8")
    assert [f.level for f in check()] == ["problem"]


def test_the_register_the_cli_and_the_sidecar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "store"
    keystore = MemoryKeyStore()
    create_identity(root, PASSPHRASE, keystore, FAST_KDF)
    key_id, public = public_identity(root)
    entry = {"key_id": key_id, "public_key": b64(public), "holder": "Examiner A", "role": "examiner"}
    register = tmp_path / "register.json"
    doc = {"schema": REGISTER_SCHEMA, "laboratory": "Synthetic Lab", "keys": [entry]}
    register.write_text(json.dumps(doc), encoding="utf-8")
    (ok,) = [f for f in check_workstation(root, keystore, register) if f.topic == "Key register"]
    assert ok.level == "ok"
    assert "Examiner A" in ok.text
    monkeypatch.setattr(cli_common, "KEYSTORE_FACTORY", lambda: keystore)
    assert main(["workstation", "--store", str(root), "--register", str(register)]) == 0
    out = capsys.readouterr().out
    assert "OK       Key register: registered to Examiner A" in out
    assert "it does not validate the method" in out
    empty = tmp_path / "empty.json"
    empty.write_text(json.dumps({**doc, "keys": []}), encoding="utf-8")
    assert main(["workstation", "--store", str(root), "--register", str(empty), "--json"]) == 1
    shown = json.loads(capsys.readouterr().out)
    assert (shown[-1]["topic"], shown[-1]["level"]) == ("Key register", "problem")
    session = Session(keystore_factory=lambda: keystore)

    def rpc(params: dict[str, Any]) -> dict[str, Any]:
        message = {"jsonrpc": "2.0", "id": 1, "method": "store.workstation", "params": params}
        reply: dict[str, Any] = json.loads(handle(json.dumps(message).encode(), session))
        return reply

    result = rpc({"store": str(root.resolve())})["result"]
    assert [f["topic"] for f in result][:3] == ["Ridge", "Platform", "Libraries"]
    assert rpc({"store": "relative/path"})["error"]["code"] == -32000  # refused: not an absolute path
    assert rpc({"store": 5})["error"]["code"] == -32602


def test_unknown_commit_other_cpu_bad_identity_and_store_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    real = environment()
    monkeypatch.setattr(
        workstation,
        "environment",
        lambda: {**real, "commit": "unknown", "commit_source": "unknown", "machine": "riscv64"},
    )
    root = tmp_path / "store"
    root.mkdir()
    (root / "identity.json").write_text("{", encoding="utf-8")
    (root / str(uuid.uuid4())).mkdir()  # a case folder with nothing in it
    by_topic = {f.topic: f for f in check_workstation(root, MemoryKeyStore())}
    assert (by_topic["Ridge"].level, "commit is unknown" in by_topic["Ridge"].text) == ("note", True)
    assert (by_topic["Platform"].level, "no reference results" in by_topic["Platform"].text) == ("note", True)
    assert by_topic["Identity"].level == "problem"
    assert (by_topic["Store"].level, "1 invalid" in by_topic["Store"].text) == ("problem", True)
    monkeypatch.setattr(os, "access", lambda path, mode: False)
    store = {f.topic: f for f in check_workstation(root, MemoryKeyStore())}["Store"]
    assert (store.level, "cannot be written" in store.text) == ("problem", True)


def fake_tool(folder: Path, version_code: int, version: str = "NFIQ2 Version: 2.3.0") -> list[str]:
    """A stand-in NFIQ 2 that answers --version (synthetic: it never sees an image)."""
    script = folder / "fake_nfiq2.py"
    lines = ["import sys", f"print({version!r})", f"sys.exit({version_code})"]
    script.write_text("\n".join(lines), encoding="utf-8")
    return [sys.executable, str(script)]


def test_the_nfiq2_tool_is_found_and_reports_its_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "store"
    root.mkdir()

    def nfiq2(command: list[str]) -> Finding:
        (found,) = [f for f in check_workstation(root, MemoryKeyStore(), nfiq2=command) if f.topic == "NFIQ 2"]
        return found

    working = nfiq2(fake_tool(tmp_path, 0))
    assert working.level == "ok"
    assert "NFIQ2 Version: 2.3.0" in working.text
    assert "indicative only" in working.text
    assert nfiq2(fake_tool(tmp_path, 0, version="")).level == "note"  # ran cleanly, printed no version
    assert nfiq2(fake_tool(tmp_path, 1)).level == "problem"  # failed when asked for its version
    not_a_program = tmp_path / "nfiq2.txt"
    not_a_program.write_text("not a program", encoding="utf-8")
    broken = nfiq2([str(not_a_program)])  # there, but cannot be started
    assert broken.level == "problem"
    assert "jobs cannot compute NFIQ 2 scores" in broken.text
    assert nfiq2([str(tmp_path / "missing.exe")]).level == "problem"
    assert nfiq2(["nfiq2"]).level == "problem"  # not an absolute path: never searched on PATH
    monkeypatch.setattr(cli_common, "KEYSTORE_FACTORY", MemoryKeyStore)
    command = fake_tool(tmp_path, 0)
    args = ["workstation", "--store", str(root), "--nfiq2", command[0], "--nfiq2-arg", command[1]]
    assert main(args) == 0
    assert "OK       NFIQ 2: NFIQ2 Version: 2.3.0" in capsys.readouterr().out
