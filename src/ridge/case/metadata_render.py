"""The photo-metadata section of readable job reports (text and HTML), from a report's ``input.metadata``.

Values were made display-safe when they were read (`ridge.metadata.values`); the HTML renderer
escapes them again. The map link is rebuilt from the recorded numbers, never taken from the
report as text, and is only a link: Ridge does not open it, and the page loads nothing.
"""

from __future__ import annotations

from html import escape
from typing import Any

from ridge.metadata.gps import MAP_URL

NOT_RECORDED = "not recorded in this report"
DISCLOSURE = "Ridge never opens this link. Opening it sends the recorded position to Google."


def _coordinate(value: object, limit: int) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float) or not -limit <= value <= limit:
        return None
    return float(value)


def map_url(location: dict[str, Any] | None) -> str | None:
    """Return the Google Maps link for a recorded position, or None when the numbers are missing or out of range."""
    if not isinstance(location, dict):
        return None
    lat, lon = _coordinate(location.get("latitude"), 90), _coordinate(location.get("longitude"), 180)
    if lat is None or lon is None:
        return None
    return MAP_URL.format(lat=f"{lat:.7f}", lon=f"{lon:.7f}")


def location_text(location: dict[str, Any]) -> str:
    """One line: decimal degrees, source, the values as recorded, altitude and GPS time."""
    extra = [
        f"altitude {location['altitude_m']:g} m" if isinstance(location.get("altitude_m"), int | float) else "",
        f"GPS time {location['time_utc']}" if location.get("time_utc") else "",
        f"datum {location['datum']}" if location.get("datum") else "",
        f"horizontal error {location['horizontal_error_m']:g} m"
        if isinstance(location.get("horizontal_error_m"), int | float)
        else "",
    ]
    tail = "".join(f", {e}" for e in extra if e)
    return (
        f"{location.get('latitude')}, {location.get('longitude')} "
        f"({location.get('source')}; recorded {location.get('recorded')}){tail}"
    )


def _named(entry: dict[str, Any]) -> str:
    return f"{entry.get('name')} ({entry['id']})" if entry.get("id") else str(entry.get("name"))


def metadata_text(meta: dict[str, Any] | None) -> list[str]:
    """Text-report lines for the photo metadata (every entry), labelled like the other report lines."""
    if not isinstance(meta, dict):
        return [f"Photo metadata {NOT_RECORDED}"]
    lines = ["Photo metadata", f"  {meta.get('notice', '')}"]
    location = meta.get("location")
    if isinstance(location, dict):
        lines.append(f"Location      {location_text(location)}")
        url = map_url(location)
        lines.append(f"Map link      {url or 'not available'}")
        if url:
            lines.append(f"              {DISCLOSURE}")
    else:
        lines.append("Location      none recorded")
    lines.extend(f"  {e.get('name')}: {e.get('value')}" for e in meta.get("summary") or [])
    for group in meta.get("groups") or []:
        lines.append(f"[{group.get('title')}]")
        lines.extend(f"  {_named(e)}: {e.get('value')}" for e in group.get("entries") or [])
    lines.extend(f"Embedded      {embedded_text(e)}" for e in meta.get("embedded") or [])
    lines.extend(f"Note          {w}" for w in meta.get("warnings") or [])
    return lines


def embedded_text(item: dict[str, Any]) -> str:
    """Describe an embedded image (such as the EXIF thumbnail) by kind, size and hash; never its pixels."""
    size = item.get("size_px")
    parts = [
        str(item.get("kind")),
        f"{item.get('format')} {size[0]} x {size[1]} px" if isinstance(size, list) and len(size) == 2 else "",
        f"{item['bytes']:,} bytes" if isinstance(item.get("bytes"), int) else "",
        str(item.get("sha256") or ""),
        str(item.get("note") or ""),
    ]
    return ", ".join(p for p in parts if p)


def _table(entries: list[dict[str, Any]], *, ids: bool) -> str:
    head = (
        '<tr><th scope="col">Name</th>'
        + ('<th scope="col">Tag</th>' if ids else "")
        + '<th scope="col">Value</th></tr>'
    )
    rows = "".join(
        f"<tr><td>{escape(str(e.get('name')))}</td>"
        + (f"<td><code>{escape(str(e.get('id') or ''))}</code></td>" if ids else "")
        + f"<td>{escape(str(e.get('value')))}</td></tr>"
        for e in entries
    )
    return f'<table class="meta">{head}{rows}</table>'


def provenance_html(section: dict[str, Any] | None) -> str:
    """Render the provenance hints (FR-42) as their own section; empty for reports made before them."""
    if not isinstance(section, dict):
        return ""
    hints = section.get("hints") or []
    items = "".join(f"<li>{escape(str(h.get('text')))}</li>" for h in hints) or "<li>none</li>"
    return f"<h3>Provenance hints</h3><p>{escape(str(section.get('notice', '')))}</p><ul>{items}</ul>"


def metadata_html(meta: dict[str, Any] | None) -> str:
    """Render the HTML section for the photo metadata: location with its map link, summary, every group."""
    if not isinstance(meta, dict):
        return f"<h2>Photo metadata</h2><p>{escape(NOT_RECORDED.capitalize())}.</p>"
    parts = ["<h2>Photo metadata</h2>", f"<p>{escape(str(meta.get('notice', '')))}</p>"]
    location = meta.get("location")
    if isinstance(location, dict):
        url = map_url(location)
        link = (
            f'<a href="{escape(url, quote=True)}" rel="noopener noreferrer" referrerpolicy="no-referrer">'
            f"Google Maps</a> <code>{escape(url)}</code><br>{escape(DISCLOSURE)}"
            if url
            else "not available"
        )
        parts.append(
            "<h3>Location</h3><table>"
            f'<tr><th scope="row">Position</th><td>{escape(location_text(location))}</td></tr>'
            f'<tr><th scope="row">Map link</th><td>{link}</td></tr></table>'
        )
    else:
        parts.append("<h3>Location</h3><p>None recorded.</p>")
    if meta.get("summary"):
        parts.append("<h3>Summary</h3>" + _table(meta["summary"], ids=False))
    for group in meta.get("groups") or []:
        entries = group.get("entries") or []
        has_ids = any(e.get("id") for e in entries)
        parts.append(f"<h3>{escape(str(group.get('title')))}</h3>" + _table(entries, ids=has_ids))
    if meta.get("embedded"):
        items = "".join(f"<li>{escape(embedded_text(e))}</li>" for e in meta["embedded"])
        parts.append(f"<h3>Embedded images</h3><p>Recorded by size and hash only.</p><ul>{items}</ul>")
    if meta.get("warnings"):
        items = "".join(f"<li>{escape(str(w))}</li>" for w in meta["warnings"])
        parts.append(f"<h3>Notes on reading</h3><ul>{items}</ul>")
    return "\n".join(parts)
