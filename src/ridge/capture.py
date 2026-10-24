"""Capture check: whether a photograph gives Ridge something to work with (FR-54; indicative, never a score).

Run on a photo before it is imported, or on stored evidence, read-only. It measures what the pipeline
will see: whether skin colour locates a finger and how much of the frame it fills, how many pixels the
camera spent on each ridge, how clearly the finger's patches show one ridge wave, the share of the
finger under specular highlights, and the file's provenance hints (edited, recompressed, no camera
metadata). Each finding is either fine, a reason to photograph again if that is still possible, or a
note. The only question answered is whether a retake would help; nothing here rates a print, and a
clean check does not mean a usable print.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final, Literal

import numpy as np

from ridge.arrays import ImageU8, Mask
from ridge.errors import ExtractionError, NoRidgePatternError
from ridge.image_io import ReadLimits, decode_image, read_bounded
from ridge.metadata import read_metadata
from ridge.metadata.provenance import provenance_hints
from ridge.pipeline.channel import gray_channel
from ridge.pipeline.mask import finger_mask, without_specular
from ridge.pipeline.period import estimate_period, ridge_signal_strength

SCHEMA: Final = "ridge.capture-check/1"
MIN_FINGER_SHARE: Final = 0.10  # the finger should fill at least a tenth of the frame
MIN_PIXELS_PER_RIDGE: Final = 6.0  # fewer pixels per ridge than this: the camera is too far away or zoomed digitally
MIN_CLARITY: Final = 0.02  # median spectral peak share of the finger's patches below this: ridges blurred or unlit
# (provisional: synthetic sharp fingers read about 0.05, fingers blurred by 5 px about 0.005; the pilot adjusts it)
MAX_GLARE_SHARE: Final = 0.05  # more of the finger than this under specular highlights: glare
LOW_JPEG_QUALITY: Final = 80  # a JPEG saved below this IJG quality was probably recompressed on the way
COPY_HINTS: Final = frozenset({"software", "xmp-history", "copy-size", "not-camera-format", "png"})
NOTICE: Final = (
    "This check only says whether photographing the finger again would help. It is not a quality score of a "
    "print and says nothing about identification."
)
SCALE_NOTE: Final = (
    "Ridge cannot see whether a ruler or an ISO/IEC 7810 ID-1 card lies in the plane of the finger pad; with one, "
    "the scale is measured instead of estimated."
)

Level = Literal["ok", "retake", "note"]


@dataclass(frozen=True, slots=True)
class Finding:
    """One observation: an identifier for tooling, its level and the plain-language text for the investigator."""

    id: str
    level: Level
    text: str

    def to_json(self) -> dict[str, str]:
        """Report form of the finding."""
        return {"id": self.id, "level": self.level, "text": self.text}


@dataclass(frozen=True, slots=True)
class CaptureCheck:
    """What the check measured and found; `verdict` is "retake" when any finding asks for one."""

    sha256: str
    width: int
    height: int
    finger_located: bool
    finger_share: float  # share of the frame covered by the located finger, 0..1 (the whole frame when not located)
    ridge_spacing_px: float | None  # pixels per ridge, as the pipeline measures it; None when it could not
    clarity: float | None  # median spectral peak share of the finger's patches, 0..1
    glare_share: float | None  # share of the finger area under specular highlights, 0..1
    findings: tuple[Finding, ...] = field(default_factory=tuple)

    @property
    def verdict(self) -> Literal["retake", "ok"]:
        """Return "retake" when any finding asks for a new photograph, else "ok" (not a quality statement)."""
        return "retake" if any(f.level == "retake" for f in self.findings) else "ok"

    def to_json(self) -> dict[str, Any]:
        """Return the ``ridge.capture-check/1`` record."""
        return {
            "schema": SCHEMA,
            "sha256": self.sha256,
            "width": self.width,
            "height": self.height,
            "finger_located": self.finger_located,
            "finger_share": self.finger_share,
            "ridge_spacing_px": self.ridge_spacing_px,
            "clarity": self.clarity,
            "glare_share": self.glare_share,
            "verdict": self.verdict,
            "findings": [f.to_json() for f in self.findings],
            "notice": NOTICE,
        }


def _ridge_findings(
    bgr: ImageU8, mask: Mask, located: bool
) -> tuple[float | None, float | None, float | None, list[Finding]]:
    """Measure the spacing, clarity and glare on the finger area; every failure becomes a finding."""
    findings: list[Finding] = []
    gray, _ = gray_channel(bgr, "green", mask)
    try:
        spacing = estimate_period(gray, mask)
    except ExtractionError as exc:
        findings.append(Finding("spacing-unmeasured", "retake", f"The ridge spacing could not be measured: {exc}."))
        return None, None, None, findings
    if spacing < MIN_PIXELS_PER_RIDGE:
        findings.append(
            Finding(
                "coarse",
                "retake",
                f"About {spacing:.1f} px per ridge: too few for this camera. Move closer or use the main camera; "
                "do not zoom digitally.",
            )
        )
    else:
        findings.append(Finding("spacing", "ok", f"About {spacing:.1f} px per ridge."))
    clarity = ridge_signal_strength(gray, mask)
    if clarity < MIN_CLARITY:
        findings.append(
            Finding(
                "unclear",
                "retake",
                f"The ridge pattern is unclear (peak share {clarity:.2f}): focus on the ridges, hold the camera still, "
                "and add even light.",
            )
        )
    else:
        findings.append(Finding("clarity", "ok", f"The ridge pattern is clear (peak share {clarity:.2f})."))
    try:
        _, glare = without_specular(bgr, mask, spacing)
    except NoRidgePatternError:
        glare = 1.0
    if glare > MAX_GLARE_SHARE:
        findings.append(
            Finding(
                "glare",
                "retake",
                f"Glare covers {100 * glare:.0f} % of the finger: move the light, switch off the flash or diffuse it.",
            )
        )
    elif located:
        findings.append(Finding("no-glare", "ok", f"Glare covers {100 * glare:.0f} % of the finger."))
    return spacing, clarity, glare, findings


def _finger_findings(bgr: ImageU8) -> tuple[Mask, bool, float, list[Finding]]:
    """Locate the finger by skin colour and judge how much of the frame it fills."""
    detected = finger_mask(bgr)
    if detected is None:
        mask: Mask = np.ones(bgr.shape[:2], dtype=bool)
        text = (
            "No finger was located by skin colour: use a plain, matt background and let the finger pad fill a "
            "third of the frame or more. The whole frame was measured instead."
        )
        return mask, False, 1.0, [Finding("not-located", "retake", text)]
    share = float(detected.mean())
    if share < MIN_FINGER_SHARE:
        text = f"The finger fills {100 * share:.0f} % of the frame: move closer so the pad fills a third or more."
        return detected, True, share, [Finding("small", "retake", text)]
    return detected, True, share, [Finding("located", "ok", f"The finger fills {100 * share:.0f} % of the frame.")]


def _provenance_findings(data: bytes) -> list[Finding]:
    """Turn the file's provenance hints into notes: a copy or an edited file is not the original."""
    record = provenance_hints(data, read_metadata(data))
    hints = record.get("hints")
    found = {h["id"]: h for h in hints if isinstance(h, dict) and "id" in h} if isinstance(hints, list) else {}
    findings: list[Finding] = []
    if found.keys() & COPY_HINTS:
        findings.append(
            Finding(
                "copy",
                "note",
                "The file shows signs of editing or copying (" + ", ".join(sorted(found.keys() & COPY_HINTS)) + "): "
                "transfer the camera's original file, unchanged, by cable or memory card.",
            )
        )
    quality = record.get("jpeg_quality_estimate")
    if isinstance(quality, int | float) and quality < LOW_JPEG_QUALITY:
        findings.append(
            Finding(
                "recompressed",
                "note",
                f"The JPEG was saved at an estimated quality of {quality:.0f}: it was probably recompressed on the "
                "way (messaging apps do this). Transfer the original.",
            )
        )
    if "no-exif" in found or "no-camera" in found:
        findings.append(Finding("no-camera-data", "note", "The file carries no camera metadata; keep the original's."))
    return findings


