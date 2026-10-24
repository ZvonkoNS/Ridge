"""The submission record of a job: what an AFIS operator needs beside the image (PRD FR-38).

AFIS transactions (ANSI/NIST-ITL Type-2 and Type-14/13 records, or the operator's own form) ask for
facts Ridge cannot infer: which finger the photo shows, who submits it, and how the image was
captured. Ridge records what the examiner states, labelled as stated, and what the photo's file
records about the camera, labelled unverified, in the signed report under ``submission``. The exact
record format and impression-type code stay with the AFIS team (PRD OQ-4); the cover sheet
(``ridge.case.cover_sheet``) presents the record for them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final

from ridge.case.case_model import clean_text
from ridge.errors import ParameterError

# ANSI/NIST-ITL 1-2011 Update 2015, Table 8 (friction ridge position codes 0-10); the same codes in 1-2025.
FINGER_POSITIONS: Final[dict[int, str]] = {
    0: "unknown",
    1: "right thumb",
    2: "right index",
    3: "right middle",
    4: "right ring",
    5: "right little",
    6: "left thumb",
    7: "left index",
    8: "left middle",
    9: "left ring",
    10: "left little",
}
IMPRESSION: Final = (
    "photograph of a finger (contactless), ridge image processed by Ridge; code to be set by the AFIS operator"
)
MAX_AGENCY_CHARS: Final = 200


def check_finger_position(value: object) -> int:
    """Return `value` as a finger position code 0..10, else raise ParameterError."""
    if isinstance(value, bool) or not isinstance(value, int) or value not in FINGER_POSITIONS:
        raise ParameterError("finger_position must be a whole number 0 (unknown) to 10 (ANSI/NIST-ITL finger codes)")
    return value


def check_source_agency(value: object) -> str | None:
    """Return `value` as a cleaned agency text (1-200 printable characters) or None."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise ParameterError("source_agency must be text or null")
    return clean_text(value, "source_agency", MAX_AGENCY_CHARS)


@dataclass(frozen=True, slots=True)
class Submission:
    """What the examiner stated for an AFIS submission (validated)."""

    finger_position: int = 0
    source_agency: str | None = None

    def __post_init__(self) -> None:
        check_finger_position(self.finger_position)
        check_source_agency(self.source_agency)


def capture_device(metadata: dict[str, Any] | None) -> str | None:
    """Return the camera the photo's file names (the metadata summary's "Camera" line), unverified, or None."""
    for entry in (metadata or {}).get("summary") or []:
        if isinstance(entry, dict) and entry.get("name") == "Camera" and isinstance(entry.get("value"), str):
            return str(entry["value"])
    return None


def submission_record(submission: Submission, metadata: dict[str, Any] | None) -> dict[str, Any]:
    """Build the report's ``submission`` section."""
    device = capture_device(metadata)
    return {
        "finger_position": submission.finger_position,
        "finger": FINGER_POSITIONS[submission.finger_position],
        "source_agency": submission.source_agency,
        "impression": IMPRESSION,
        "capture_device": device,
        "capture_device_note": (
            "as the photo's file records it; not verified by Ridge" if device else "the photo's file names no camera"
        ),
        "notice": "Finger position and source agency are the examiner's statements; nothing here is an identification.",
    }


def submission_line(section: dict[str, Any] | None) -> str:
    """Describe a report's submission section as one labelled text line (empty for older reports)."""
    if not section:
        return ""
    agency = section.get("source_agency") or "not stated"
    device = section.get("capture_device") or "none named in the file"
    return (
        f"Submission    finger position {section.get('finger_position')} ({section.get('finger')}), "
        f"source agency {agency}, capture device {device} (unverified)"
    )
