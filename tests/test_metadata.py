"""Photo metadata (FR-36): every block Ridge reads, the location and its map link, on synthetic files."""

from __future__ import annotations

import json
from fractions import Fraction
from typing import Any

import pytest
import rfc8785

from ridge.image_io import HEIF_AVAILABLE
from ridge.metadata import NOTICE, SCHEMA, read_metadata
from ridge.metadata.gps import fixed
from tests import metadata_samples as samples
from tests.metadata_samples import MAP_URL, R


def group(meta: dict[str, Any], ident: str) -> dict[str, str]:
    """A group's entries as name -> value (the first of repeated names)."""
    found = next(g for g in meta["groups"] if g["id"] == ident)
    entries: dict[str, str] = {}
    for e in found["entries"]:
        entries.setdefault(e["name"], e["value"])
    return entries


def ids(meta: dict[str, Any]) -> list[str]:
    return [g["id"] for g in meta["groups"]]


def test_a_camera_jpeg_gives_location_summary_and_every_group() -> None:
    meta = read_metadata(samples.full_jpeg())
    assert meta["schema"] == SCHEMA
    assert meta["notice"] == NOTICE
    assert ids(meta) == ["file", "exif-ifd0", "exif-photo", "exif-gps", "xmp", "icc", "jpeg"]  # no IPTC block
    assert meta["location"] == {
        "source": "EXIF GPS",
        "latitude": 46.0512333,
        "longitude": 14.5056778,
        "recorded": "46° 3' 4.44\" N, 14° 30' 20.44\" E",
        "map_url": MAP_URL,
        "altitude_m": 295.3,
        "time_utc": "2024-05-01T08:22:33.5Z",
        "datum": "WGS-84",
    }
    summary = {e["name"]: e["value"] for e in meta["summary"]}
    assert summary == {
        "Camera": "Synthetic Camera Co Model 7",
        "Software": "Firmware 1.2",
        "Camera serial number": "SN-0001",
        "Taken (camera clock)": "2024:05:01 10:22:33.123 +02:00",
        "Exposure": "1/120 s, f/1.8, ISO 100, 4.2 mm (26 mm in 35 mm film)",
        "Created with (XMP)": "Synthetic Editor 3",
    }
    assert meta["truncated"] is False
    assert meta["entries"] == sum(len(g["entries"]) for g in meta["groups"]) + len(meta["summary"])


def test_exif_values_are_shown_in_words_where_exif_defines_them() -> None:
    meta = read_metadata(samples.full_jpeg())
    ifd0, photo, gps = group(meta, "exif-ifd0"), group(meta, "exif-photo"), group(meta, "exif-gps")
    assert ifd0["Orientation"] == "6 (rotate 90 CW)"
    assert photo["ExifVersion"] == "0232 (version 2.32)"
    assert photo["Flash"] == "16 (did not fire, compulsory flash suppression)"
    assert photo["ExposureTime"] == "0.008333333333 (1/120)"
    assert photo["FNumber"] == "1.8"
    assert photo["UserComment"] == "synthetic comment"
    assert gps["GPSVersionID"] == "2.3.0.0"
    assert gps["GPSAltitudeRef"] == "0 (above sea level)"
    assert gps["GPSLatitude"] == "46, 3, 4.44"
    tags = {e["name"]: e["id"] for g in meta["groups"] if g["id"] == "exif-ifd0" for e in g["entries"]}
    assert tags["Make"] == "0x010F"
    assert "ExifOffset" not in ifd0
    assert "GPSInfo" not in ifd0  # links to other IFDs are structure, not values


def test_the_makernote_is_summarised_by_size_and_hash_never_copied() -> None:
    meta = read_metadata(samples.full_jpeg())
    note = group(meta, "exif-photo")["MakerNote"]
    assert note.startswith("vendor-specific data starting 'SynthMaker', not decoded, 54 bytes, sha256:")
    assert any("MakerNote" in w for w in meta["warnings"])


def test_xmp_properties_lists_and_edit_history_are_flattened() -> None:
    xmp = group(read_metadata(samples.full_jpeg()), "xmp")
    assert xmp["xmp:CreatorTool"] == "Synthetic Editor 3"
    assert xmp["dc:subject"] == "finger; test"
    assert xmp["dc:title"] == "Title; sl: Naslov"
    assert xmp["xmpMM:History[1]/stEvt:action"] == "saved"
    assert xmp["xmpMM:History[1]/stEvt:softwareAgent"] == "Synthetic Editor 3"


