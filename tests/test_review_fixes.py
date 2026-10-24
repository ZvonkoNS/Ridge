"""Regression tests for the Codex review findings on the AFIS-readiness stack (pull requests #35 to #49)."""

from __future__ import annotations

import io
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from ridge.capture import check_bytes
from ridge.case.annotation_image import export_annotated
from ridge.case.annotations import add_annotation
from ridge.case.cover_sheet import render_cover_sheet
from ridge.case.identity import create_identity, unlock_identity
from ridge.case.jobs import JobParams, run_extraction_job
from ridge.case.reports import load_report
from ridge.case.store import open_case
from ridge.errors import ParameterError
from ridge.export.sweep import sweep_factors
from ridge.image_io import encode_image
from ridge.metadata.provenance import provenance_hints
from ridge.pipeline.location import PrintLocation
from ridge.pipeline.rectify import rectification
from ridge.validation.report import read_ranks
from tests.case_helpers import FAST_KDF, PASSPHRASE, MemoryKeyStore, new_case, photo_file
from tests.conftest import write_png
from tests.synthetic import finger_photo, whorl_pattern
from tests.test_rectify import ellipse_mask


def test_a_sweep_too_fine_for_its_steps_is_refused_before_anything_is_written() -> None:  # PR 38
    assert len(set(sweep_factors(0.025, 3))) == 3
    with pytest.raises(ParameterError, match="too small to tell 9 steps apart"):
        sweep_factors(0.025, 9)


def test_a_rank_row_with_the_wrong_number_of_fields_is_refused(tmp_path: Path) -> None:  # PR 40
    short = tmp_path / "short.csv"
    short.write_text("probe,rank\np1,1\np2\n", encoding="utf-8")
    with pytest.raises(ParameterError, match="line 3: the row does not have the header's fields"):
        read_ranks(short)
    long = tmp_path / "long.csv"
    long.write_text("probe,rank\np1,1,extra\n", encoding="utf-8")
    with pytest.raises(ParameterError, match="line 2"):
        read_ranks(long)
    ok = tmp_path / "ok.csv"
    ok.write_text("probe,rank\np1,1\np2,\n", encoding="utf-8")
    assert read_ranks(ok)["all"] == [1, None]  # an explicitly empty rank is a search whose mate was not returned


def test_provenance_tells_an_unreadable_exif_block_from_an_absent_one_and_sees_any_history_prefix() -> None:  # PR 39
    png = encode_image(finger_photo(whorl_pattern(240, 180, 9.0)), ".png")
    unreadable = provenance_hints(png, {"groups": [], "warnings": ["The EXIF block could not be read (SyntaxError)."]})
    ids = {h["id"] for h in unreadable["hints"]}
    assert "exif-unreadable" in ids
    assert "no-exif" not in ids
    assert "copy-size" not in ids
    absent = provenance_hints(png, {"groups": [], "warnings": []})
    assert "no-exif" in {h["id"] for h in absent["hints"]}
    history = {
        "groups": [
            {"id": "exif-ifd0", "entries": [{"name": "Make", "value": "Cam"}]},
            {"id": "xmp", "entries": [{"name": "mm:History[1]/stEvt:action", "value": "saved"}]},
        ],
        "warnings": [],
    }
    assert "xmp-history" in {h["id"] for h in provenance_hints(png, history)["hints"]}


def test_a_software_tag_alone_is_a_note_not_a_copy_warning() -> None:  # PR 46
    photo = finger_photo(whorl_pattern(480, 360, 9.0))
    buffer = io.BytesIO()
    exif = Image.Exif()
    exif[0x0131] = "CamFirmware 1.2"  # Software, as a camera writes it
    exif[0x010F] = "CamMaker"  # Make
    Image.fromarray(photo[:, :, ::-1]).save(buffer, format="JPEG", quality=95, exif=exif.tobytes())
    check = check_bytes(buffer.getvalue())
    notes = {f.id for f in check.findings if f.level == "note"}
    assert "software" in notes
    assert "copy" not in notes


def test_the_rectified_half_width_does_not_depend_on_background_rows() -> None:  # PR 44a
    short = rectification(ellipse_mask(600, 400, 128, 240))
    tall = rectification(ellipse_mask(1600, 400, 128, 240))
    assert short is not None
    assert tall is not None
    assert short.half_width_px == pytest.approx(128 * 0.866, rel=0.05)  # the median over the finger's rows
    assert tall.half_width_px == pytest.approx(short.half_width_px, rel=0.03)


