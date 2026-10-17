"""Reproduction check (PRD FR-34, NFR-3): re-run a signed job from its report alone and compare outputs.

The original report must verify first (FR-28). Its recorded parameters then run as a new job on the
same evidence. The new job is logged, signed and stored like any other; outputs with identical
bytes are deduplicated, not stored twice. Every output hash is compared by role and label, and the
result is logged as ``job.reproduce`` under a fresh signed head. A re-run that fails outright is
logged the same way (``failed``, linked to the original job) before the error is raised.

Results are reproducible per operating system and CPU architecture (NFR-3, ADR-009). A mismatch on
another platform is expected and is reported with the environment differences rather than hidden.
NFIQ 2 is an external tool: its score is not an output file and is not compared.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ridge.case.export_step import ExportOptions
from ridge.case.identity import Signer
from ridge.case.jobs import JobParams, run_extraction_job
from ridge.case.reports import list_jobs, load_report
from ridge.case.store import OpenCase
from ridge.errors import IntegrityError, RidgeError


@dataclass(frozen=True)
class Reproduction:
    """How a re-run compares with the original job."""

    original_job: str
    new_job: str
    matched: list[str]
    differing: list[str]
    missing: list[str]  # produced originally, not now
    extra: list[str]  # produced now, not originally
    environment_changes: dict[str, list[Any]] = field(default_factory=dict)  # key -> [original, now]

    @property
    def identical(self) -> bool:
        """True when every output has the same role, label and bytes."""
        return not (self.differing or self.missing or self.extra)


def params_from_report(parameters: dict[str, Any]) -> JobParams:
    """Rebuild the job parameters recorded in a report (reports before M3 have no minutiae flag)."""
    try:
        export = parameters["export"]
        ruler = export["ruler"]
        return JobParams(
            period=parameters["period"],
            min_quality=parameters["min_quality"],
            flip=parameters["flip"],
            crop=parameters["crop"],
            debug=parameters["debug"],
            export=ExportOptions(
                enabled=export["enabled"],
                mirror=export["mirror"],
                target_ppi=export["target_ppi"],
                ruler=None if ruler is None else (ruler[0], ruler[1], ruler[2], ruler[3], ruler[4]),
            ),
            minutiae=parameters.get("minutiae", False),
        )
    except (KeyError, TypeError, IndexError):
        raise IntegrityError("the report's parameters are incomplete; the job cannot be reproduced") from None


def _flatten(env: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    flat: dict[str, Any] = {}
    for key, value in env.items():
        if isinstance(value, dict):
            flat.update(_flatten(value, f"{prefix}{key}."))
        else:
            flat[f"{prefix}{key}"] = value
    return flat


def reproduce_job(
    case: OpenCase, store: Path, signer: Signer, ref: str, *, nfiq2_command: Sequence[str] | None = None
) -> Reproduction:
    """Re-run job `ref` with its recorded parameters and compare every output."""
    original = load_report(case, store, ref).report
    params = params_from_report(original["parameters"])
    try:
        outcome = run_extraction_job(case, original["input"]["sha256"], signer, params, nfiq2_command=nfiq2_command)
    except RidgeError as exc:  # the most important negative result: record it, linked and signed
        rerun = list_jobs(case.entries)[-1]  # run_extraction_job logged this job as failed
        case.entries.append(
            case.custody.append(
                "job.reproduce",
                result="failed",
                job_id=rerun.job_id,
                original_job_id=original["job_id"],
                error=str(exc),
            )
        )
        case.entries.append(case.custody.sign_head(signer))
        raise
    before = {f"{o['role']}:{o['label']}": o["sha256"] for o in original["outputs"]}
    after = {f"{o.role}:{o.label}": o.sha256 for o in outcome.outputs}
    old_env, new_env = _flatten(original["ridge"]), _flatten(outcome.report["ridge"])
    result = Reproduction(
        original_job=original["job_id"],
        new_job=outcome.job_id,
        matched=sorted(k for k in before.keys() & after.keys() if before[k] == after[k]),
        differing=sorted(k for k in before.keys() & after.keys() if before[k] != after[k]),
        missing=sorted(before.keys() - after.keys()),
        extra=sorted(after.keys() - before.keys()),
        environment_changes={
            k: [old_env.get(k), new_env.get(k)]
            for k in sorted(old_env.keys() | new_env.keys())
            if old_env.get(k) != new_env.get(k)
        },
    )
    case.entries.append(
        case.custody.append(
            "job.reproduce",
            result="ok" if result.identical else "mismatch",
            job_id=result.new_job,
            original_job_id=result.original_job,
            matched=len(result.matched),
            differing=result.differing,
            missing=result.missing,
            extra=result.extra,
            environment_changes=result.environment_changes,
        )
    )
    case.entries.append(case.custody.sign_head(signer))
    return result