def test_icc_jpeg_structure_and_comment() -> None:
    meta = read_metadata(samples.full_jpeg())
    icc = group(meta, "icc")
    assert icc["Description"] == "sRGB built-in"
    assert icc["Class"] == "display device"
    assert icc["Colour space"] == "RGB"
    assert icc["Profile"].startswith("ICC profile, ")
    jpeg = [e for g in meta["groups"] if g["id"] == "jpeg" for e in g["entries"]]
    assert [e["name"] for e in jpeg] == ["APP0", "APP1", "APP1", "APP2", "Comment (COM)"]
    assert jpeg[1]["value"].startswith("Exif, ")
    assert jpeg[2]["value"].startswith("http://ns.adobe.com/xap/1.0/, ")
    assert jpeg[4]["value"] == "synthetic comment segment"
    files = group(meta, "file")
    assert files["Format"] == "JPEG (image/jpeg)"
    assert files["Stored size"] == "64 x 48 px (before EXIF orientation)"
    assert files["Resolution"] == "72 x 72 dpi (declared in the file, not a measured scale)"


def test_the_same_bytes_give_the_same_canonical_record() -> None:
    data = samples.full_jpeg()
    first, second = read_metadata(data), read_metadata(data)
    assert rfc8785.dumps(first) == rfc8785.dumps(second)  # deterministic and canonicalisable


@pytest.mark.parametrize(
    ("lat_ref", "lon_ref", "alt_ref", "expected"),
    [("S", "W", b"\x01", (-46.0512333, -14.5056778, -295.3)), ("N", "W", b"\x00", (46.0512333, -14.5056778, 295.3))],
)
def test_hemispheres_and_below_sea_level(
    lat_ref: str, lon_ref: str, alt_ref: bytes, expected: tuple[float, ...]
) -> None:
    exif = samples.camera_exif(t1=lat_ref, t3=lon_ref, t5=alt_ref)
    location = read_metadata(samples.jpeg(exif))["location"]
    assert (location["latitude"], location["longitude"], location["altitude_m"]) == expected
    assert location["map_url"].endswith(f"query={expected[0]:.7f}%2C{expected[1]:.7f}")


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"t1": None}, "reference is missing"),
        ({"t1": "NS"}, "reference is NS"),
        ({"t3": "X"}, "reference is X"),
        ({"t2": (R(46, 1), R(60, 1), R(0, 1))}, "minutes or seconds are 60 or more"),
        ({"t2": (R(91, 1), R(0, 1), R(0, 1))}, "beyond 90 degrees"),
        ({"t4": (R(14, 1), R(30, 0), R(0, 1))}, "not 1-3 non-negative rationals"),
        ({"t4": (R(181, 1), R(0, 1), R(0, 1))}, "beyond 180 degrees"),
    ],
)
def test_an_unusable_position_is_listed_but_not_mapped(overrides: dict[str, Any], reason: str) -> None:
    meta = read_metadata(samples.jpeg(samples.camera_exif(**overrides)))
    assert meta["location"] is None
    assert any("not shown on a map" in w and reason in w for w in meta["warnings"]), meta["warnings"]
    assert "GPSLatitude" in group(meta, "exif-gps") or "GPSLongitude" in group(meta, "exif-gps")


def test_zero_zero_and_other_datums_are_flagged() -> None:
    zero = (R(0, 1), R(0, 1), R(0, 1))
    meta = read_metadata(samples.jpeg(samples.camera_exif(t2=zero, t4=zero, t18="Tokyo")))
    assert meta["location"]["latitude"] == 0.0
    assert any("0, 0" in w for w in meta["warnings"])
    assert any("datum 'Tokyo'" in w for w in meta["warnings"])


def test_optional_gps_fields_and_odd_times() -> None:
    exif = samples.camera_exif(t7=(R(25, 1), R(0, 1), R(0, 1)), t31=R(5, 1))
    location = read_metadata(samples.jpeg(exif))["location"]
    assert "time_utc" not in location  # hour 25 is not a time
    assert location["horizontal_error_m"] == 5.0
    bare = read_metadata(samples.jpeg(samples.camera_exif(t5=None, t6=None, t7=None, t18=None, t29=None)))
    assert set(bare["location"]) == {"source", "latitude", "longitude", "recorded", "map_url"}


def test_xmp_gps_is_used_when_exif_has_none_and_a_difference_is_reported() -> None:
    attrs = 'xmp:CreatorTool="Tool" exif:GPSLatitude="46,3.074N" exif:GPSLongitude="14,30,20.44E"'
    no_gps = samples.camera_exif(t1=None, t2=None, t3=None, t4=None)
    meta = read_metadata(samples.jpeg(no_gps, xmp_packet=samples.xmp(attrs=attrs)))
    assert meta["location"]["source"] == "XMP exif:GPSLatitude/GPSLongitude"
    assert meta["location"]["latitude"] == pytest.approx(46.0512333, abs=1e-7)
    both = read_metadata(
        samples.jpeg(samples.camera_exif(), xmp_packet=samples.xmp(attrs=attrs.replace("46,3", "47,3")))
    )
    assert both["location"]["source"] == "EXIF GPS"
    assert any("different GPS positions" in w for w in both["warnings"])
    bad = read_metadata(samples.jpeg(no_gps, xmp_packet=samples.xmp(attrs='exif:GPSLatitude="north"')))
    assert bad["location"] is None
    assert any("XMP GPS position" in w for w in bad["warnings"])


