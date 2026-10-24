"""Provenance hints (PRD FR-42): drawn from the file's own facts and encoding, never verified or scored."""

from __future__ import annotations

import getpass
import io
import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from PIL import Image, JpegImagePlugin

from ridge.case import cli_common
from ridge.case.cli import main
from ridge.case.identity import create_identity, unlock_identity
from ridge.case.jobs import JobParams, run_extraction_job
from ridge.case.report_html import render_report_html
from ridge.case.reports import load_report, render_report
from ridge.case.store import open_case
from ridge.metadata import read_metadata
from ridge.metadata.provenance import (
    COPY_SIDES,
    SCHEMA,
    STD_LUMINANCE_SUM,
    jpeg_quality_estimate,
    provenance_hints,
    provenance_text,
)
from ridge.sidecar.handlers import Session
from ridge.sidecar.server import handle
from tests import metadata_samples as samples
from tests.case_helpers import FAST_KDF, PASSPHRASE, MemoryKeyStore, new_case, photo_file
from tests.golden_cases import CASES_BY_NAME


def jpeg_bytes(quality: int, *, exif: Image.Exif | None = None, size: tuple[int, int] = (64, 48)) -> bytes:
    rng = np.random.default_rng(3)
    image = Image.fromarray(rng.integers(0, 255, (size[1], size[0], 3), dtype=np.uint8))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=quality, **({"exif": exif} if exif is not None else {}))
    return buffer.getvalue()


def ids(record: dict[str, Any]) -> list[str]:
    return [h["id"] for h in record["hints"]]


def test_jpeg_quality_is_estimated_from_the_luminance_table() -> None:
    assert STD_LUMINANCE_SUM == 3688  # ITU-T T.81 Table K.1, summed
    for quality in (95, 85, 75, 50):
        data = jpeg_bytes(quality)
        with Image.open(io.BytesIO(data)) as im:
            assert isinstance(im, JpegImagePlugin.JpegImageFile)
            tables = dict(im.quantization)
        estimate = jpeg_quality_estimate(tables)
        assert estimate is not None
        assert abs(estimate - quality) <= 2
    assert jpeg_quality_estimate(None) is None
    assert jpeg_quality_estimate({0: [0] * 64}) is None
    assert jpeg_quality_estimate({0: [1, 2, 3]}) is None


def test_a_stripped_small_jpeg_reads_like_a_forwarded_copy() -> None:
    data = jpeg_bytes(72, size=(1280, 32))
    record = provenance_hints(data, read_metadata(data))
    assert record["schema"] == SCHEMA
    assert ids(record) == ["no-exif", "copy-size", "jpeg-quality"]
    assert "1280 px" in record["hints"][1]["text"]
    assert abs(record["jpeg_quality_estimate"] - 72) <= 2
    assert "Ridge does not verify them" in record["notice"]
    assert 1280 in COPY_SIDES


def test_a_camera_jpeg_names_its_software_and_history_but_not_a_missing_exif() -> None:
    data = samples.full_jpeg()  # camera EXIF, Software "Firmware 1.2", XMP history, ICC
    record = provenance_hints(data, read_metadata(data))
    found = ids(record)
    assert "no-exif" not in found
    assert "no-camera" not in found
    assert "copy-size" not in found
    assert "software" in found
    assert any("Firmware 1.2" in h["text"] for h in record["hints"])
    assert "xmp-history" in found
    assert "jpeg-quality" in found


def test_an_exif_block_without_a_camera_and_a_png_photo() -> None:
    exif = Image.Exif()
    exif[0x0112] = 1  # orientation only
    data = jpeg_bytes(90, exif=exif)
    assert "no-camera" in ids(provenance_hints(data, read_metadata(data)))
    png = io.BytesIO()
    Image.fromarray(CASES_BY_NAME["whorl_default"].photo()[:, :, ::-1]).save(png, format="PNG")
    record = provenance_hints(png.getvalue(), read_metadata(png.getvalue()))
    assert ids(record) == ["no-exif", "png"]
    assert record["jpeg_quality_estimate"] is None
    assert provenance_hints(b"not an image", None)["hints"][0]["id"] == "no-exif"  # bounded, never raises


