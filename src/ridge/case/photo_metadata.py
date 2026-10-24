"""One imported photo's metadata, read from its verified stored bytes (FR-36).

Shared by ``ridge-case metadata`` and the sidecar's ``metadata.get``, so both refuse the same
items with the same message and log the same read.
"""

from __future__ import annotations

from typing import Any

from ridge.case.case_model import StoredItem
from ridge.case.store import OpenCase
from ridge.errors import ParameterError
from ridge.metadata import read_metadata
from ridge.metadata.provenance import provenance_hints

__all__ = ["PHOTO_ROLES", "read_photo_metadata", "read_photo_record"]

PHOTO_ROLES = ("evidence", "reference")  # outputs are written without metadata (FR-12); minutiae are JSON


def read_photo_metadata(case: OpenCase, sha: str) -> tuple[StoredItem, dict[str, Any]]:
    """Return the stored photo and its ``ridge.photo-metadata/1`` record.

    `sha` is a full SHA-256 or a unique prefix of at least 8 characters. Other roles are refused
    with ParameterError before anything is read, so a refusal logs nothing; the read itself is
    logged as ``evidence.read`` or ``reference.read`` by ``OpenCase.read``.
    """
    item, meta, _ = read_photo_record(case, sha)
    return item, meta


def read_photo_record(case: OpenCase, sha: str) -> tuple[StoredItem, dict[str, Any], dict[str, Any]]:
    """Return the stored photo, its metadata record and its provenance hints (FR-42) from one logged read."""
    item = case.item(sha)
    if item.role not in PHOTO_ROLES:
        raise ParameterError("metadata is shown for imported photos only (evidence or reference images)")
    data = case.read(item.sha256)
    meta = read_metadata(data)
    return item, meta, provenance_hints(data, meta)
