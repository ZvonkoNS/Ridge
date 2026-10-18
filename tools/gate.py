"""Ridge quality gates (Python equivalents of the instruction pack's npm gates).

    python tools/gate.py all          # every gate, stops at the first failure
    python tools/gate.py lint test    # selected gates

Gates: docs, lint, format, typecheck, test, sast, deps, secrets, licenses, sbom, gui (the desktop
GUI's npm and cargo checks, in tools/gate_gui.py).
Run inside the project virtualenv with requirements-dev.lock installed. A gate whose tool
is missing FAILS (it is never skipped silently). ``deps`` needs network access to the
vulnerability databases; ``secrets`` needs the gitleaks binary on PATH.
"""

from __future__ import annotations

import importlib.metadata
import json
import re
import shutil
import subprocess  # nosec B404 - fixed tool invocations, no shell
import sys
from collections.abc import Callable
from pathlib import Path

from gate_gui import gate_gui  # tools/ is on sys.path when this script runs

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
BUILD = ROOT / "build"
ALLOWED_LICENSES = {
    "MIT",
    "MIT License",
    "MIT-0",
    "MIT-CMU",
    "BSD-3-Clause",
    "BSD License",
    "0BSD",
    "Zlib",
    "CC0-1.0",
    "Apache-2.0",
    "Apache Software License",
}
REQUIRED_DOCS = (
    "AGENTS.md",
    "CLAUDE.md",
    "README.md",
    "docs/prd.md",
    "docs/architecture.md",
    "Instruction_documentation/README.md",
    "Instruction_documentation/Project_Standards_Profile.md",
    "Instruction_documentation/standards_applicability_and_compliance_matrix.md",
    "Instruction_documentation/forensic_evidence_and_biometric_data_standards.md",
    "Instruction_documentation/execution_rules.md",
    "Instruction_documentation/coding_standards.md",
    "Instruction_documentation/testing_and_codex_quality_gates.md",
    "Instruction_documentation/Handoff/Handoff_Template.md",
)
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".tif", ".tiff", ".bmp", ".webp", ".gif", ".wsq"}
MD_LINK = re.compile(r"\]\(([^)\s]+)\)")


def run(*cmd: str) -> bool:
    """Run a command from the repository root; True when it exits 0."""
    print("$", " ".join(cmd), flush=True)
    return subprocess.run(cmd, cwd=ROOT, check=False).returncode == 0  # nosec B603


def _git_files(*args: str) -> list[str]:
    git = shutil.which("git")
    if git is None:
        return []
    out = subprocess.run([git, "ls-files", *args], cwd=ROOT, check=True, capture_output=True, text=True)  # nosec B603
    return [line for line in out.stdout.splitlines() if line]


def gate_docs() -> bool:
    """Check required docs, links, handoff numbering, images in git and runtime doc imports."""
    problems = [f"missing: {doc}" for doc in REQUIRED_DOCS if not (ROOT / doc).is_file()]
    for md in [
        ROOT / "AGENTS.md",
        ROOT / "CLAUDE.md",
        *ROOT.glob("docs/**/*.md"),
        *ROOT.glob("Instruction_documentation/**/*.md"),
    ]:
        for target in MD_LINK.findall(md.read_text(encoding="utf-8")):
            if re.match(r"^(https?:|mailto:|#)", target):
                continue
            path = target.split("#")[0].split(":")[0] if not re.match(r"^[A-Za-z]:", target) else target
            if path and not (md.parent / path).exists():
                problems.append(f"broken link in {md.relative_to(ROOT)}: {target}")
    numbers = sorted(
        int(m.group(1))
        for p in (ROOT / "Instruction_documentation/Handoff").glob("Handoff_*.md")
        if (m := re.fullmatch(r"Handoff_(\d+)\.md", p.name))
    )
    if numbers != list(range(1, len(numbers) + 1)):
        problems.append(f"handoffs are not consecutive from 1: {numbers}")
    tracked_or_new = _git_files() + _git_files("--others", "--exclude-standard")
    problems += [
        f"image file in git (biometric data must never be committed): {f}"
        for f in tracked_or_new
        if Path(f).suffix.lower() in IMAGE_SUFFIXES
    ]
    for py in (ROOT / "src").rglob("*.py"):
        if "Instruction_documentation" in py.read_text(encoding="utf-8"):
            problems.append(f"runtime code references the documentation: {py.relative_to(ROOT)}")
    for problem in problems:
        print("  docs:", problem)
    return not problems


