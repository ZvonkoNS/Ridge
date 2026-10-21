"""Hostile metadata (ASVS V5 file handling; CWE-20, CWE-150, CWE-400, CWE-611, CWE-776, CVE-2021-42574).

Metadata is attacker-controlled. Whatever a file holds, reading it must only give a bounded,
display-safe record or one of Ridge's typed errors: no entity expansion, no file read through an
external entity, no hidden characters reaching the screen, no unbounded output.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from PIL import Image

from ridge.errors import DecodeError, InputRejectedError
from ridge.metadata import read_metadata
from ridge.metadata.values import MAX_ENTRIES, MAX_TOTAL_BYTES, MAX_VALUE_BYTES, Budget, as_text, describe, text
from ridge.metadata.xmp import MAX_XMP_BYTES
from tests import metadata_samples as samples

BOUND = MAX_TOTAL_BYTES * 3  # JSON of a full record: values, names, escaping and the fixed groups
# Bidirectional override and isolate, zero-width space, byte order mark, Arabic letter mark, ESC, BEL
HIDDEN = tuple(chr(c) for c in (0x202E, 0x2066, 0x200B, 0xFEFF, 0x061C, 0x1B, 0x07))


def test_an_entity_bomb_in_xmp_is_refused_not_expanded() -> None:
    bomb = (
        '<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaaaaaaaa">'
        + "".join(f'<!ENTITY {chr(98 + i)} "{("&" + chr(97 + i) + ";") * 10}">' for i in range(8))
        + ']><x:xmpmeta xmlns:x="adobe:ns:meta/">&i;</x:xmpmeta>'
    ).encode()
    meta = read_metadata(samples.jpeg(xmp_packet=bomb, icc=False))
    assert any("refuses" in w for w in meta["warnings"])
    raw = next(g for g in meta["groups"] if g["id"] == "xmp")["entries"]
    assert [e["name"] for e in raw] == ["XMP packet (raw text)"]
    assert len(json.dumps(meta)) < 20_000  # 10**9 characters were it expanded


def test_an_external_entity_is_never_resolved(tmp_path: Path) -> None:
    secret = tmp_path / "secret.txt"
    secret.write_text("TOP-SECRET-MARKER", encoding="utf-8")
    packet = (
        f'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY e SYSTEM "{secret.as_uri()}">]>'
        '<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
        '<rdf:Description xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:source>&e;</dc:source>'
        "</rdf:Description></rdf:RDF></x:xmpmeta>"
    ).encode()
    meta = read_metadata(samples.jpeg(xmp_packet=packet, icc=False))
    assert "TOP-SECRET-MARKER" not in json.dumps(meta)
    assert any("refuses" in w for w in meta["warnings"])


def test_malformed_xmp_is_listed_as_raw_text() -> None:
    meta = read_metadata(samples.jpeg(xmp_packet=b"<x:xmpmeta><unclosed>", icc=False))
    entries = next(g for g in meta["groups"] if g["id"] == "xmp")["entries"]
    assert entries == [{"name": "XMP packet (raw text)", "value": "<x:xmpmeta><unclosed>"}]


@pytest.mark.parametrize("hidden", HIDDEN)
def test_hidden_and_control_characters_are_made_visible(hidden: str) -> None:
    exif = Image.Exif()
    exif[0x010F] = f"Camera{hidden}Co"
    meta = read_metadata(samples.jpeg(exif, xmp_packet=samples.xmp(attrs=f'xmp:CreatorTool="T{hidden}x"'), icc=False))
    shown = json.dumps(meta, ensure_ascii=False)
    assert hidden not in shown
    assert f"<U+{ord(hidden):04X}>" in shown


def test_text_keeps_ordinary_text_and_marks_the_rest() -> None:
    assert text("line one\nline two\ttab\r\n") == "line one line two tab "
    assert text("ok\x00\x00") == "ok"
    assert text("a\x00b") == "a<U+0000>b"
    assert text("ščž 日本") == "ščž 日本"
    assert as_text(b"\x01\x02abc") is None
    assert as_text(b"") is None
    assert describe(b"\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f\x10").startswith(
        "binary data, 17 bytes, sha256:"
    )
    assert describe((1, 2, 3)) == "1, 2, 3"
    assert describe(list(range(40))).endswith("... (40 values in all)")


def test_a_long_value_is_shortened_and_counted() -> None:
    exif = Image.Exif()
    exif[0x013B] = "A" * 100_000  # Artist; a PNG, because JPEG limits EXIF to 64 KiB
    meta = read_metadata(samples.png(exif=exif))
    artist = next(e for g in meta["groups"] for e in g["entries"] if e["name"] == "Artist")
    assert len(artist["value"].encode()) <= MAX_VALUE_BYTES
    assert artist["value"].endswith("(shortened: 100,000 characters in all)")
    assert any("long values were shortened" in w for w in meta["warnings"])


def test_thousands_of_entries_are_capped() -> None:
    props = " ".join(f'xmp:P{i}="v"' for i in range(MAX_ENTRIES + 500))
    meta = read_metadata(samples.png(xmp_packet=samples.xmp(attrs=props)))
    assert meta["truncated"] is True
    assert sum(len(g["entries"]) for g in meta["groups"] if g["id"] != "file") <= MAX_ENTRIES
    assert any("entries were left out" in w for w in meta["warnings"])
    assert len(json.dumps(meta)) < BOUND


def test_the_byte_budget_bounds_the_record() -> None:
    props = " ".join(f'xmp:P{i}="{"v" * 1500}"' for i in range(400))  # 600 kB of values
    meta = read_metadata(samples.png(xmp_packet=samples.xmp(attrs=props)))
    assert meta["truncated"] is True
    assert len(json.dumps(meta)) < BOUND


def test_a_huge_xmp_packet_is_not_parsed() -> None:
    packet = samples.xmp(body="<x:y>" + "z" * (MAX_XMP_BYTES + 10) + "</x:y>")
    meta = read_metadata(samples.png(xmp_packet=packet))
    entries = next(g for g in meta["groups"] if g["id"] == "xmp")["entries"]
    assert entries[0]["value"].startswith("XMP packet, not parsed, ")
    assert any("was not parsed" in w for w in meta["warnings"])


def test_a_corrupt_exif_block_is_reported_not_fatal() -> None:
    data = samples.with_segment(samples.jpeg(icc=False), 0xE1, b"Exif\x00\x00MM\x00*\x00\x00\x00\x08\xff\xff")
    meta = read_metadata(data)
    assert meta["groups"][0]["id"] == "file"
    assert meta["location"] is None


def test_budget_stops_at_the_entry_limit() -> None:
    budget = Budget()
    kept = [budget.entry("n", "v") for _ in range(MAX_ENTRIES + 3)]
    assert sum(e is not None for e in kept) == MAX_ENTRIES
    assert budget.dropped == 3


@pytest.mark.parametrize("data", [b"", b"not an image", b"%PDF-1.7 synthetic"])
def test_what_is_not_an_allowed_image_is_refused(data: bytes) -> None:
    with pytest.raises(InputRejectedError):
        read_metadata(data)


FULL = samples.full_jpeg()


@settings(max_examples=300, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(st.lists(st.tuples(st.integers(0, len(FULL) - 1), st.integers(0, 255)), min_size=1, max_size=12))
def test_mutated_metadata_never_escapes_typed_errors_or_bounds(changes: list[tuple[int, int]]) -> None:
    data = bytearray(FULL)
    for at, value in changes:
        data[at] = value
    try:
        meta = read_metadata(bytes(data))
    except (InputRejectedError, DecodeError):
        return
    shown = json.dumps(meta, ensure_ascii=False)
    assert len(shown) < BOUND
    assert not any(h in shown for h in HIDDEN[:2])
