"""Property-based fuzzing of the record files a reviewer receives from outside (ASVS V5, CWE-20/754).

Key registers, key cards, limits files and their signatures, custody heads, processing records and
disclosure-package manifests are parsed from files that anyone may hand to the offline checks.
Arbitrary JSON, or arbitrary bytes, must only ever produce Ridge's typed refusal for that file,
never another exception type.
"""

from __future__ import annotations

import contextlib
import json
import tempfile
from pathlib import Path
from typing import Any

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from ridge.case.custody_head import check_head
from ridge.case.key_card import check_card
from ridge.case.key_register import SCHEMA as REGISTER_SCHEMA
from ridge.case.key_register import parse_register
from ridge.case.limits import SCHEMA as LIMITS_SCHEMA
from ridge.case.limits import SIGNATURE_SCHEMA, check_signature, parse_limits
from ridge.case.package import MANIFEST, check_package
from ridge.case.processing_record import SCHEMA as RECORD_SCHEMA
from ridge.case.processing_record import check_exported_log
from ridge.errors import InputRejectedError, IntegrityError, ParameterError

FUZZ = settings(max_examples=60, deadline=None, suppress_health_check=[HealthCheck.too_slow])
SCALARS = st.none() | st.booleans() | st.integers(-(2**40), 2**40) | st.floats(allow_nan=False) | st.text(max_size=40)
JSON = st.recursive(
    SCALARS,
    lambda inner: st.lists(inner, max_size=4) | st.dictionaries(st.text(max_size=16), inner, max_size=6),
    max_leaves=25,
)


def near(schema_field: str, schema: str, fields: list[str]) -> st.SearchStrategy[dict[str, Any]]:
    """Documents that look like the real format: the right schema and known keys with random values."""
    return st.fixed_dictionaries({schema_field: st.just(schema)}, optional=dict.fromkeys(fields, JSON))


def as_bytes(doc: object) -> bytes:
    return json.dumps(doc).encode()


def in_file(name: str, data: bytes) -> tuple[tempfile.TemporaryDirectory[str], Path]:
    folder = tempfile.TemporaryDirectory()
    path = Path(folder.name) / name
    path.write_bytes(data)
    return folder, path


@FUZZ
@given(
    st.one_of(
        st.binary(max_size=600),
        JSON.map(as_bytes),
        near("schema", REGISTER_SCHEMA, ["laboratory", "keys"]).map(as_bytes),
        st.lists(
            st.fixed_dictionaries(
                {},
                optional=dict.fromkeys(
                    ("key_id", "public_key", "holder", "role", "valid_from", "valid_until", "revoked"), JSON
                ),
            ),
            max_size=3,
        ).map(lambda keys: as_bytes({"schema": REGISTER_SCHEMA, "laboratory": "L", "keys": keys})),
    )
)
def test_key_registers_only_raise_parameter_errors(data: bytes) -> None:
    with contextlib.suppress(ParameterError):
        parse_register(data)


LIMIT_FIELDS = ["source", "architectures", "min_ridge_period_px", "max_ridge_period_px", "require_ruler"]


@FUZZ
@given(
    st.one_of(st.binary(max_size=600), JSON.map(as_bytes), near("schema", LIMITS_SCHEMA, LIMIT_FIELDS).map(as_bytes))
)
def test_limits_files_only_raise_parameter_errors(data: bytes) -> None:
    with contextlib.suppress(ParameterError):
        parse_limits(data)


SIGNATURE_FIELDS = ["key_id", "public_key", "limits_sha256", "signature"]


@FUZZ
@given(st.one_of(st.binary(max_size=600), near("schema", SIGNATURE_SCHEMA, SIGNATURE_FIELDS).map(as_bytes)))
def test_limits_signatures_only_raise_parameter_errors(signature: bytes) -> None:
    with contextlib.suppress(ParameterError):
        check_signature(b'{"schema": "ridge.limits-of-use/1"}', signature)


CARD_FIELDS = ["key_id", "public_key", "role", "holder", "created_utc", "statement", "signature"]
HEAD_FIELDS = ["case_id", "seq", "head", "ts_utc", "exported_utc", "key_id", "public_key", "signature"]


@FUZZ
@given(
    st.one_of(
        st.binary(max_size=600),
        near("schema", "ridge.key-card/1", CARD_FIELDS).map(as_bytes),
    )
)
def test_key_cards_only_raise_integrity_errors(data: bytes) -> None:
    folder, path = in_file("card.json", data)
    with folder, contextlib.suppress(IntegrityError):
        check_card(path)


@FUZZ
@given(
    st.one_of(
        st.binary(max_size=600),
        near("schema", "ridge.custody-head/1", [*HEAD_FIELDS, "file_signature"]).map(as_bytes),
    )
)
def test_custody_heads_only_raise_integrity_errors(data: bytes) -> None:
    folder, path = in_file("head.json", data)
    with folder, contextlib.suppress(IntegrityError, InputRejectedError):
        check_head(path)


@FUZZ
@given(
    st.one_of(
        st.binary(max_size=600),
        near("schema", RECORD_SCHEMA, ["case_id", "identity", "entries", "exported_utc"]).map(as_bytes),
    )
)
def test_processing_records_only_raise_integrity_errors(data: bytes) -> None:
    folder, path = in_file("record.json", data)
    with folder, contextlib.suppress(IntegrityError, InputRejectedError):
        check_exported_log(path)


@FUZZ
@given(
    manifest=st.one_of(
        st.binary(max_size=600),
        near("schema", "ridge.package/1", ["package_id", "case_id", "identity", "files", "created_utc"]).map(as_bytes),
    ),
    signature=st.binary(max_size=120),
)
def test_package_manifests_only_raise_integrity_errors(manifest: bytes, signature: bytes) -> None:
    folder, path = in_file(MANIFEST, manifest)
    with folder:
        (path.parent / (MANIFEST + ".sig")).write_bytes(signature)
        with contextlib.suppress(IntegrityError, InputRejectedError):
            check_package(path.parent)