def gate_lint() -> bool:
    """Ruff lint (incl. bandit S, bugbear, pylint subsets)."""
    return run(PY, "-m", "ruff", "check", ".")


def gate_format() -> bool:
    """Ruff formatting check."""
    return run(PY, "-m", "ruff", "format", "--check", ".")


def gate_typecheck() -> bool:
    """Mypy strict (configuration in pyproject.toml)."""
    return run(PY, "-m", "mypy")


def gate_test() -> bool:
    """Pytest with branch coverage (fail-under in pyproject.toml)."""
    return run(PY, "-m", "pytest", "--cov", "--cov-report=term-missing")


def gate_sast() -> bool:
    """Bandit on the runtime package."""
    return run(PY, "-m", "bandit", "-q", "-c", "pyproject.toml", "-r", "src")


def gate_deps() -> bool:
    """Known-vulnerability audit of both hash-pinned lock files (needs network)."""
    return all(
        run(PY, "-m", "pip_audit", "--strict", "--require-hashes", "--disable-pip", "-r", lock)
        for lock in ("requirements.lock", "requirements-dev.lock")
    )


def gate_secrets() -> bool:
    """Gitleaks over the working tree and, when present, the git history."""
    gitleaks = shutil.which("gitleaks")
    if gitleaks is None:
        print("  secrets: gitleaks not found on PATH (https://github.com/gitleaks/gitleaks) - gate FAILED")
        return False
    ok = run(gitleaks, "dir", ".", "--config", ".gitleaks.toml", "--redact", "--no-banner")
    if (ROOT / ".git").exists():
        ok = run(gitleaks, "git", ".", "--config", ".gitleaks.toml", "--redact", "--no-banner") and ok
    return ok


def runtime_packages() -> list[str]:
    """Runtime packages pinned in requirements.lock that are installed on this platform."""
    pinned = re.findall(
        r"^([A-Za-z0-9][A-Za-z0-9._-]*)==", (ROOT / "requirements.lock").read_text(encoding="utf-8"), re.M
    )
    installed = {_norm(d.metadata["Name"]) for d in importlib.metadata.distributions()}
    return [name for name in pinned if _norm(name) in installed]


def _norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def gate_licenses() -> bool:
    """Runtime dependency licences (from requirements.lock) against the allow-list."""
    out = subprocess.run(  # nosec B603
        [PY, "-m", "piplicenses", "--format=json", "--packages", *runtime_packages()],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    bad = []
    for pkg in json.loads(out.stdout):
        parts = {p.strip("() ") for p in re.split(r"\s+(?:AND|OR)\s+|;", pkg["License"])}
        if not parts <= ALLOWED_LICENSES:
            bad.append(f"{pkg['Name']}: {pkg['License']}")
        print(f"  {pkg['Name']} {pkg['Version']}: {pkg['License']}")
    # pillow-heif wheels also bundle libheif/libde265 (LGPL) and x265 (GPL): recorded as an
    # exception in Instruction_documentation/Project_Standards_Profile.md, not visible in metadata.
    for item in bad:
        print("  licenses: not allowed:", item)
    return not bad


def gate_sbom() -> bool:
    """CycloneDX SBOM of the runtime lock file -> build/sbom.cdx.json."""
    BUILD.mkdir(exist_ok=True)
    return run(
        PY,
        "-m",
        "cyclonedx_py",
        "requirements",
        "requirements.lock",
        "--pyproject",
        "pyproject.toml",
        "--output-reproducible",
        "--of",
        "JSON",
        "-o",
        str(BUILD / "sbom.cdx.json"),
    )


GATES: dict[str, Callable[[], bool]] = {
    "docs": gate_docs,
    "lint": gate_lint,
    "format": gate_format,
    "typecheck": gate_typecheck,
    "test": gate_test,
    "sast": gate_sast,
    "deps": gate_deps,
    "secrets": gate_secrets,
    "licenses": gate_licenses,
    "sbom": gate_sbom,
    "gui": gate_gui,
}


def main(argv: list[str]) -> int:
    """Run the named gates (or all) and return 0 only if every one passed."""
    names = list(GATES) if not argv or argv == ["all"] else argv
    unknown = [n for n in names if n not in GATES]
    if unknown:
        print(f"unknown gate(s): {', '.join(unknown)}; choose from: all, {', '.join(GATES)}")
        return 2
    for name in names:
        print(f"=== gate: {name}", flush=True)
        if not GATES[name]():
            print(f"=== FAILED: {name}")
            return 1
    print(f"=== all {len(names)} gate(s) passed: {', '.join(names)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