def test_the_exif_thumbnail_is_recorded_by_hash_and_size_never_its_pixels() -> None:
    thumb = samples.thumbnail_jpeg()
    meta = read_metadata(samples.jpeg(samples.raw_exif_with_thumbnail(thumb), icc=False))
    [embedded] = meta["embedded"]
    assert embedded["kind"] == "EXIF thumbnail"
    assert embedded["size_px"] == [16, 12]
    assert embedded["bytes"] == len(thumb)
    assert embedded["sha256"].startswith("sha256:")
    text = json.dumps(meta)
    assert thumb.hex() not in text
    assert thumb[20:60].hex() not in text
    assert group(meta, "exif-ifd1")["Compression"] == "6 (JPEG (old-style))"
    bad = read_metadata(samples.jpeg(samples.raw_exif_with_thumbnail(offset_shift=10_000), icc=False))
    assert bad["embedded"] == [{"kind": "EXIF thumbnail", "note": "its offset or length points outside the EXIF block"}]


def test_iptc_datasets_are_named_and_utf8_is_honoured() -> None:
    meta = read_metadata(samples.iptc_jpeg())
    iptc = group(meta, "iptc")
    assert iptc["Object name"] == "Predmet št. 12"
    assert iptc["Keywords"] == "finger, synthetic"
    assert iptc["By-line (creator)"] == "Examiner A"
    assert iptc["Dataset 2:200"] == "custom"
    jpeg = group(meta, "jpeg")
    assert jpeg["APP13"].startswith("Photoshop 3.0, ")


def test_png_text_exif_and_xmp() -> None:
    data = samples.png(
        exif=samples.camera_exif(),
        texts={"Comment": "plain", "Description": "čez"},
        xmp_packet=samples.xmp(),
    )
    meta = read_metadata(data)
    assert meta["location"]["map_url"] == MAP_URL
    text = group(meta, "png-text")
    assert text == {"Comment": "plain", "Description": "čez"}  # the XMP packet is in its own group
    assert group(meta, "xmp")["xmp:CreatorTool"] == "Synthetic Editor 3"


def test_webp_and_tiff() -> None:
    webp = read_metadata(samples.save("WEBP", lossless=True, exif=samples.camera_exif(), xmp=samples.xmp()))
    assert webp["location"]["map_url"] == MAP_URL
    assert "xmp" in ids(webp)
    tiff = read_metadata(samples.save("TIFF", tiffinfo={0x010F: "Scanner Co", 700: samples.xmp()}))
    ifd0 = group(tiff, "exif-ifd0")
    assert ifd0["Make"] == "Scanner Co"
    assert ifd0["XMLPacket"].startswith("XMP packet (see XMP), ")
    assert group(tiff, "xmp")["xmp:CreatorTool"] == "Synthetic Editor 3"
    assert group(tiff, "file")["Format"] == "TIFF (image/tiff)"


@pytest.mark.skipif(not HEIF_AVAILABLE, reason="pillow-heif is not installed")
def test_heif() -> None:
    meta = read_metadata(samples.save("HEIF", quality=-1, exif=samples.camera_exif(), xmp=samples.xmp()))
    assert meta["location"]["map_url"] == MAP_URL
    heif = group(meta, "heif")
    assert heif["Primary image"] == "yes"
    assert "Thumbnails" in heif


def test_a_file_without_metadata_has_only_its_file_facts() -> None:
    meta = read_metadata(samples.save("BMP"))
    assert ids(meta) == ["file"]
    assert meta["location"] is None
    assert meta["summary"] == []
    assert meta["embedded"] == []
    assert meta["warnings"] == []


def test_fixed_rounds_half_even_to_seven_places() -> None:
    assert fixed(Fraction(5, 10**8)) == "0.0000000"  # half to even
    assert fixed(Fraction(15, 10**8)) == "0.0000002"
    assert fixed(Fraction(-1, 3)) == "-0.3333333"


@pytest.mark.parametrize(("day", "shown"), [("2024:13:40", False), ("2023:02:29", False), ("2024:02:29", True)])
def test_gps_time_needs_a_real_calendar_day(day: str, shown: bool) -> None:
    location = read_metadata(samples.jpeg(samples.camera_exif(t29=day)))["location"]
    assert ("time_utc" in location) is shown
    raw = group(read_metadata(samples.jpeg(samples.camera_exif(t29=day))), "exif-gps")
    assert raw["GPSDateStamp"] == day  # the raw tag stays listed either way
