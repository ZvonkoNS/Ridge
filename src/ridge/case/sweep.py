"""Scale sweep of a stored comparison export into a new folder (PRD FR-39); every file is logged.

The export's scale uncertainty comes from the job's verified report, never from a guess. Each
rescaled file keeps the export's declared resolution, is hashed, and is logged as ``sweep.export``
with its factor and the stored export it came from; ``SWEEP.csv`` indexes the folder. If the sweep
stops part-way, the files already written stay (each is logged), the index lists exactly those,
and the error says how many of how many were written.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ridge.case.case_model import StoredItem, publish_logged
from ridge.case.crypto import sha256_hex
from ridge.case.export_file import CONVERTIBLE_ROLES
from ridge.case.reports import load_report
from ridge.case.store import OpenCase
from ridge.errors import IntegrityError, OutputError, OutputExistsError, ParameterError, RidgeError
from ridge.export.formats import EXTENSIONS, FileFormat, check_format, convert_png, decode_gray_png
from ridge.export.png import encode_png
from ridge.export.sweep import DEFAULT_STEPS, rescaled, sweep_factors
from ridge.image_io import publish

INDEX = "SWEEP.csv"
SWEEP_ROLES = ("export", "export-gray")


@dataclass(frozen=True, slots=True)
class SweepFile:
    """One rescaled file: its name, factor, SHA-256 and size in pixels."""

    name: str
    factor: float
    sha256: str
    width: int
    height: int


@dataclass(frozen=True, slots=True)
class Sweep:
    """A finished sweep: the source export, its recorded scale and every file written."""

    item: StoredItem
    ppi: float
    scale: dict[str, Any]
    files: list[SweepFile]


def _recorded_scale(case: OpenCase, store: Path, item: StoredItem) -> tuple[float, dict[str, Any]]:
    """Return (declared ppi, scale section) of the export from its job's verified report."""
    if item.role not in SWEEP_ROLES:
        raise ParameterError(f"a scale sweep needs a comparison export (export or export-gray), not a {item.role}")
    if item.job_id is None:  # pragma: no cover - artefacts always carry their job
        raise IntegrityError(f"export {item.sha256[:12]} names no job")
    export = load_report(case, store, item.job_id, log=False).report.get("export") or {}
    ppi, scale = export.get("ppi"), export.get("scale")
    if not isinstance(ppi, int | float) or not isinstance(scale, dict) or "uncertainty_pct" not in scale:
        raise IntegrityError(f"the report of job {item.job_id[:8]} does not record the export's scale")
    return float(ppi), scale


def _file_name(item: StoredItem, factor: float, fmt: FileFormat | None) -> str:
    stem = Path(item.label).stem or item.role
    return f"{stem}_scale_{factor:.4f}{EXTENSIONS[fmt or 'png']}"


def export_sweep(
    case: OpenCase, store: Path, sha: str, dest: Path, *, steps: int = DEFAULT_STEPS, fmt: FileFormat | None = None
) -> Sweep:
    """Write the sweep of export `sha` into the new folder `dest` (one logged file per factor)."""
    item = case.item(sha)
    if item.role not in CONVERTIBLE_ROLES or item.role not in SWEEP_ROLES:
        raise ParameterError(f"a scale sweep needs a comparison export (export or export-gray), not a {item.role}")
    if fmt is not None:
        fmt = check_format(fmt)
    ppi, scale = _recorded_scale(case, store, item)
    factors = sweep_factors(float(scale["uncertainty_pct"]), steps)
    pixels, _ = decode_gray_png(case.read(item.sha256, log=False))
    try:
        dest.mkdir(mode=0o700)  # private: file names carry labels
    except FileExistsError:
        raise OutputExistsError(f"{dest.name} already exists: choose a new folder") from None
    sweep = Sweep(item, ppi, scale, [])
    try:
        for factor in factors:
            sweep.files.append(_write_one(case, item, dest, pixels=pixels, factor=factor, ppi=ppi, fmt=fmt))
    except (RidgeError, OSError) as exc:
        if not sweep.files:
            dest.rmdir()  # nothing left the store: leave nothing behind
            raise
        _write_index(dest, sweep)
        raise OutputError(
            f"the sweep stopped after {len(sweep.files)} of {len(factors)} file(s) ({exc}); {INDEX} lists the "
            "written files, each is in the custody log"
        ) from exc
    _write_index(dest, sweep)
    return sweep


def _write_one(
    case: OpenCase,
    item: StoredItem,
    dest: Path,
    *,
    pixels: Any,
    factor: float,
    ppi: float,
    fmt: FileFormat | None,
) -> SweepFile:
    image = rescaled(pixels, factor)
    data = encode_png(image, ppi)  # declared at the export's resolution: the AFIS reads a different physical size
    if fmt in ("tiff", "bmp"):
        data = convert_png(data, fmt)
    name, digest = _file_name(item, factor, fmt), sha256_hex(data)
    publish_logged(
        [(dest / name, data)],
        lambda: case.entries.append(
            case.custody.append(
                "sweep.export",
                sha256=digest,
                source_sha256=item.sha256,
                role=item.role,
                job_id=item.job_id,
                factor=factor,
                ppi=ppi,
                destination=str((dest / name).resolve()),
            )
        ),
        overwrite=False,
    )
    return SweepFile(name, factor, digest, image.shape[1], image.shape[0])


def _write_index(dest: Path, sweep: Sweep) -> None:
    buffer = io.StringIO()
    rows = csv.writer(buffer, lineterminator="\n")
    rows.writerow(
        [
            "file",
            "factor",
            "sha256",
            "width_px",
            "height_px",
            "declared_ppi",
            "source_sha256",
            "job_id",
            "scale_method",
            "uncertainty_pct",
        ]
    )
    rows.writerows(
        [
            f.name,
            f"{f.factor:.4f}",
            f.sha256,
            f.width,
            f.height,
            f"{sweep.ppi:g}",
            sweep.item.sha256,
            sweep.item.job_id or "",
            str(sweep.scale.get("method")),
            str(sweep.scale.get("uncertainty_pct")),
        ]
        for f in sweep.files
    )
    publish(dest / INDEX, buffer.getvalue().encode("utf-8"))
