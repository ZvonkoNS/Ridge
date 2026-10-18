"""Freeze the GUI sidecar with PyInstaller (one folder) and smoke-test it over stdio.

    python -m pip install --require-hashes --no-deps -r requirements-build.lock
    python tools/build_sidecar.py            # -> build/sidecar/ridge-sidecar/ridge-sidecar[.exe]

The release bundle ships this folder as ``resources/sidecar/`` (architecture §10;
``gui/src-tauri/tauri.release.conf.json``). The build is checked before it is accepted: the
frozen sidecar must answer ``ridge.version`` with the protocol the GUI speaks and must list an
empty synthetic store, over the same newline-delimited JSON-RPC the GUI uses. Code signing of
the result is a release step outside this script (release_readiness_checklist.md).
"""

from __future__ import annotations

import json
import shutil
import subprocess  # nosec B404 - fixed tool invocations, no shell
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build"
DIST = BUILD / "sidecar"
NAME = "ridge-sidecar"
PROTOCOL = "ridge.sidecar/1"
ENTRY = "from ridge.sidecar.server import main\n\nraise SystemExit(main())\n"
# The OS keystore backend is chosen at run time; it must be in the bundle (a missing one would
# leave keyring's "fail" backend, and every unlock would be refused).
KEYSTORE_BACKEND = {"win32": "keyring.backends.Windows", "darwin": "keyring.backends.macOS"}.get(
    sys.platform, "keyring.backends.SecretService"
)


def freeze() -> Path:
    """Run PyInstaller and return the frozen executable."""
    work = BUILD / "pyinstaller"
    work.mkdir(parents=True, exist_ok=True)
    entry = work / "ridge_sidecar_entry.py"
    entry.write_text(ENTRY, encoding="utf-8")
    shutil.rmtree(DIST / NAME, ignore_errors=True)
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onedir",
        "--console",  # stdio is the transport; the GUI starts it without a window
        "--name",
        NAME,
        "--distpath",
        str(DIST),
        "--workpath",
        str(work),
        "--specpath",
        str(work),
        "--collect-submodules",
        "keyring.backends",  # backends are found through entry points at run time
        "--copy-metadata",
        "keyring",
        "--copy-metadata",
        "ridge",
        str(entry),
    ]
    print("$", " ".join(command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True)  # nosec B603
    exe = DIST / NAME / (NAME + (".exe" if sys.platform == "win32" else ""))
    if not exe.is_file():
        raise SystemExit(f"PyInstaller did not produce {exe}")
    return exe


def check_bundle() -> None:
    """Check that this platform's keystore backend and the sidecar methods are in the frozen archive."""
    # build tool only: untyped, and installed from requirements-build.lock, not in development or CI
    from PyInstaller.archive.readers import (  # type: ignore[import-untyped,import-not-found,unused-ignore]  # noqa: PLC0415
        ZlibArchiveReader,
    )

    names = set(ZlibArchiveReader(str(BUILD / "pyinstaller" / NAME / "PYZ-00.pyz")).toc)
    missing = {KEYSTORE_BACKEND, "ridge.sidecar.handlers", "ridge.case.limits"} - names
    if missing:
        raise SystemExit(f"frozen sidecar lacks {sorted(missing)}")
    print(f"frozen archive ok: {len(names)} modules, keystore backend {KEYSTORE_BACKEND}")


def smoke(exe: Path) -> None:
    """Talk JSON-RPC to the frozen sidecar the way the GUI does; raise on any mismatch."""
    with tempfile.TemporaryDirectory() as tmp:
        store = Path(tmp) / "store"
        store.mkdir()
        requests = [
            {"jsonrpc": "2.0", "id": 1, "method": "ridge.version"},
            {"jsonrpc": "2.0", "id": 2, "method": "store.identity", "params": {"store": str(store)}},
            {"jsonrpc": "2.0", "id": 3, "method": "store.cases", "params": {"store": str(store)}},
        ]
        stdin = "".join(json.dumps(r) + "\n" for r in requests)
        done = subprocess.run([str(exe)], input=stdin.encode(), capture_output=True, timeout=120, check=False)  # nosec B603
    replies = [json.loads(line) for line in done.stdout.decode("utf-8").splitlines()]
    expected = [{"protocol": PROTOCOL}, {"exists": False}, []]
    results = [r.get("result") for r in replies]
    if done.returncode != 0 or len(results) != 3:
        tail = done.stderr.decode(errors="replace")[-2000:]
        raise SystemExit(f"frozen sidecar failed (exit {done.returncode}): {tail}")
    if results[0].get("protocol") != PROTOCOL or results[1:] != expected[1:]:
        raise SystemExit(f"frozen sidecar answered unexpectedly: {results}")
    print(f"frozen sidecar ok: Ridge {results[0].get('ridge')}, protocol {PROTOCOL}")


def main() -> int:
    """Freeze, then smoke-test."""
    exe = freeze()
    check_bundle()
    smoke(exe)
    print(f"sidecar folder: {exe.parent}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