def test_hint_text_is_display_safe() -> None:
    exif = Image.Exif()
    exif[0x010F] = "Cam"
    exif[0x0110] = "M"
    exif[0x0131] = "Tool\x1b[2JX"  # a terminal escape in the Software tag
    record = provenance_hints(jpeg_bytes(90, exif=exif), read_metadata(jpeg_bytes(90, exif=exif)))
    software = next(h for h in record["hints"] if h["id"] == "software")
    assert "\x1b" not in software["text"]
    assert "Tool<U+001B>[2JX" in software["text"]
    lines = provenance_text(record)
    assert lines[0].startswith("Provenance    hints")
    assert any("Tool<U+001B>[2JX" in line for line in lines)
    assert provenance_text(None) == []
    assert "- none" in provenance_text({"hints": [], "notice": "n"})[1]


@pytest.fixture
def case_dir(tmp_path: Path) -> tuple[Path, MemoryKeyStore]:
    keystore = MemoryKeyStore()
    store = tmp_path / "store"
    create_identity(store, PASSPHRASE, keystore, FAST_KDF)
    return new_case(store, keystore), keystore


def test_jobs_record_the_hints_and_reports_render_them(case_dir: tuple[Path, MemoryKeyStore], tmp_path: Path) -> None:
    folder, keystore = case_dir
    store = folder.parent
    signer = unlock_identity(store, PASSPHRASE, keystore)
    with open_case(folder, PASSPHRASE, keystore) as case:
        evidence = case.import_evidence(photo_file(tmp_path / "in"))
        outcome = run_extraction_job(case, evidence.sha256, signer, JobParams())
        section = outcome.report["input"]["provenance"]
        assert section["schema"] == SCHEMA
        assert ids(section) == ["no-exif", "png"]
        signed = load_report(case, store, outcome.job_id)
        text = render_report(signed.report, signer.key_id)
        assert "Provenance    hints (not verified):" in text
        assert "PNG is not a phone camera format" in text
        html = render_report_html(signed)
        assert "<h3>Provenance hints</h3>" in html
        assert "PNG is not a phone camera format" in html
        older = {**signed.report, "input": {k: v for k, v in signed.report["input"].items() if k != "provenance"}}
        assert "Provenance" not in render_report(older, signer.key_id)


def test_cli_and_sidecar_show_the_hints(
    case_dir: tuple[Path, MemoryKeyStore],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    folder, keystore = case_dir
    monkeypatch.setattr(cli_common, "KEYSTORE_FACTORY", lambda: keystore)
    monkeypatch.setattr(getpass, "getpass", lambda prompt="": PASSPHRASE)
    with open_case(folder, PASSPHRASE, keystore) as case:
        sha = case.import_evidence(photo_file(tmp_path / "in")).sha256
        before = len(case.entries)
    assert main(["metadata", str(folder), sha]) == 0
    out = capsys.readouterr().out
    assert "Provenance    hints (not verified):" in out
    assert "PNG is not a phone camera format" in out
    with open_case(folder, PASSPHRASE, keystore) as case:
        assert len(case.entries) - before == 1  # the hints come from the same single logged read
    assert main(["metadata", str(folder), sha, "--json"]) == 0
    assert "provenance" not in json.loads(capsys.readouterr().out)  # --json stays the metadata record alone

    session = Session(keystore_factory=lambda: keystore)

    def rpc(method: str, params: dict[str, Any]) -> Any:
        message = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
        return json.loads(handle(json.dumps(message).encode(), session))

    rpc("session.unlock", {"store": str(folder.parent.resolve()), "case_id": folder.name, "passphrase": PASSPHRASE})
    view = rpc("metadata.get", {"sha256": sha})["result"]
    assert view["provenance"]["schema"] == SCHEMA
    assert ids(view["provenance"]) == ["no-exif", "png"]
    session.close()
