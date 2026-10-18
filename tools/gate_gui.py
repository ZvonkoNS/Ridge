"""The desktop GUI gate (desktop_gui_tauri_standards.md §13), run by ``python tools/gate.py gui``.

npm: clean install from the lock file (lifecycle scripts off), lint, typecheck, format, tests,
production build, audit, licence allow-list; the build must not contain the development preview.
cargo: fmt, clippy with warnings as errors, tests (including the live sidecar test, made mandatory
here), cargo-audit and cargo-deny. A missing tool FAILS the gate; nothing is skipped silently.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess  # nosec B404 - fixed tool invocations, no shell
import sys
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui"
TAURI = GUI / "src-tauri"
NPM_LICENSES = {
    "MIT",
    "ISC",
    "Apache-2.0",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "0BSD",
    "OFL-1.1",  # the bundled Atkinson Hyperlegible fonts
    "(MIT OR Apache-2.0)",
    "Apache-2.0 OR MIT",
    "MIT OR Apache-2.0",
}
PREVIEW_MARKERS = ("the preview does not mock", "synthetic preview")


def _run(cwd: Path, *cmd: str, env: dict[str, str] | None = None) -> bool:
    print("$", " ".join(cmd), f"(in {cwd.relative_to(ROOT)})", flush=True)
    merged = {**os.environ, **(env or {})}
    return subprocess.run(cmd, cwd=cwd, env=merged, check=False).returncode == 0  # nosec B603


def npm_licences_ok(lock: Path) -> bool:
    """Check that every runtime (non-dev) npm package in the lock file has an allowed licence."""
    packages = json.loads(lock.read_text(encoding="utf-8")).get("packages", {})
    bad = [
        f"{name.removeprefix('node_modules/')}: {meta.get('license')}"
        for name, meta in packages.items()
        if name and not meta.get("dev") and meta.get("license") not in NPM_LICENSES
    ]
    for item in bad:
        print("  gui: npm licence not allowed:", item)
    return not bad


def preview_absent(dist: Path) -> bool:
    """Check that the development preview (synthetic data, mocked IPC) is not in the production build."""
    leaks = [p.name for p in dist.rglob("*.js") if any(m in p.read_text(encoding="utf-8") for m in PREVIEW_MARKERS)]
    for leak in leaks:
        print("  gui: development preview code in the production build:", leak)
    return bool(list(dist.rglob("*.js"))) and not leaks


def gate_gui() -> bool:
    """Run every GUI check; stop at the first failure."""
    tools = {name: shutil.which(name) for name in ("npm", "npx", "cargo")}
    missing = [name for name, path in tools.items() if path is None]
    if missing:
        print(f"  gui: {', '.join(missing)} not found on PATH - gate FAILED")
        return False
    npm, npx, cargo = (str(tools[n]) for n in ("npm", "npx", "cargo"))
    steps: list[Callable[[], bool]] = [
        lambda: _run(ROOT, sys.executable, "tools/gui_icons.py"),
        lambda: _run(GUI, npm, "ci", "--no-audit"),
        lambda: _run(GUI, npm, "run", "lint"),
        lambda: _run(GUI, npm, "run", "typecheck"),
        lambda: _run(GUI, npx, "prettier", "--check", "."),
        lambda: _run(GUI, npm, "test"),
        lambda: _run(GUI, npm, "run", "build"),
        lambda: preview_absent(GUI / "dist"),
        lambda: _run(GUI, npm, "audit", "--audit-level=moderate"),
        lambda: npm_licences_ok(GUI / "package-lock.json"),
        lambda: _run(TAURI, cargo, "fmt", "--check"),
        lambda: _run(TAURI, cargo, "clippy", "--locked", "--all-targets", "--", "-D", "warnings"),
        lambda: _run(TAURI, cargo, "test", "--locked", env={"RIDGE_REQUIRE_SIDECAR": "1"}),
        lambda: _run(TAURI, cargo, "audit", "--deny", "warnings"),
        lambda: _run(TAURI, cargo, "deny", "--locked", "check"),
    ]
    return all(step() for step in steps)
