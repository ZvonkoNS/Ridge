"""Sidecar method registry: the allow-list of JSON-RPC methods and their parameter schemas.

The sidecar is a trusted layer (architecture §5, ADR-002); its caller is the Tauri Rust core,
which forwards only allow-listed commands from the untrusted WebView. Every argument is still
validated (deny by default): case ids must be UUIDs (no path traversal), paths absolute,
numbers in range. ``identity.create``, ``case.create`` and ``session.unlock`` carry the examiner
passphrase and must only ever be sent by the Rust core from its passphrase prompt, never from
WebView code. The methods themselves live in `store_methods`, `case_methods` and `job_methods`.
"""

from __future__ import annotations

from collections.abc import Callable

from ridge.sidecar import case_methods as case
from ridge.sidecar import job_methods as job
from ridge.sidecar import recovery_methods as recovery
from ridge.sidecar import store_methods as store
from ridge.sidecar.protocol import Json, Schema
from ridge.sidecar.session import Session

PROTOCOL = store.PROTOCOL
Handler = Callable[[Session, dict[str, Json]], Json]
str_ = (str,)
bool_ = (bool,)
int_ = (int,)
NUMBER = job.NUMBER
METHODS: dict[str, tuple[Handler, Schema]] = {
    "ridge.version": (store.version, {}),
    "store.cases": (store.cases, {"store": (str_, True)}),
    "store.identity": (store.identity_status, {"store": (str_, True)}),
    "store.limits": (store.limits_of_use, {"store": (str_, True)}),
    "files.check": (store.files_check, {"path": (str_, True), "register": ((str, type(None)), False)}),
    "store.backup": (store.backup, {"store": (str_, True), "dest": (str_, True)}),
    "store.workstation": (store.workstation, {"store": (str_, True), "register": ((str, type(None)), False)}),
    "store.verify": (store.verify_all, {"store": (str_, True), "passphrase": (str_, True)}),
    "store.overview": (store.overview, {"store": (str_, True), "passphrase": (str_, True)}),
    "identity.create": (store.identity_create, {"store": (str_, True), "passphrase": (str_, True)}),
    "identity.card": (
        store.identity_card,
        {"store": (str_, True), "passphrase": (str_, True), "holder": (str_, True), "dest": (str_, True)},
    ),
    "recovery.export": (
        recovery.export,
        {
            "store": (str_, True),
            "dest": (str_, True),
            "examiner_passphrase": (str_, True),
            "recovery_passphrase": (str_, True),
        },
    ),
    "recovery.check": (recovery.check_passphrase, {"path": (str_, True), "recovery_passphrase": (str_, True)}),
    "recovery.import": (
        recovery.restore,
        {
            "path": (str_, True),
            "store": (str_, True),
            "examiner_passphrase": (str_, True),
            "recovery_passphrase": (str_, True),
        },
    ),
    "case.create": (
        store.case_create,
        {
            "store": (str_, True),
            "reference": (str_, True),
            "legal_basis": (str_, True),
            "retention_until": (str_, True),
            "passphrase": (str_, True),
        },
    ),
    "session.unlock": (store.unlock, {"store": (str_, True), "case_id": (str_, True), "passphrase": (str_, True)}),
    "session.lock": (store.lock, {}),
    "session.status": (store.status, {}),
    "case.info": (case.info, {}),
    "case.status": (case.status, {}),
    "case.hold": (case.hold, {"on": (bool_, True), "reason": (str_, True)}),
    "case.items": (case.items, {}),
    "case.export_all": (
        case.export_all,
        {"role": (str_, True), "dest": (str_, True), "format": ((str, type(None)), False)},
    ),
    "note.add": (
        case.note_add,
        {
            "text": (str_, True),
            "job_id": ((str, type(None)), False),
            "sha256": ((str, type(None)), False),
            "corrects": ((int, type(None)), False),
        },
    ),
    "notes.list": (case.notes, {"job_id": ((str, type(None)), False), "sha256": ((str, type(None)), False)}),
    "case.import": (case.import_evidence, {"path": (str_, True), "source": ((str, type(None)), False)}),
    "case.verify": (case.verify, {}),
    "case.export": (case.export_item, {"sha256": (str_, True), "dest": (str_, True), "overwrite": (bool_, False)}),
    "case.jobs": (job.jobs, {}),
    "report.get": (job.report, {"job_id": (str_, True)}),
    "job.reproduce": (job.reproduce, {"job_id": (str_, True)}),
    "report.export": (job.report_export, {"job_id": (str_, True), "dest": (str_, True), "overwrite": (bool_, False)}),
    "report.export_html": (
        job.report_export_html,
        {"job_id": (str_, True), "dest": (str_, True), "overwrite": (bool_, False)},
    ),
    "cover.export": (job.cover_export, {"job_id": (str_, True), "dest": (str_, True), "overwrite": (bool_, False)}),
    "sweep.export": (
        job.sweep_export,
        {"sha256": (str_, True), "dest": (str_, True), "steps": (int_, False), "format": ((str, type(None)), False)},
    ),
    "log.export": (job.log_export, {"dest": (str_, True), "overwrite": (bool_, False)}),
    "log.entries": (
        job.log_entries,
        {
            "offset": (int_, False),
            "limit": (int_, False),
            "action": ((str, type(None)), False),
            "text": ((str, type(None)), False),
        },
    ),
    "head.export": (job.head_export, {"dest": (str_, True), "overwrite": (bool_, False)}),
    "package.export": (job.package_export, {"dest": (str_, True)}),
    "case.import_reference": (case.import_reference, {"path": (str_, True), "source": (str_, True)}),
    "compare.export": (
        job.compare_export,
        {
            "export": (str_, True),
            "reference": (str_, True),
            "dest": (str_, True),
            "reference_ppi": ((int, float, type(None)), False),
            "ppi": (NUMBER, False),
            "overwrite": (bool_, False),
        },
    ),
    "preview.get": (case.preview, {"sha256": (str_, True), "max_side": (int_, False)}),
    "metadata.get": (case.photo_metadata, {"sha256": (str_, True)}),
    "minutiae.get": (case.minutiae, {"sha256": (str_, True)}),
    "preview.region": (
        case.preview_region,
        {"sha256": (str_, True), "x": (int_, True), "y": (int_, True), "width": (int_, True), "height": (int_, True)},
    ),
    "job.run": (
        job.run_job,
        {
            "evidence": (str_, True),
            "period": ((int, float, type(None)), False),
            "min_quality": (NUMBER, False),
            "flip": (bool_, False),
            "crop": (bool_, False),
            "debug": (bool_, False),
            "export": (bool_, False),
            "mirror": (bool_, False),
            "ppi": (NUMBER, False),
            "ruler": ((list, type(None)), False),
            "reference": (str_, False),
            "minutiae": (bool_, False),
            "roi": ((list, type(None)), False),
            "finger_position": (int_, False),
            "source_agency": ((str, type(None)), False),
        },
    ),
}
SCHEMAS: dict[str, Schema] = {name: schema for name, (_, schema) in METHODS.items()}
__all__ = ["METHODS", "PROTOCOL", "SCHEMAS", "Session"]
