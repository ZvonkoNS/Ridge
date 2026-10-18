"""A readable HTML rendering of a verified job report, for the case file or printing (FR-28).

The signed canonical JSON and its detached signature stay authoritative; the page says so and
names the SHA-256 of the JSON it renders. Every value is HTML-escaped and the page carries a
Content-Security-Policy that allows no scripts, no network and no embedded content, so a hostile
value in a report cannot do anything when the page is opened. The page holds no images.
"""

from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any

from ridge.case.crypto import sha256_hex
from ridge.case.limits import render_lines as render_limits
from ridge.case.reports import SignedReport, export_line, load_report, minutiae_line, nfiq2_line, printable
from ridge.case.store import OpenCase, publish_logged
from ridge.errors import OutputExistsError

_LABEL_WIDTH = 14  # the text renderer's label column; its helper lines start with it
CSP = "default-src 'none'; style-src 'unsafe-inline'; img-src 'none'; form-action 'none'; base-uri 'none'"
STYLE = """
body { font: 15px/1.5 system-ui, sans-serif; color: #1b1d21; background: #fff;
  margin: 2rem auto; max-width: 52rem; padding: 0 1rem; }
h1 { font-size: 1.4rem; margin: 0 0 .25rem; }
h2 { font-size: 1.05rem; margin: 1.5rem 0 .5rem; }
.banner { border: 2px solid #1b1d21; padding: .5rem .75rem; font-weight: 700; margin: 1rem 0; }
table { border-collapse: collapse; width: 100%; }
th, td { text-align: left; vertical-align: top; padding: .3rem .5rem; border-top: 1px solid #c3c7cd; }
th { width: 11rem; font-weight: 600; }
code { font: 13px ui-monospace, monospace; overflow-wrap: anywhere; }
footer { margin-top: 2rem; font-size: 13px; color: #474c54; }
""".strip()


def _value(line: str) -> str:
    """Return the value part of a text-renderer line ("Label         value")."""
    return line[_LABEL_WIDTH:].strip() if len(line) > _LABEL_WIDTH else line.strip()


def _rows(rows: list[tuple[str, str]]) -> str:
    body = "".join(f'<tr><th scope="row">{escape(k)}</th><td>{v}</td></tr>' for k, v in rows if v)
    return f"<table>{body}</table>"


def _code(value: object) -> str:
    return f"<code>{escape(printable(value))}</code>"


def _text(value: object) -> str:
    return escape(printable(value))


def _limits(section: dict[str, Any] | None) -> str:
    lines = render_limits(section)
    return "<br>".join(_text(_value(line)) for line in lines)


def render_report_html(signed: SignedReport) -> str:
    """Render a verified report as a self-contained HTML page (no scripts, no images)."""
    report = signed.report
    env, source = report.get("ridge") or {}, report.get("input") or {}
    params, meas = report.get("parameters") or {}, report.get("measurements") or {}
    size = source.get("size_px") or ["?", "?"]
    summary = [
        ("Case reference", _text(report.get("case_reference"))),
        ("Case", _code(report.get("case_id"))),
        ("Job", _code(report.get("job_id"))),
        ("Created (UTC)", _text(report.get("created_utc"))),
        ("Signed with key", _code(signed.key_id)),
        ("Ridge", _text(f"{env.get('version')} on {env.get('platform')} ({env.get('machine')})")),
        ("Python", _text(env.get("python"))),
    ]
    inputs = [
        ("Photo", _text(f"{source.get('label')} · {source.get('format')} {size[0]} x {size[1]} px")),
        ("SHA-256", _code(source.get("sha256"))),
        ("Source", _text(source.get("source")) if source.get("source") else ""),
    ]
    parameters = [(str(k), _code(v if v is not None else "none")) for k, v in sorted(params.items())]
    results = [
        ("Ridge spacing", _text(f"{meas.get('ridge_period_px', 0):.2f} px") if meas else ""),
        ("Finger located", _text("yes" if meas.get("found_finger") else "no") if meas else ""),
        ("Export", _text(_value(export_line(report.get("export"))))),
        ("NFIQ 2", _text(_value(nfiq2_line((report.get("quality") or {}).get("nfiq2"))))),
        ("Minutiae", _text(_value(minutiae_line(report.get("minutiae"))))),
        ("Limits of use", _limits(report.get("limits_of_use"))),
    ]
    outputs = "".join(
        f"<tr><td>{_text(o.get('role'))}</td><td>{_text(o.get('label'))}</td><td>{_code(o.get('sha256'))}</td>"
        f"<td>{_text(o.get('size'))}</td></tr>"
        for o in report.get("outputs") or []
    )
    canonical_sha = sha256_hex(signed.canonical)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="{CSP}">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Ridge job report {escape(signed.job_id[:8])}</title><style>{STYLE}</style></head>
<body>
<h1>Ridge job report</h1>
<p class="banner">Image enhancement only. Ridge does not identify anyone and draws no conclusions.</p>
<h2>Summary</h2>{_rows(summary)}
<h2>Input</h2>{_rows(inputs)}
<h2>Parameters</h2>{_rows(parameters)}
<h2>Results</h2>{_rows(results)}
<h2>Outputs</h2><table><tr><th scope="col">Role</th><th scope="col">File</th><th scope="col">SHA-256</th>
<th scope="col">Bytes</th></tr>{outputs}</table>
<p>{_text(report.get("disclaimer", ""))}</p>
<footer>This page renders the signed report whose SHA-256 is {_code(canonical_sha)}, custody head
{_code(report.get("custody_head"))}. The signed JSON report and its detached signature are authoritative;
verify them with <code>ridge-case check-report</code>. This page is not signed.</footer>
</body></html>
"""


def export_report_html(case: OpenCase, store: Path, ref: str, dest: Path, *, overwrite: bool = False) -> SignedReport:
    """Write the HTML rendering of a checked report (logged as ``report.export`` with format html)."""
    signed = load_report(case, store, ref, log=False)
    if not overwrite and dest.exists():
        raise OutputExistsError(f"{dest.name} already exists (use --overwrite to replace)")
    publish_logged(
        [(dest, render_report_html(signed).encode("utf-8"))],
        lambda: case.entries.append(
            case.custody.append("report.export", job_id=signed.job_id, destination=str(dest.resolve()), format="html")
        ),
        overwrite=overwrite,
    )
    return signed
