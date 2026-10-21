"""The position a photo's metadata records, in decimal degrees, with a Google Maps link to it.

Coordinates are computed with exact rationals and rounded half-even to 7 decimal places (about
1 cm), so the same file gives the same text on every platform. Positions outside the valid
ranges, or without their N/S and E/W references, are not converted: the raw GPS group still
lists what was recorded. Ridge never opens the link; it is shown so the examiner can copy it.
"""

from __future__ import annotations

import datetime
import re
from collections.abc import Mapping, Sequence
from fractions import Fraction
from typing import Any

from ridge.metadata.values import number, text

DECIMALS = 7
MAP_URL = "https://www.google.com/maps/search/?api=1&query={lat}%2C{lon}"  # Google Maps URLs API
_WGS84 = re.compile(r"^\s*WGS[\s-]*(19)?84\s*$", re.IGNORECASE)
# At most 12 decimals (about 1 nm): longer digit strings are malformed, and Python refuses to convert
# integer strings over 4300 digits (ValueError), which must never reach Fraction().
_XMP_COORD = re.compile(r"^\s*(\d{1,3}),(\d{1,2}(?:\.\d{1,12})?)(?:,(\d{1,2}(?:\.\d{1,12})?))?\s*([NSEWnsew])\s*$")


def _fraction(value: Any) -> Fraction | None:
    """Return an EXIF rational (or number) as an exact Fraction, or None when undefined."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return Fraction(value)
    numerator, denominator = getattr(value, "numerator", None), getattr(value, "denominator", None)
    if isinstance(numerator, int) and isinstance(denominator, int) and denominator != 0:
        return Fraction(numerator, denominator)
    return None


def _ref(value: Any) -> str:
    if isinstance(value, bytes):
        value = value.decode("ascii", "replace")
    return value.strip("\x00 ").upper() if isinstance(value, str) else ""


def degrees(parts: Sequence[Any], ref: Any, limit: int, refs: str) -> tuple[Fraction | None, str]:
    """Signed degrees from EXIF [degrees, minutes, seconds] and its reference; None and a reason if unusable."""
    letter = _ref(ref)
    if letter not in set(refs):  # a set: "" or "NS" must not match as substrings of "NS"
        return None, f"its reference is {text(letter) or 'missing'}, not {' or '.join(refs)}"
    values = [_fraction(p) for p in parts] if isinstance(parts, tuple | list) else []
    if not 1 <= len(values) <= 3 or any(v is None or v < 0 for v in values):
        return None, "it is not 1-3 non-negative rationals"
    d, m, s = [*(v for v in values if v is not None), Fraction(0), Fraction(0)][:3]
    if m >= 60 or s >= 60:
        return None, "minutes or seconds are 60 or more"
    total = d + m / 60 + s / 3600
    if total > limit:
        return None, f"it is beyond {limit} degrees"
    return (-total if letter in {"S", "W"} else total), _dms(d, m, s, letter)


def _dms(d: Fraction, m: Fraction, s: Fraction, letter: str) -> str:
    return f"{number(d, 12)}° {number(m, 12)}' {number(s, 12)}\" {letter}"


def fixed(value: Fraction, places: int = DECIMALS) -> str:
    """`value` rounded half-even to `places` decimal places, as text."""
    scaled = round(value * 10**places)
    sign = "-" if scaled < 0 else ""
    whole, part = divmod(abs(scaled), 10**places)
    return f"{sign}{whole}.{part:0{places}d}"


def position(lat: Fraction, lon: Fraction, source: str, recorded: str) -> dict[str, Any]:
    """Build the location section: decimal degrees, the values as recorded and the map link."""
    lat_s, lon_s = fixed(lat), fixed(lon)
    return {
        "source": source,
        "latitude": float(lat_s),
        "longitude": float(lon_s),
        "recorded": recorded,
        "map_url": MAP_URL.format(lat=lat_s, lon=lon_s),
    }


def _real_date(match: re.Match[str]) -> bool:
    """Whether YYYY:MM:DD names a real calendar day (2024:13:40 and 2023:02:29 do not)."""
    try:
        datetime.date(int(match[1]), int(match[2]), int(match[3]))
    except ValueError:
        return False
    return True


def _time(gps: Mapping[int, Any]) -> str | None:
    """GPS date and time (UTC by definition) as ISO 8601, when both are recorded and valid."""
    date, clock = gps.get(29), gps.get(7)
    if not isinstance(date, str) or not isinstance(clock, tuple | list) or len(clock) != 3:
        return None
    match = re.fullmatch(r"(\d{4}):(\d{2}):(\d{2})", date.strip("\x00 "))
    hms = [_fraction(v) for v in clock]
    if match is None or not _real_date(match) or any(v is None or v < 0 for v in hms):
        return None
    h, m, s = (v for v in hms if v is not None)
    if h.denominator != 1 or m.denominator != 1 or h >= 24 or m >= 60 or s >= 61:
        return None
    whole, ms = divmod(round(s * 1000), 1000)  # milliseconds, rounded half-even
    seconds = f"{whole:02d}" + (f".{ms:03d}".rstrip("0") if ms else "")
    return f"{match[1]}-{match[2]}-{match[3]}T{int(h):02d}:{int(m):02d}:{seconds}Z"


def exif_location(gps: Mapping[int, Any], warnings: list[str]) -> dict[str, Any] | None:
    """Return the position in an EXIF GPS IFD, or None (with a warning when one is recorded but unusable)."""
    if 2 not in gps and 4 not in gps:
        return None
    lat, lat_text = degrees(gps.get(2, ()), gps.get(1), 90, "NS")
    lon, lon_text = degrees(gps.get(4, ()), gps.get(3), 180, "EW")
    if lat is None or lon is None:
        reason = lat_text if lat is None else lon_text
        which = "latitude" if lat is None else "longitude"
        warnings.append(
            f"The EXIF GPS position is recorded but not shown on a map: its {which} is unusable ({reason})."
        )
        return None
    found = position(lat, lon, "EXIF GPS", f"{lat_text}, {lon_text}")
    altitude = _fraction(gps.get(6))
    if altitude is not None:
        below = gps.get(5) in (1, 3, b"\x01", b"\x03")
        found["altitude_m"] = float(fixed(-altitude if below else altitude, 2))
    if (moment := _time(gps)) is not None:
        found["time_utc"] = moment
    datum = gps.get(18)
    if isinstance(datum, str) and datum.strip("\x00 "):
        found["datum"] = text(datum)
        if not _WGS84.match(datum.strip("\x00")):
            warnings.append(
                f"The GPS position uses the map datum {text(datum)!r}; Google Maps uses WGS 84, so the link can be off."
            )
    error = _fraction(gps.get(31))
    if error is not None:
        found["horizontal_error_m"] = float(fixed(error, 2))
    _null_island(lat, lon, warnings)
    return found


def xmp_location(lat_text: str | None, lon_text: str | None, warnings: list[str]) -> dict[str, Any] | None:
    """Return the position in XMP (exif:GPSLatitude "DDD,MM.mmk" or "DDD,MM,SSk"), or None."""
    if lat_text is None and lon_text is None:
        return None
    lat, lon = _xmp_coord(lat_text, 90, "NS"), _xmp_coord(lon_text, 180, "EW")
    if lat is None or lon is None:
        warnings.append("The XMP GPS position is recorded but not shown on a map: it is incomplete or malformed.")
        return None
    _null_island(lat, lon, warnings)
    return position(lat, lon, "XMP exif:GPSLatitude/GPSLongitude", f"{text(lat_text or '')}, {text(lon_text or '')}")


def _xmp_coord(value: str | None, limit: int, refs: str) -> Fraction | None:
    match = _XMP_COORD.match(value or "")
    if match is None:
        return None
    seconds = Fraction(match[3]) if match[3] is not None else Fraction(0)
    found, _ = degrees((Fraction(match[1]), Fraction(match[2]), seconds), match[4], limit, refs)
    return found


def _null_island(lat: Fraction, lon: Fraction, warnings: list[str]) -> None:
    if lat == 0 and lon == 0:
        warnings.append("The GPS position is 0, 0: devices often write this when they have no position fix.")


def compare(exif: dict[str, Any] | None, xmp: dict[str, Any] | None, warnings: list[str]) -> None:
    """Warn when EXIF and XMP both record a position and they differ (more than about 1 m)."""
    if exif is None or xmp is None:
        return
    if abs(exif["latitude"] - xmp["latitude"]) > 1e-5 or abs(exif["longitude"] - xmp["longitude"]) > 1e-5:
        warnings.append(
            "EXIF and XMP record different GPS positions; the EXIF one is shown "
            f"(XMP: {xmp['latitude']}, {xmp['longitude']})."
        )
