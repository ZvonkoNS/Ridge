"""Terminal output of every command-line tool: no escapes (CWE-150), no hidden reordering (CVE-2021-42574)."""

from __future__ import annotations

import getpass
from pathlib import Path

import pytest

from ridge import cli as ridge_cli
from ridge.case import cli_common
from ridge.case.cli import main as ridge_case
from ridge.terminal import HIDDEN_RANGES, reveal, safe
from tests.case_helpers import FAST_KDF, PASSPHRASE, MemoryKeyStore, new_case
from tests.conftest import write_png
from tests.golden_cases import CASES_BY_NAME

# Built with chr(): invisible characters never go into the source.
ESC, CR, RLO, ZWSP, BOM = chr(0x1B), chr(0x0D), chr(0x202E), chr(0x200B), chr(0xFEFF)


def test_every_hidden_character_is_written_as_its_code_point() -> None:
    for first, last in HIDDEN_RANGES:
        for code in {first, (first + last) // 2, last}:
            assert reveal(f"a{chr(code)}b") == f"a<U+{code:04X}>b"
    assert reveal("Škofja Loka, 指纹, café") == "Škofja Loka, 指纹, café"  # ordinary letters stay


def test_safe_keeps_line_breaks_and_tabs_but_shows_carriage_returns() -> None:
    assert safe(f"one\ttwo\nthree{CR}four") == "one\ttwo\nthree<U+000D>four"
    assert safe(f"{ESC}[2J{RLO}") == "<U+001B>[2J<U+202E>"
    assert reveal("one\ntwo") == "one<U+000A>two"
    assert safe(42) == "42"


def test_say_and_warn_never_pass_hidden_characters(capsys: pytest.CaptureFixture[str]) -> None:
    cli_common.say(f"label {RLO}fdp.exe")
    cli_common.warn(f"problem {ESC}]0;title{BOM}")
    captured = capsys.readouterr()
    assert captured.out == "label <U+202E>fdp.exe\n"
    assert captured.err == "problem <U+001B>]0;title<U+FEFF>\n"


@pytest.fixture
def keystore(monkeypatch: pytest.MonkeyPatch) -> MemoryKeyStore:
    shared = MemoryKeyStore()
    monkeypatch.setattr(cli_common, "KEYSTORE_FACTORY", lambda: shared)
    monkeypatch.setattr(getpass, "getpass", lambda prompt="": PASSPHRASE)
    return shared


def test_case_listing_and_import_show_hidden_characters_in_names_and_notes(
    tmp_path: Path, keystore: MemoryKeyStore, capsys: pytest.CaptureFixture[str]
) -> None:
    from ridge.case.identity import create_identity  # noqa: PLC0415  # keeps the unit tests above import-light

    store = tmp_path / "store"
    create_identity(store, PASSPHRASE, keystore, FAST_KDF)
    case_dir = new_case(store, keystore)
    photo = write_png(tmp_path / f"invoice{RLO}gnp.png", CASES_BY_NAME["whorl_default"].photo())
    source = f"Exhibit{ZWSP} 12 {RLO}A"
    assert ridge_case(["import", str(case_dir), str(photo), "--source", source]) == 0
    imported = capsys.readouterr().out
    assert ridge_case(["list", str(case_dir)]) == 0
    listed = capsys.readouterr().out
    for out in (imported, listed):
        assert RLO not in out
        assert ZWSP not in out
        assert "invoice<U+202E>gnp.png" in out
    assert "[Exhibit<U+200B> 12 <U+202E>A]" in listed


def test_case_errors_show_hidden_characters_in_paths(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    missing = tmp_path / f"store{RLO}x"
    missing.mkdir()
    assert ridge_case(["cases", "--store", str(missing)]) == 1
    err = capsys.readouterr().err
    assert RLO not in err
    assert "store<U+202E>x is not a Ridge store folder" in err


def test_rnd_cli_shows_hidden_characters_in_file_names(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    photo = write_png(tmp_path / f"finger{RLO}gnp.png", CASES_BY_NAME["whorl_default"].photo())
    absent = tmp_path / f"absent{ZWSP}.png"
    assert ridge_cli.main([str(absent), str(photo), "-o", str(tmp_path / "out")]) == 0
    captured = capsys.readouterr()
    assert RLO not in captured.out
    assert ZWSP not in captured.err
    assert "finger<U+202E>gnp.png -> " in captured.out
    assert "absent<U+200B>.png not found, skipped" in captured.err