def test_outline_edges_follow_the_curved_unrolling() -> None:  # PR 44b
    # A tapered finger: the half-width halves from the bottom to the top, so a vertical canvas edge bends.
    yy, xx = np.mgrid[0:400, 0:300].astype(np.float64)
    half = 40.0 + 60.0 * yy / 399.0
    mask = np.abs(xx - 150.0) <= half
    r = rectification(mask)
    assert r is not None
    canvas_x = r.middle + 40.0  # a constant arc offset inside every row's reach
    rect = PrintLocation(
        box=(int(canvas_x) - 20, 50, 40, 300),
        outline=(((int(canvas_x), 50), (int(canvas_x) + 20, 50), (int(canvas_x) + 20, 350), (int(canvas_x), 350)),),
        parts=1,
    )
    back = rect.from_rectified(r)
    left_edge = sorted({p for p in back.outline[0] if 50 <= p[1] <= 350}, key=lambda p: p[1])
    xs_along = [p[0] for p in left_edge]
    assert len(left_edge) > 4  # points along the edge, not only its ends
    assert max(xs_along) - min(xs_along) >= 3  # and the edge bends with the half-width
    assert sum(len(poly) for poly in back.outline) <= 256


@pytest.fixture
def job_case(tmp_path: Path) -> tuple[Path, MemoryKeyStore, str]:
    keystore = MemoryKeyStore()
    store = tmp_path / "store"
    create_identity(store, PASSPHRASE, keystore, FAST_KDF)
    folder = new_case(store, keystore)
    with open_case(folder, PASSPHRASE, keystore) as case:
        evidence = case.import_evidence(photo_file(tmp_path / "in"))
    return folder, keystore, evidence.sha256


def test_a_rerun_job_can_be_annotated_and_the_export_keeps_its_resolution_and_numbers(  # PR 48
    job_case: tuple[Path, MemoryKeyStore, str], tmp_path: Path
) -> None:
    folder, keystore, evidence = job_case
    signer = unlock_identity(folder.parent, PASSPHRASE, keystore)
    with open_case(folder, PASSPHRASE, keystore) as case:
        first = run_extraction_job(case, evidence, signer, JobParams())
        second = run_extraction_job(case, evidence, signer, JobParams())  # identical pixels: duplicate writes
        export_sha = next(i.sha256 for i in case.items() if i.role == "export")
        print_sha = next(i.sha256 for i in case.items() if i.role == "print")
        assert first.job_id != second.job_id
        a = add_annotation(
            case, signer, job_id=second.job_id, sha256=print_sha, marks=[{"x": 1, "y": 1, "kind": "other"}]
        )
        assert a.job_id == second.job_id
        with pytest.raises(ParameterError, match="same job"):
            add_annotation(case, signer, job_id="0" * 36, sha256=print_sha, marks=[{"x": 1, "y": 1, "kind": "other"}])
        with Image.open(io.BytesIO(case.read(export_sha, log=False))) as im:
            width, height = im.size
            dpi = im.info["dpi"]
        marks = [{"x": width - 1, "y": height - 1, "kind": "ending"}, {"x": 0, "y": 0, "kind": "bifurcation"}]
        b = add_annotation(case, signer, job_id=first.job_id, sha256=export_sha, marks=marks)
        dest = tmp_path / "charted.png"
        export_annotated(case, b.seq, dest)
        source = np.asarray(Image.open(io.BytesIO(case.read(export_sha, log=False))).convert("RGB"))
    with Image.open(dest) as out:
        assert out.info["dpi"] == pytest.approx(dpi, abs=1)
        drawn = np.asarray(out.convert("RGB"))
    corner = (slice(height - 40, height), slice(width - 40, width))
    assert (drawn[corner] != source[corner]).any()  # the number of the last mark landed inside the image
    assert (drawn[:40, :40] != source[:40, :40]).any()


def test_the_cover_sheet_says_when_no_limits_were_configured(
    job_case: tuple[Path, MemoryKeyStore, str],
) -> None:  # PR 37
    folder, keystore, evidence = job_case
    signer = unlock_identity(folder.parent, PASSPHRASE, keystore)
    with open_case(folder, PASSPHRASE, keystore) as case:
        outcome = run_extraction_job(case, evidence, signer, JobParams())
        signed = load_report(case, folder.parent, outcome.job_id, log=False)
    page = render_cover_sheet(signed)
    assert "none configured in this store" in page
    report = dict(signed.report)
    report.pop("limits_of_use", None)
    older = type(signed)(**{**signed.__dict__, "report": report}) if hasattr(signed, "__dict__") else signed
    if older is not signed:
        assert "not recorded in this report" in render_cover_sheet(older)


def test_the_resolution_note_counts_the_pipelines_own_enlargement(
    job_case: tuple[Path, MemoryKeyStore, str],
) -> None:  # PR 36
    folder, keystore, _ = job_case
    signer = unlock_identity(folder.parent, PASSPHRASE, keystore)
    low = write_png(folder.parent.parent / "low.png", finger_photo(whorl_pattern(480, 360, 4.5)))  # few px per ridge
    with open_case(folder, PASSPHRASE, keystore) as case:
        evidence = case.import_evidence(low)
        outcome = run_extraction_job(case, evidence.sha256, signer, JobParams())
    export = outcome.report["export"]
    assert export["produced"]
    assert export["pixels_per_photo_pixel"] == pytest.approx(
        export["factor"] * outcome.report["measurements"]["output_scale"]
    )
    assert export["pixels_per_photo_pixel"] > 1.05
    assert "resolution_note" in export
