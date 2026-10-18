"""A readable HTML rendering of a verified processing record, for the DPO or a court (PRIV-3).

Made only after the record verified (`check_exported_log`). Like the readable report it escapes
every value, carries a Content-Security-Policy that allows no scripts or embedded content, holds
no images and says that the signed JSON stays authoritative.
"""

from __future__ import annotations

from collections.abc import Callable
from html import escape
from pathlib import Path
from typing import Any

from ridge.case.crypto import sha256_hex
from ridge.case.processing_record import MAX_RECORD_BYTES, LogCheck, parse_record, verify_record
from ridge.case.report_html import BANNER, CSP, STYLE
from ridge.case.reports import printable
from ridge.image_io import publish, read_bounded

_DETAILS = ("label", "source", "text", "reason", "destination", "error", "package_id", "format")


def _t(value: object) -> str:
    return escape(printable(value))


def _details(entry: dict[str, Any]) -> str:
    parts = [f"job {_t(str(entry['job_id'])[:8])}"] if entry.get("job_id") else []
    if entry.get("sha256"):
        parts.append(f"<code>{_t(str(entry['sha256'])[:16])}</code>")
    if isinstance(entry.get("legal_hold"), bool):
        parts.append("hold placed" if entry["legal_hold"] else "hold lifted")
    for key in _DETAILS:
        value = entry.get(key)
        if isinstance(value, str) and value:
            text = value if len(value) <= 300 else value[:297] + "..."
            parts.append(f"{key}: " + "<br>".join(_t(line) for line in text.splitlines()))
    return " · ".join(parts)


def render_record_html(record: dict[str, Any], check: LogCheck, data: bytes) -> str:
    """Render a verified processing record (`data` are the file's bytes, named by their SHA-256)."""
    rows = "".join(
        f"<tr><td>{_t(e.get('seq'))}</td><td>{_t(e.get('ts_utc'))}</td><td>{_t(e.get('actor'))}</td>"
        f"<td><code>{_t(e.get('action'))}</code>{' (failed)' if e.get('result') == 'failed' else ''}</td>"
        f"<td>{_details(e)}</td></tr>"
        for e in record.get("entries") or []
        if isinstance(e, dict)
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="{CSP}">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Ridge processing record {_t(check.case_id[:8])}</title><style>{STYLE}
th {{ width: auto; }}</style></head>
<body>
<h1>Ridge processing record</h1>
<p class="banner">{BANNER}</p>
<table>
<tr><th scope="row">Case</th><td><code>{_t(check.case_id)}</code></td></tr>
<tr><th scope="row">Exported (UTC)</th><td>{_t(check.exported_utc)}</td></tr>
<tr><th scope="row">Entries</th><td>{check.entries}, {check.signed_heads} signed head(s), chain verified</td></tr>
<tr><th scope="row">Signed with key</th><td><code>{_t(check.key_id)}</code></td></tr>
</table>
<h2>Custody entries</h2>
<table><tr><th scope="col">#</th><th scope="col">Time (UTC)</th><th scope="col">Examiner</th>
<th scope="col">Action</th><th scope="col">Details</th></tr>{rows}</table>
<footer>This page renders the processing record whose SHA-256 is <code>{sha256_hex(data)}</code>.
The signed JSON record is authoritative; verify it with <code>ridge-case check-log</code>.
This page is not signed.</footer>
</body></html>
"""


def write_record_html(
    path: Path,
    dest: Path,
    *,
    expected_key_id: str | None = None,
    confirm: Callable[[LogCheck], object] | None = None,
) -> LogCheck:
    """Verify an exported processing record, then write its readable copy (never over a file).

    `confirm` (for example the key-register check) runs after verification and before anything is
    written; when it raises, no copy exists.
    """
    data = read_bounded(path, MAX_RECORD_BYTES)
    record = parse_record(data)
    check, _ = verify_record(record, expected_key_id=expected_key_id)
    if confirm is not None:
        confirm(check)
    publish(dest, render_record_html(record, check, data).encode("utf-8"))
    return check
