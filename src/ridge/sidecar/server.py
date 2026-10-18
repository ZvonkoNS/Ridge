"""``ridge-sidecar``: JSON-RPC 2.0 over stdin/stdout for the desktop GUI (milestone M4).

Started by the Tauri Rust core as a child process; never opens a socket (SEC-1). It exits
when stdin closes, locking the open case. Responses are written one per line and flushed.
"""

from __future__ import annotations

import sys
from typing import BinaryIO

from ridge.errors import InputError, RidgeError
from ridge.sidecar.handlers import METHODS, SCHEMAS, Session
from ridge.sidecar.protocol import (
    APPLICATION_ERROR,
    INPUT_REFUSED,
    INTERNAL_ERROR,
    MAX_MESSAGE_BYTES,
    RpcError,
    error_response,
    parse_request,
    response,
)


def handle(line: bytes, session: Session) -> bytes:
    """Answer one framed request (never raises for request problems)."""
    request_id = None
    try:
        request = parse_request(line, SCHEMAS)
        request_id = request.id
        session.touch()  # idle auto-lock happens before the request is served
        handler, _ = METHODS[request.method]
        return response(request_id, handler(session, request.params))
    except RpcError as exc:
        return error_response(exc.request_id, exc.code, exc.message)
    except InputError as exc:  # one input file was refused: a batch of files may go on
        return error_response(request_id, INPUT_REFUSED, str(exc))
    except RidgeError as exc:
        return error_response(request_id, APPLICATION_ERROR, str(exc))
    except OSError as exc:
        return error_response(request_id, APPLICATION_ERROR, exc.strerror or type(exc).__name__)
    except Exception as exc:  # noqa: BLE001  # a bug: answer safely, keep serving
        return error_response(request_id, INTERNAL_ERROR, f"internal error ({type(exc).__name__})")


def _read_line(stream: BinaryIO) -> bytes | None:
    """One line, or an oversize marker; never buffers more than MAX_MESSAGE_BYTES + 1."""
    line = stream.readline(MAX_MESSAGE_BYTES + 1)
    if not line:
        return None
    if len(line) > MAX_MESSAGE_BYTES and not line.endswith(b"\n"):
        while (rest := stream.readline(MAX_MESSAGE_BYTES)) and not rest.endswith(b"\n"):
            pass  # discard the rest of the oversized message
    return line


def serve(stdin: BinaryIO, stdout: BinaryIO, session: Session | None = None) -> int:
    """Serve requests until stdin closes; always lock the case at the end."""
    session = session or Session()
    try:
        while (line := _read_line(stdin)) is not None:
            if not line.strip():
                continue
            stdout.write(handle(line, session))
            stdout.flush()
    finally:
        session.close()
    return 0


def main() -> int:
    """Console entry point ``ridge-sidecar``."""
    return serve(sys.stdin.buffer, sys.stdout.buffer)
