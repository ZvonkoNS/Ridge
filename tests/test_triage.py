"""Folder triage (FR-57): reading order, the CSV index, untouched originals, refused destinations and the CLI."""

from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path
from typing import Any, cast

import cv2
import numpy as np
import pytest

import ridge.triage as triage_module
from ridge.arrays import ImageU8
from ridge.capture import MIN_CLARITY
from ridge.case.cli import main
from ridge.errors import InputError, InputRejectedError, OutputError, OutputExistsError, ParameterError
from ridge.image_io import encode_image, read_bounded
from ridge.sidecar.handlers import Session
from ridge.sidecar.server import handle
from ridge.triage import (
    COLUMNS,
    GROUPS,
    NOTICE,
    SCHEMA,
    Triage,
    index_bytes,
    list_photos,
    row_text,
    triage_folder,
    triage_text,
    write_index,
)
from tests.case_helpers import MemoryKeyStore
from tests.synthetic import BACKGROUND_BGR, finger_photo, whorl_pattern


def png(img: ImageU8) -> bytes:
    return encode_image(img, ".png")


def stripes(height: int, width: int, period: float) -> ImageU8:
    """A grey periodic texture without a finger: a ridge-like wave the skin-colour gate does not locate."""
    xx = np.arange(width, dtype=np.float32)[None, :]
    wave = 0.5 + 0.5 * np.cos(2.0 * np.pi * xx / period)
    img = np.broadcast_to((90.0 + 80.0 * wave)[..., None], (height, width, 3)).astype(np.float32)
    img += np.random.default_rng(3).normal(0.0, 6.0, (height, width, 1)).astype(np.float32)
    return cast(ImageU8, np.clip(img, 0, 255).astype(np.uint8))


def plain(height: int, width: int) -> ImageU8:
    """The synthetic background alone: no finger, no wave."""
    img = np.empty((height, width, 3), np.float32)
    img[:] = BACKGROUND_BGR
    img += np.random.default_rng(5).normal(0.0, 6.0, (height, width, 1)).astype(np.float32)
    return cast(ImageU8, np.clip(img, 0, 255).astype(np.uint8))


def snapshot(folder: Path) -> dict[str, tuple[int, str]]:
    return {
        p.relative_to(folder).as_posix(): (p.stat().st_mtime_ns, hashlib.sha256(p.read_bytes()).hexdigest())
        for p in folder.rglob("*")
        if p.is_file()
    }


