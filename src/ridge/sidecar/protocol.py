"""JSON-RPC 2.0 framing and validation for the GUI sidecar (architecture §7.3, PRD SEC-2, SEC-8).

One UTF-8 JSON object per line on stdin/stdout; no sockets, no batches, no notifications.
Every request is untrusted: size-limited, strictly parsed (duplicate keys refused), checked
against an allow-list of methods and a per-method parameter schema that refuses unknown or
mistyped fields. Error responses carry safe messages only (no stack traces, no data).
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Any, cast

MAX_MESSAGE_BYTES = 1024 * 1024
MAX_ID_CHARS = 64

PARSE_ERROR, INVALID_REQUEST, METHOD_NOT_FOUND, INVALID_PARAMS, INTERNAL_ERROR = -32700, -32600, -32601, -32602, -32603
APPLICATION_ERROR = -32000  # Ridge refused or failed (RidgeError); the message is safe to show
INPUT_REFUSED = -32001  # an input file was refused (wrong format, too large, undecodable); safe to show

type Json = Any
# field -> (expected types, required)
type Schema = dict[str, tuple[tuple[type, ...], bool]]


class RpcError(Exception):
    """A JSON-RPC error to send back."""

    def __init__(self, code: int, message: str, request_id: int | str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.request_id = request_id


@dataclass(frozen=True)
class Request:
    """A validated request."""

    id: int | str
    method: str
    params: dict[str, Json]


def _no_duplicates(pairs: list[tuple[str, Json]]) -> dict[str, Json]:
    keys = [k for k, _ in pairs]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate key")
    return dict(pairs)


def _reject_constant(name: str) -> None:
    raise ValueError(f"{name} is not valid JSON")


def parse_request(line: bytes, schemas: dict[str, Schema]) -> Request:
    """Validate one framed message against the method allow-list and its parameter schema."""
    if len(line) > MAX_MESSAGE_BYTES:
        raise RpcError(INVALID_REQUEST, f"message larger than {MAX_MESSAGE_BYTES // 1024} KiB")
    try:
        message = json.loads(line.decode("utf-8"), object_pairs_hook=_no_duplicates, parse_constant=_reject_constant)
    except (UnicodeDecodeError, ValueError):
        raise RpcError(PARSE_ERROR, "not a single valid UTF-8 JSON message") from None
    if not isinstance(message, dict) or set(message) - {"jsonrpc", "id", "method", "params"}:
        raise RpcError(INVALID_REQUEST, "a request is an object with jsonrpc, id, method and params only")
    request_id = message.get("id")
    if message.get("jsonrpc") != "2.0" or not _valid_id(request_id):
        raise RpcError(INVALID_REQUEST, 'jsonrpc must be "2.0" and id an integer or a short string')
    try:
        method = message.get("method")
        if not isinstance(method, str) or method not in schemas:
            raise RpcError(METHOD_NOT_FOUND, "unknown method")
        params = message.get("params", {})
        if not isinstance(params, dict):
            raise RpcError(INVALID_PARAMS, "params must be an object")
        check_params(params, schemas[method])
    except RpcError as exc:
        exc.request_id = request_id  # the id is known from here on: echo it (JSON-RPC 2.0)
        raise
    return Request(cast(int | str, request_id), method, params)


def _valid_id(value: Json) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return abs(value) < 2**53
    return isinstance(value, str) and 0 < len(value) <= MAX_ID_CHARS


def check_params(params: dict[str, Json], schema: Schema) -> None:
    """Refuse unknown, missing or mistyped parameters (bool is never accepted as a number)."""
    unknown = set(params) - set(schema)
    if unknown:
        raise RpcError(INVALID_PARAMS, f"unknown parameter(s): {', '.join(sorted(unknown))}")
    for name, (types, required) in schema.items():
        if name not in params:
            if required:
                raise RpcError(INVALID_PARAMS, f"missing parameter: {name}")
            continue
        value = params[name]
        if value is None and type(None) in types:
            continue
        if isinstance(value, bool) and bool not in types:
            raise RpcError(INVALID_PARAMS, f"{name} has the wrong type")
        if not isinstance(value, types) or (isinstance(value, float) and not math.isfinite(value)):
            raise RpcError(INVALID_PARAMS, f"{name} has the wrong type")


def response(request_id: int | str | None, result: Json) -> bytes:
    """Build a success response line."""
    return _line({"jsonrpc": "2.0", "id": request_id, "result": result})


def error_response(request_id: int | str | None, code: int, message: str) -> bytes:
    """Build an error response line."""
    return _line({"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}})


def _line(obj: dict[str, Json]) -> bytes:
    return json.dumps(obj, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8") + b"\n"
