"""One-line descriptions of job-report sections, shared by the text and HTML renderers.

Each line starts with a 14-character label column ("Export        ..."); the HTML renderer
shows the part after it.
"""

from __future__ import annotations

from typing import Any


def export_line(export: dict[str, Any] | None) -> str:
    """Describe a report's export section as one labelled text line."""
    if export is None:
        return "Export        not requested"
    if not export.get("produced"):
        return f"Export        not produced: {export.get('reason')}"
    scale = export.get("scale") or {}
    transforms = ", ".join(export.get("transforms") or []) or "none"
    gray = export.get("grayscale") or {}  # reports made before FR-37 have no grayscale twin
    twin = f"; grayscale twin sha256 {str(gray.get('sha256'))[:12]}" if gray.get("sha256") else ""
    where = f" ({scale['reference']})" if scale.get("reference") else ""  # older reports name no object
    return (
        f"Export        {export.get('ppi'):g} ppi, scale from {scale.get('method')}{where} "
        f"(+-{scale.get('uncertainty_pct', 0):.1f} %), transforms: {transforms}{twin}"
    )


def scale_notice_line(export: dict[str, Any] | None) -> str:
    """Return the notice of an export scaled without a reference object in the photo (empty otherwise)."""
    notice = ((export or {}).get("scale") or {}).get("notice")
    return f"Scale notice  {notice}" if notice else ""


def nfiq2_line(nfiq2: dict[str, Any] | None) -> str:
    """Describe a report's NFIQ 2 score as one labelled text line (empty when absent)."""
    if nfiq2 is None:
        return ""
    if not nfiq2.get("computed"):
        return f"NFIQ 2        not computed: {nfiq2.get('reason')}"
    scored = f" on the {nfiq2['image']} image" if nfiq2.get("image") else ""  # older reports name none
    return f"NFIQ 2        {nfiq2.get('score')} ({nfiq2.get('label')}; {nfiq2.get('version')}){scored}"


def minutiae_line(minutiae: dict[str, Any] | None) -> str:
    """Describe a report's minutiae summary as one labelled text line (empty when absent)."""
    if minutiae is None:
        return ""
    if not minutiae.get("produced"):
        return f"Minutiae      not produced: {minutiae.get('reason')}"
    return (
        f"Minutiae      {minutiae.get('count')} ({minutiae.get('endings')} endings, "
        f"{minutiae.get('bifurcations')} bifurcations), {minutiae.get('label')}"
    )


def print_area_line(area: dict[str, Any] | None) -> str:
    """Describe where the print came from in the photo (empty for reports made before it was recorded)."""
    if not area:
        return ""
    x, y, w, h = area.get("box_px") or ["?", "?", "?", "?"]
    parts = area.get("parts")
    kept = f"{parts} kept area" + ("" if parts == 1 else "s")
    return f"Print area    x {x}, y {y}, {w}x{h} px of the photo (the print image's frame; {kept})"