@pytest.fixture(scope="module")
def folder(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("phone")
    sharp = finger_photo(whorl_pattern(480, 360, 9.0))
    (root / "IMG_0003.png").write_bytes(png(sharp))
    (root / "IMG_0001.png").write_bytes(png(finger_photo(whorl_pattern(480, 360, 9.0), blur_sigma=5.0)))
    ok, grey = cv2.imencode(
        ".jpg", finger_photo(whorl_pattern(480, 360, 9.0), colour=False), [cv2.IMWRITE_JPEG_QUALITY, 95]
    )
    assert ok
    (root / "IMG_0002.jpg").write_bytes(grey.tobytes())
    (root / "IMG_0007.png").write_bytes(png(stripes(480, 360, 9.0)))
    (root / "IMG_0004.png").write_bytes(png(plain(480, 360)))
    (root / "IMG_0005.png").write_bytes(b"not an image")
    (root / "notes.txt").write_bytes(b"text")
    (root / "sub").mkdir()
    (root / "sub" / "IMG_0006.png").write_bytes(png(sharp))
    return root


@pytest.fixture(scope="module")
def triage(folder: Path) -> Triage:
    before = snapshot(folder)
    result = triage_folder(folder)
    assert snapshot(folder) == before  # every original untouched: bytes and timestamps
    return result


@pytest.fixture(scope="module")
def small(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("small")
    (root / "a.png").write_bytes(png(finger_photo(whorl_pattern(480, 360, 9.0))))
    (root / "b.png").write_bytes(b"not an image")
    return root


def test_the_reading_order_puts_a_located_finger_with_a_clear_wave_first(triage: Triage, folder: Path) -> None:
    assert triage.rows[0].file == "IMG_0003.png"
    assert {r.file: r.group for r in triage.rows} == {
        "IMG_0003.png": "finger-ridges",
        "IMG_0002.jpg": "ridges-no-finger",  # a finger in grey: skin colour does not locate it
        "IMG_0007.png": "ridges-no-finger",  # a periodic texture: the same group, by design
        "IMG_0001.png": "finger-unclear",
        "IMG_0004.png": "nothing",
        "IMG_0005.png": "refused",
    }
    order = [r.group for r in triage.rows]
    assert order == sorted(order, key=GROUPS.index)
    wave = [r.clarity for r in triage.rows if r.group == "ridges-no-finger"]
    assert wave == sorted(wave, key=lambda c: -(c or 0.0))  # the clearest wave first within a group
    assert (len(triage.rows), triage.other_files, triage.recursive) == (6, 1, False)  # notes.txt was not opened
    assert {g: triage.count(g) for g in GROUPS} == {
        "finger-ridges": 1,
        "ridges-no-finger": 2,
        "finger-unclear": 1,
        "nothing": 1,
        "refused": 1,
    }
    first, refused = triage.rows[0], triage.rows[-1]
    assert first.check is not None
    assert first.check.sha256 == hashlib.sha256((folder / "IMG_0003.png").read_bytes()).hexdigest()
    assert first.clarity is not None
    assert first.clarity >= MIN_CLARITY
    assert refused.check is None
    assert refused.clarity is None
    assert refused.size == len(b"not an image")
    assert "not a supported image" in refused.reason


def test_the_index_lists_every_file_in_order_and_is_the_same_bytes_twice(
    triage: Triage, folder: Path, tmp_path: Path
) -> None:
    dest = tmp_path / "out" / "TRIAGE.csv"
    dest.parent.mkdir()
    digest = write_index(triage, dest)
    data = dest.read_bytes()
    assert hashlib.sha256(data).hexdigest() == digest
    assert b"\r" not in data
    rows = list(csv.reader(io.StringIO(data.decode("utf-8"))))
    assert rows[0] == list(COLUMNS)
    assert [r[0] for r in rows[1:]] == [str(i) for i in range(1, 7)]
    assert [r[2] for r in rows[1:]] == [row.file for row in triage.rows]
    first = dict(zip(COLUMNS, rows[1], strict=True))
    assert (first["group"], first["finger_located"], first["capture_verdict"], first["reason"]) == (
        "finger-ridges",
        "yes",
        "ok",
        "",
    )
    assert {"ok:located", "ok:clarity", "note:scale"} <= set(first["findings"].split())
    assert float(first["clarity"]) >= MIN_CLARITY
    assert (first["width_px"], first["height_px"]) == ("360", "480")
    last = dict(zip(COLUMNS, rows[-1], strict=True))
    assert (last["group"], last["sha256"], last["clarity"]) == ("refused", "", "")
    assert "not a supported image" in last["reason"]
    assert data == index_bytes(triage_folder(folder))  # the same folder gives the same index


def test_an_unsafe_destination_is_refused_and_nothing_is_written(triage: Triage, folder: Path, tmp_path: Path) -> None:
    taken = tmp_path / "taken.csv"
    taken.write_bytes(b"x")
    with pytest.raises(OutputExistsError, match="already exists"):
        write_index(triage, taken)
    assert taken.read_bytes() == b"x"
    with pytest.raises(OutputError, match="inside the scanned folder"):
        write_index(triage, folder / "TRIAGE.csv")
    with pytest.raises(OutputError, match="inside the scanned folder"):
        write_index(triage, folder / "sub" / "TRIAGE.csv")
    with pytest.raises(OutputError, match=r"\.csv"):
        write_index(triage, tmp_path / "TRIAGE.png")
    with pytest.raises(OutputError, match="does not exist"):
        write_index(triage, tmp_path / "missing" / "TRIAGE.csv")
    assert not (folder / "TRIAGE.csv").exists()
    assert not (folder / "sub" / "TRIAGE.csv").exists()
    assert sorted(p.name for p in tmp_path.iterdir()) == ["taken.csv"]


def test_folders_that_cannot_be_checked_are_refused_before_any_read(folder: Path, tmp_path: Path) -> None:
    with pytest.raises(InputError, match="not a folder"):
        triage_folder(folder / "IMG_0003.png")
    with pytest.raises(InputError, match="no photo"):
        triage_folder(tmp_path)
    with pytest.raises(InputRejectedError, match="the limit is 2"):
        triage_folder(folder, max_files=2)
    with pytest.raises(ParameterError, match="--max-files"):
        triage_folder(folder, max_files=0)
    photos, other = list_photos(folder)
    assert [p.name for p in photos] == [
        "IMG_0001.png",
        "IMG_0002.jpg",
        "IMG_0003.png",
        "IMG_0004.png",
        "IMG_0005.png",
        "IMG_0007.png",
    ]
    assert other == 1
    photos, other = list_photos(folder, recursive=True)
    assert [p.relative_to(folder).as_posix() for p in photos][-1] == "sub/IMG_0006.png"
    assert (len(photos), other) == (7, 1)


def test_the_record_and_the_text(triage: Triage) -> None:
    record = triage.to_json()
    assert (record["schema"], record["notice"], record["photos"], record["other_files"]) == (SCHEMA, NOTICE, 6, 1)
    assert record["counts"]["finger-ridges"] == 1
    assert record["thresholds"]["min_clarity"] == MIN_CLARITY
    assert set(record["groups"]) == set(GROUPS)
    assert [r["order"] for r in record["rows"]] == [1, 2, 3, 4, 5, 6]
    assert record["rows"][0]["check"]["schema"] == "ridge.capture-check/1"
    assert "notice" not in record["rows"][0]["check"]  # the triage record carries its own notice once
    assert record["rows"][-1]["check"] is None
    json.dumps(record)
    lines = triage_text(triage, index=(Path("x.csv"), "ab" * 32))
    assert lines[0].endswith("6 photo(s) checked, 1 other file(s) not read")
    assert any(line.split() == ["1", "finger-ridges", *lines[1].split()[2:]] for line in lines[1:2])
    assert lines[-2] == f"index written to x.csv (SHA-256 {'ab' * 32})"
    assert lines[-1] == NOTICE
    assert row_text(1, triage.rows[0]).startswith("    1  finger-ridges     clarity 0.0")
    assert row_text(6, triage.rows[-1]).endswith("IMG_0005.png")
    assert "not a supported image" in row_text(6, triage.rows[-1])
    recursive = Triage(triage.folder, True, triage.rows, 0)
    assert triage_text(recursive)[0].endswith("6 photo(s) checked, subfolders included")


def test_the_cli_lists_writes_and_refuses(small: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["triage", str(small)]) == 0
    out = capsys.readouterr().out
    assert out.splitlines()[0].startswith("    1  finger-ridges")
    assert out.splitlines()[1].startswith("    2  refused")
    assert "2 photo(s) checked" in out
    assert NOTICE in out
    index = tmp_path / "TRIAGE.csv"
    assert main(["triage", str(small), "--to", str(index), "--json"]) == 0
    record = json.loads(capsys.readouterr().out)
    assert record["schema"] == SCHEMA
    assert record["index"] == {"path": str(index), "sha256": hashlib.sha256(index.read_bytes()).hexdigest()}
    assert main(["triage", str(small), "--to", str(index)]) == 1  # never replaced
    assert "already exists" in capsys.readouterr().err
    assert main(["triage", str(small), "--max-files", "1"]) == 1
    assert "the limit is 1" in capsys.readouterr().err
    assert main(["triage", str(small / "a.png")]) == 1
    assert "not a folder" in capsys.readouterr().err


def test_an_unreadable_file_and_a_link_become_rows(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "f"
    root.mkdir()
    (root / "a.png").write_bytes(b"not an image")
    (root / "b.png").write_bytes(b"not an image either")

    def denied(path: Path, max_bytes: int) -> bytes:
        if path.name == "b.png":
            raise PermissionError(13, "Permission denied")
        return read_bounded(path, max_bytes)

    monkeypatch.setattr(triage_module, "read_bounded", denied)
    try:
        (root / "c.png").symlink_to(root / "a.png")
    except OSError:  # creating links needs extra privileges on this system: the link row is then not checked
        linked = False
    else:
        linked = True
    rows = {row.file: row for row in triage_folder(root).rows}
    assert rows["a.png"].group == "refused"
    assert "not a supported image" in rows["a.png"].reason
    assert rows["b.png"].group == "refused"
    assert rows["b.png"].reason == "cannot be read (Permission denied)"
    assert rows["b.png"].size == len(b"not an image either")
    if linked:
        assert rows["c.png"].reason == "a link, not a regular file"
        assert rows["c.png"].size == 0


def test_the_sidecar_triages_a_folder_and_writes_the_index_only_where_asked(small: Path, tmp_path: Path) -> None:
    session = Session(keystore_factory=MemoryKeyStore)

    def rpc(method: str, params: dict[str, Any]) -> Any:
        message = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
        return json.loads(handle(json.dumps(message).encode(), session))

    record = rpc("folder.triage", {"path": str(small.resolve())})["result"]  # no case is unlocked
    assert record["schema"] == SCHEMA
    assert record["counts"] == {
        "finger-ridges": 1,
        "ridges-no-finger": 0,
        "finger-unclear": 0,
        "nothing": 0,
        "refused": 1,
    }
    assert [row["file"] for row in record["rows"]] == ["a.png", "b.png"]
    assert record["notice"] == NOTICE
    assert "index" not in record
    index = tmp_path / "phone-A-triage.csv"
    saved = rpc("folder.triage", {"path": str(small.resolve()), "recursive": True, "dest": str(index.resolve())})
    assert saved["result"]["index"] == {
        "path": str(index.resolve()),
        "sha256": hashlib.sha256(index.read_bytes()).hexdigest(),
    }
    assert saved["result"]["recursive"] is True
    refused = rpc("folder.triage", {"path": str(small.resolve()), "dest": str(index.resolve())})["error"]
    assert refused["code"] == -32000
    assert "already exists" in refused["message"]
    assert rpc("folder.triage", {"path": "phone-A"})["error"]["code"] == -32000  # relative paths are refused
    over = rpc("folder.triage", {"path": str(small.resolve()), "max_files": 1})["error"]
    assert over["code"] == -32001  # an input refused before any photo is read
    assert "the limit is 1" in over["message"]
    assert rpc("folder.triage", {"path": str(small.resolve()), "extra": 1})["error"]["code"] == -32602
    assert rpc("folder.triage", {"path": str(small.resolve()), "recursive": "yes"})["error"]["code"] == -32602
    assert sorted(p.name for p in small.iterdir()) == ["a.png", "b.png"]  # nothing written next to the photos
