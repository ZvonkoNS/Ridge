"""Offline guarantee (PRD SEC-1, ADR-001): Ridge never opens a network connection."""

from __future__ import annotations

import ast
import socket
from pathlib import Path

import pytest

from ridge.cli import main

SRC = Path(__file__).resolve().parents[1] / "src" / "ridge"
NETWORK_MODULES = {"socket", "ssl", "http", "urllib", "ftplib", "smtplib", "telnetlib", "xmlrpc", "requests", "httpx"}


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module.split(".")[0])
    return names


@pytest.mark.parametrize("path", sorted(SRC.rglob("*.py")), ids=lambda p: p.relative_to(SRC).as_posix())
def test_no_network_imports(path: Path) -> None:
    assert not imported_modules(path) & NETWORK_MODULES


def test_full_run_makes_no_network_calls(photo_png: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    assert main([str(photo_png), "-o", str(tmp_path / "out"), "--debug"]) == 0


def test_runtime_never_reads_documentation() -> None:
    for path in SRC.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "Instruction_documentation" not in text, path
        assert "docs/" not in text, path
