"""An AFIS submission cover sheet for one job (PRD FR-38): the facts an operator needs, no images.

The sheet is a self-contained HTML page like the readable report: every value escaped, a
Content-Security-Policy that allows no scripts, network or images, not signed, naming the signed
report it comes from. It lists the submission record, the exports to attach with their stored
SHA-256 (so received files can be checked), their resolution, scale method and uncertainty, the
transforms, the indicative NFIQ 2 score and the limits-of-use outcome. Writing it is logged as
``cover.export`` with the page's SHA-256.
"""

from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any

from ridge.case.case_model import publish_logged
from ridge.case.crypto import sha256_hex
from ridge.case.report_html import BANNER, CSP, STYLE
from ridge.case.report_lines import export_line, nfiq2_line, resolution_note_line, scale_notice_line
from ridge.case.reports import SignedReport, load_report, printable
from ridge.case.store import OpenCase
from ridge.case.submission import Submission, submission_record
from ridge.errors import OutputExistsError

LABEL_WIDTH = 14  # the text renderer's label column
OLDER = "not recorded (report made before submission records)"


def _text(value: object) -> str:
    return escape(printable(value))


def _code(value: object) -> str:
    return f"<code>{escape(printable(value))}</code>"


def _rows(rows: list[tuple[str, str]]) -> str:
    body = "".join(f'<tr><th scope="row">{escape(k)}</th><td>{v}</td></tr>' for k, v in rows if v)
    return f"<table>{body}</table>"


def _value(line: str) -> str:
    return line[LABEL_WIDTH:].strip() if len(line) > LABEL_WIDTH else line.strip()


def _submission_rows(report: dict[str, Any]) -> list[tuple[str, str]]:
    section = report.get("submission")
    if not section:  # a report signed before the record existed: say so rather than guess
        section = {**submission_record(Submission(), None), "finger": OLDER}
    device = section.get("capture_device") or "none named in the file"
    return [
        ("Finger position", _text(f"{section.get('finger_position')}: {section.get('finger')}")),
        ("Source agency", _text(section.get("source_agency") or "not stated")),
        ("Impression", _text(section.get("impression"))),
        ("Capture device", _text(f"{device} ({section.get('capture_device_note')})")),
    ]


KINDS = {
    "export-gray": "Grayscale comparison export (recommended for AFIS)",
    "export": "Binary comparison export",
}


def _file_row(output: dict[str, Any]) -> tuple[str, str]:
    detail = f"{_text(output.get('label'))} · {_code(output.get('sha256'))} · {_text(output.get('size'))} bytes"
    return KINDS[str(output.get("role"))], detail


def _limits_row(limits: dict[str, Any]) -> tuple[str, str]:
    if limits.get("within"):
        state = "within the limits of use"
    else:
        state = "outside the limits of use: " + "; ".join(limits.get("warnings") or [])
    return "Limits of use", _text(f"{limits.get('source')}: {state}")


def _file_rows(report: dict[str, Any]) -> list[tuple[str, str]]:
    export = report.get("export") or {}
    rows = [_file_row(o) for o in report.get("outputs") or [] if o.get("role") in KINDS]
    rows.append(("Export", _text(_value(export_line(export)).replace("+-", "±")) if export else _text("not produced")))
    rows.append(("Scale notice", _text(_value(scale_notice_line(export)).replace("+-", "±"))))
    rows.append(("Resolution", _text(_value(resolution_note_line(export)))))
    rows.append(("NFIQ 2", _text(_value(nfiq2_line((report.get("quality") or {}).get("nfiq2")))) or "not computed"))
    limits = report.get("limits_of_use") or {}
    if limits.get("configured"):
        rows.append(_limits_row(limits))
    return rows


def render_cover_sheet(signed: SignedReport) -> str:
    """Render the cover sheet for a verified report (no scripts, no images, not signed)."""
    report = signed.report
    env, source = report.get("ridge") or {}, report.get("input") or {}
    head = [
        ("Case reference", _text(report.get("case_reference"))),
        ("Job", _code(report.get("job_id"))),
        ("Created (UTC)", _text(report.get("created_utc"))),
        ("Processed with", _text(f"Ridge {env.get('version')} on {env.get('platform')} ({env.get('machine')})")),
        ("Examiner key", _code(signed.key_id)),
        ("Source photo", f"{_text(source.get('label'))} · {_code(source.get('sha256'))}"),
        ("Source note", _text(source.get("source")) if source.get("source") else ""),
    ]
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="{CSP}">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Ridge submission cover sheet {escape(signed.job_id[:8])}</title><style>{STYLE}</style></head>
<body>
<h1>Ridge submission cover sheet</h1>
<p class="banner">{BANNER}</p>
<p>For the AFIS operator: the files named below are processed images for comparison, derived from a
photograph. Check each received file against its SHA-256; a file converted on export (TIFF, BMP) has
its own hash, recorded in the case's custody log next to the stored hash. The finger position and the
source agency are the examiner's statements. The impression type code is set by the operator.</p>
<h2>Case and job</h2>{_rows(head)}
<h2>Submission record</h2>{_rows(_submission_rows(report))}
<h2>Files to attach</h2>{_rows(_file_rows(report))}
<p>{_text(report.get("disclaimer", ""))}</p>
<footer>This sheet is derived from the signed report whose SHA-256 is {_code(sha256_hex(signed.canonical))}
(custody head {_code(report.get("custody_head"))}). It is not signed; verify the report with
<code>ridge-case check-report</code>.</footer>
</body></html>
"""


def export_cover_sheet(case: OpenCase, store: Path, ref: str, dest: Path, *, overwrite: bool = False) -> SignedReport:
    """Write the cover sheet of a checked report (logged as ``cover.export`` with the page's SHA-256)."""
    signed = load_report(case, store, ref, log=False)
    if not overwrite and dest.exists():
        raise OutputExistsError(f"{dest.name} already exists (use --overwrite to replace)")
    page = render_cover_sheet(signed).encode("utf-8")
    publish_logged(
        [(dest, page)],
        lambda: case.entries.append(
            case.custody.append(
                "cover.export", job_id=signed.job_id, sha256=sha256_hex(page), destination=str(dest.resolve())
            )
        ),
        overwrite=overwrite,
    )
    return signed
