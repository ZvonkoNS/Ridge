"""Freeze the GUI sidecar with PyInstaller (one folder) and smoke-test it over stdio.

    python -m pip install --require-hashes --no-deps -r requirements-build.lock
    python tools/build_sidecar.py            # -> build/sidecar/ridge-sidecar/ridge-sidecar[.exe]

The release bundle ships this folder as ``resources/sidecar/`` (architecture §10;
``gui/src-tauri/tauri.release.conf.json``). The build is checked before it is accepted: the
archive must hold the keystore backend and the image decoders, the folder their native
libraries, and the frozen sidecar must answer ``ridge.version`` with the protocol the GUI speaks,
list an empty synthetic store and report in its workstation check that it reads HEIF/HEIC, over
the same newline-delimited JSON-RPC the GUI uses. Code signing of the result is a release step
outside this script (release_readiness_checklist.md).
"""

from __future__ import annotations

import fnmatch
import json
import os
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
# Pillow finds its format plugins by name when a file is opened, so a frozen build without one
# would refuse that format as unsupported at run time. One plugin per allow-listed format
# (ridge.image_io.ALLOWED_FORMATS), the HEIF opener and the XMP parser (FR-36).
DECODERS = frozenset(
    {
        "PIL.JpegImagePlugin",
        "PIL.PngImagePlugin",
        "PIL.TiffImagePlugin",
        "PIL.BmpImagePlugin",
        "PIL.WebPImagePlugin",
        "pillow_heif",
        "defusedxml.ElementTree",
    }
)
# The decoders' native parts, as file-name patterns for any platform: Pillow's core and WebP
# extensions, pillow-heif's extension and libheif. The archive can hold the Python modules without
# them; ridge.image_io would then drop HEIF from its allow-list without an error, so the smoke test
# also asks the frozen engine itself whether it reads HEIF.
NATIVE = (
    "_imaging.*",
    "_webp.*",
    "_pillow_heif.*",
    "libheif*",
    "_imagingft.*",
)  # _imagingft: FreeType for the annotated image's mark numbers
HEIF_READABLE = "HEIF/HEIC photos can be read"  # the workstation check's wording (ridge.case.workstation)
# Modules of the 2026-10-24 follow-up that the GUI reaches through the sidecar: the capture check (FR-54) and the
# examiner annotations with their drawn export (FR-55), which needs Pillow's drawing and font modules.
FEATURES = frozenset(
    {"ridge.capture", "ridge.case.annotations", "ridge.case.annotation_image", "PIL.ImageDraw", "PIL.ImageFont"}
)