def check_bytes(data: bytes, limits: ReadLimits | None = None) -> CaptureCheck:
    """Check decoded image bytes (hashed and decoded from the same buffer); raises InputError for a refused file."""
    limits = limits or ReadLimits()
    bgr = decode_image(data, limits)
    mask, located, share, findings = _finger_findings(bgr)
    spacing, clarity, glare, ridge = _ridge_findings(bgr, mask, located)
    findings.extend(ridge)
    findings.extend(_provenance_findings(data))
    findings.append(Finding("scale", "note", SCALE_NOTE))
    return CaptureCheck(
        sha256=hashlib.sha256(data).hexdigest(),
        width=int(bgr.shape[1]),
        height=int(bgr.shape[0]),
        finger_located=located,
        finger_share=share,
        ridge_spacing_px=spacing,
        clarity=clarity,
        glare_share=glare,
        findings=tuple(findings),
    )


def check_file(path: Path, limits: ReadLimits | None = None) -> CaptureCheck:
    """Check a photo file read once, bounded and read-only (the file is never changed)."""
    limits = limits or ReadLimits()
    return check_bytes(read_bounded(path, limits.max_bytes), limits)


def check_text(check: CaptureCheck) -> list[str]:
    """Plain-text lines for the terminal and the readable views: the verdict, then each finding."""
    verdict = (
        "Photograph the finger again if you still can:"
        if check.verdict == "retake"
        else "No reason to photograph the finger again was found."
    )
    marks = {"ok": "ok", "retake": "retake", "note": "note"}
    lines = [f"capture check {check.sha256[:12]}  {check.width} x {check.height} px", verdict]
    lines.extend(f"  [{marks[f.level]}] {f.text}" for f in check.findings)
    lines.append(NOTICE)
    return lines
