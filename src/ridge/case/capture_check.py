"""The capture check (FR-54) on a photo stored in a case: one logged read of the verified bytes."""

from __future__ import annotations

from ridge.capture import CaptureCheck, check_bytes
from ridge.case.case_model import StoredItem
from ridge.case.photo_metadata import PHOTO_ROLES
from ridge.case.store import OpenCase
from ridge.errors import ParameterError


def check_stored_photo(case: OpenCase, sha: str) -> tuple[StoredItem, CaptureCheck]:
    """Return the stored photo and its capture check; outputs are refused before anything is read."""
    item = case.item(sha)
    if item.role not in PHOTO_ROLES:
        raise ParameterError("the capture check runs on imported photos only (evidence or reference images)")
    return item, check_bytes(case.read(item.sha256))