def stamp(work: Path) -> Path:
    """Write ridge/_build.json with the commit being built (PRD FR-34), and whether the tree is dirty."""
    git = shutil.which("git")
    if git is None:
        raise SystemExit("git is needed to stamp the commit into the sidecar")
    commit = subprocess.run([git, "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, check=True, text=True)  # nosec B603
    status = subprocess.run([git, "status", "--porcelain"], cwd=ROOT, capture_output=True, check=True, text=True)  # nosec B603
    info = work / "_build.json"
    info.write_text(
        json.dumps({"commit": commit.stdout.strip(), "dirty": bool(status.stdout.strip())}), encoding="utf-8"
    )
    return info


def freeze() -> Path:
    """Run PyInstaller and return the frozen executable."""
    work = BUILD / "pyinstaller"
    work.mkdir(parents=True, exist_ok=True)
    entry = work / "ridge_sidecar_entry.py"
    entry.write_text(ENTRY, encoding="utf-8")
    build_info = stamp(work)
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
        "--add-data",
        f"{build_info}{os.pathsep}ridge",  # read by ridge.build_info at run time
        str(entry),
    ]
    print("$", " ".join(command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True)  # nosec B603
    exe = DIST / NAME / (NAME + (".exe" if sys.platform == "win32" else ""))
    if not exe.is_file():
        raise SystemExit(f"PyInstaller did not produce {exe}")
    return exe


def check_bundle() -> None:
    """Check that the keystore backend, the image decoders and the sidecar methods are in the frozen archive."""
    # build tool only: untyped, and installed from requirements-build.lock, not in development or CI
    from PyInstaller.archive.readers import (  # type: ignore[import-untyped,import-not-found,unused-ignore]  # noqa: PLC0415
        ZlibArchiveReader,
    )

    names = set(ZlibArchiveReader(str(BUILD / "pyinstaller" / NAME / "PYZ-00.pyz")).toc)
    missing = {KEYSTORE_BACKEND, "ridge.sidecar.handlers", "ridge.case.limits", *DECODERS, *FEATURES} - names
    if missing:
        raise SystemExit(f"frozen sidecar lacks {sorted(missing)}")
    print(
        f"frozen archive ok: {len(names)} modules, keystore backend {KEYSTORE_BACKEND}, {len(DECODERS)} decoders, "
        f"{len(FEATURES)} feature modules"
    )


def check_native(folder: Path) -> None:
    """Check that the decoders' native extensions and libraries are in the frozen folder."""
    names = [p.name for p in folder.rglob("*") if p.is_file()]
    missing = [pattern for pattern in NATIVE if not fnmatch.filter(names, pattern)]
    if missing:
        raise SystemExit(f"frozen sidecar lacks the native libraries {missing}")
    print(f"native decoders ok: {', '.join(NATIVE)}")


def smoke(exe: Path) -> None:
    """Talk JSON-RPC to the frozen sidecar the way the GUI does; raise on any mismatch.

    The workstation check is read-only: it asks the OS keystore whether a Ridge device secret
    exists, never shows it, and here it serves to learn whether the frozen engine reads HEIF.
    """
    with tempfile.TemporaryDirectory() as tmp:
        store = Path(tmp) / "store"
        store.mkdir()
        photo = synthetic_photo(Path(tmp) / "finger.png")
        requests = [
            {"jsonrpc": "2.0", "id": 1, "method": "ridge.version"},
            {"jsonrpc": "2.0", "id": 2, "method": "store.identity", "params": {"store": str(store)}},
            {"jsonrpc": "2.0", "id": 3, "method": "store.cases", "params": {"store": str(store)}},
            {"jsonrpc": "2.0", "id": 4, "method": "store.workstation", "params": {"store": str(store)}},
            {"jsonrpc": "2.0", "id": 5, "method": "photo.check", "params": {"path": str(photo)}},
        ]
        stdin = "".join(json.dumps(r) + "\n" for r in requests)
        done = subprocess.run([str(exe)], input=stdin.encode(), capture_output=True, timeout=120, check=False)  # nosec B603
    replies = [json.loads(line) for line in done.stdout.decode("utf-8").splitlines()]
    expected = [{"protocol": PROTOCOL}, {"exists": False}, []]
    results = [r.get("result") for r in replies]
    if done.returncode != 0 or len(results) != len(requests):
        tail = done.stderr.decode(errors="replace")[-2000:]
        raise SystemExit(f"frozen sidecar failed (exit {done.returncode}): {tail}")
    if results[0].get("protocol") != PROTOCOL or results[1:3] != expected[1:]:
        raise SystemExit(f"frozen sidecar answered unexpectedly: {results[:3]}")
    if not str(results[0].get("commit_source", "")).startswith("build"):  # the stamp must be in the bundle
        raise SystemExit(f"frozen sidecar does not carry its commit stamp: {results[0]}")
    libraries = next((f.get("text", "") for f in results[3] or [] if f.get("topic") == "Libraries"), "")
    if HEIF_READABLE not in libraries:
        raise SystemExit(f"the frozen sidecar does not read HEIF/HEIC: {libraries!r}")
    check = results[4] or {}
    if check.get("verdict") != "ok" or not check.get("finger_located"):  # the pipeline's finger and ridge measures run
        raise SystemExit(f"the frozen sidecar's capture check did not pass a synthetic finger: {check}")
    version = f"Ridge {results[0].get('ridge')} {results[0].get('commit')}"
    print(f"frozen sidecar ok: {version}, protocol {PROTOCOL}, reads HEIF, checks a synthetic photo")


def synthetic_photo(path: Path) -> Path:
    """Write the test suite's synthetic finger photo (no real data) for the frozen engine's capture check."""
    sys.path.insert(0, str(ROOT))
    from PIL import Image  # noqa: PLC0415  # build tool only
    from tests.synthetic import finger_photo, whorl_pattern  # noqa: PLC0415  # build tool only

    bgr = finger_photo(whorl_pattern(480, 360, 9.0))
    Image.fromarray(bgr[:, :, ::-1]).save(path, format="PNG")
    return path


def main() -> int:
    """Freeze, check the bundle, then smoke-test."""
    exe = freeze()
    check_bundle()
    check_native(exe.parent)
    smoke(exe)
    print(f"sidecar folder: {exe.parent}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
