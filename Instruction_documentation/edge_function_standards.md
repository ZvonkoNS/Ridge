# Entrypoint, Sidecar JSON-RPC And Tauri Command Standards

Last verified: 2026-10-16
The file name is kept for cross-references. For Ridge it covers every thin entrypoint at a trust boundary: the CLI, the Python sidecar JSON-RPC handlers (planned `src/ridge/sidecar/`, M4) and the Tauri commands (planned `gui/src-tauri/`, M4).

Serverless functions, Edge Functions, cloud functions, webhooks and HTTP endpoints: **not applicable to Ridge today** - Ridge runs offline with no network. Becomes applicable only if a server component is added, which requires a profile change, a threat model and the original pack rules (authentication, rate limits, signature and replay checks) restored.

## Core rule

Entrypoints are thin, auditable adapters of about 20-30 lines. They parse, build a request context, call one handler and map the result. Validation, state checks, business logic, storage, custody logging and response mapping live in focused modules.

## Standards posture

- NIST SSDF; ISO/IEC 27034; OWASP ASVS 5.0.0 V2, V5, V13, V15, V16 (V4 only if an HTTP API ever appears); CWE (CWE-20, CWE-22, CWE-78, CWE-502, CWE-770 in particular).
- JSON-RPC 2.0 message format; ECMA-404 JSON; ISO 8601 UTC timestamps; RFC 8785 where payloads are hashed or signed.
- Forensic rules in `forensic_evidence_and_biometric_data_standards.md` for every mutating method.

## Entrypoints and structure

| Entrypoint | Location | Rules |
| --- | --- | --- |
| CLI | `src/ridge/cli.py`, `src/ridge/__main__.py`, `fingerprint_extract.py` (backward-compatible shim calling `ridge.cli.main`) | argparse only; parameter ranges validated (for example `--min-quality` in 0..1, `--period` within documented bounds); exit codes documented and stable; no passphrase or key in arguments; messages sanitised of control characters. |
| Sidecar | planned `src/ridge/sidecar/` | Sections below. |
| Tauri commands | planned `gui/src-tauri/` | Section "Tauri command rules" and `desktop_gui_tauri_standards.md`. |

Proposed sidecar layout (authoritative design in `docs/architecture.md`):

```text
src/ridge/sidecar/
  __main__.py     Thin stdio loop
  protocol.py     Framing, size limits, JSON-RPC 2.0 parsing and serialisation
  registry.py     Allow-list: method name -> handler, schema, mutating flag
  schemas.py      Request/response schemas per method
  handlers/       One small module per method
  errors.py       Typed error -> JSON-RPC error mapping
```

## Transport rules

- JSON-RPC 2.0 over the sidecar's stdin/stdout. No sockets, no localhost HTTP, no files used as a message channel.
- stdout carries protocol messages only. Logs go to stderr (captured and redacted by the Rust core). A stray `print` corrupts the channel and is a defect.
- UTF-8, one JSON-RPC message per line, at most 1 MiB per message (`docs/architecture.md` section 7.3); the size limit is enforced before parsing; malformed frames end the session safely; the sidecar exits when stdin closes.
- A version handshake is the first exchange; protocol or Ridge version mismatch between GUI and sidecar is refused.
- Images are passed by case-store reference, never inline; display previews are bounded base64 PNGs (`docs/architecture.md` section 7.3). Nothing travels through plaintext temporary files.
- The sidecar is a signed, frozen build shipped inside the application bundle (PyInstaller one-folder build per `docs/architecture.md`); the Rust core never runs a Python interpreter or script from the system.

## Security rules

- Deny by default: methods not in the registry return `-32601` (method not found); notifications for mutating methods are rejected.
- Strict schemas: unknown fields, wrong types, out-of-range values and oversized strings or arrays are rejected with `-32602` before the handler runs.
- State checks: every method declares the case state it needs (no case, case locked, case unlocked); calls in the wrong state are refused.
- No file system paths from the WebView. Handles are opaque, case-scoped, validated against the open case, and unguessable.
- No network access, no shell, no dynamic imports, no deserialization other than JSON.
- Resource limits per call: input bytes, pixels, processing time (timeout with cancellation), and one mutating operation at a time per case.
- Errors: JSON-RPC reserved codes for protocol errors (`-32700`, `-32600`, `-32601`, `-32602`, `-32603`); typed application errors in the implementation-defined server range (`-32000` to `-32099`). Error data never contains stack traces, absolute paths, pixel data, keys or passphrases.
- Secrets: passphrases reach the sidecar only through a dedicated unlock method, are held in memory for the shortest possible time, and are never echoed, logged or stored.

## Idempotency and reliability

- Every mutating request carries a client request ID; a repeated ID returns the original result instead of repeating the action (no double ingest, no duplicate custody entries).
- Mutating methods are never retried automatically by the Rust core or the GUI.
- A sidecar crash or timeout leaves the case store consistent: every mutation is transactional with its custody entry.
- Partial failure (for example batch processing) reports per-item results and an overall status.

## Data and contract rules

- Request and response schemas are versioned; breaking changes bump the protocol version.
- Timestamps ISO 8601 UTC; hashes as `sha256:<hex>`; numeric parameters with documented units and ranges.
- Unicode file names are passed through unchanged inside handles and reports, never re-encoded.

## Tauri command rules

- Each command is a thin Rust function: deserialise into a typed struct with `#[serde(deny_unknown_fields)]`, check size limits, call exactly one allow-listed sidecar method, map the result to a typed response or typed error.
- Commands are registered through the build-time allow-list and granted per window in capability files; no `remote` grants.
- Commands never read or write files on behalf of the WebView, except through native dialogs owned by the Rust core.

## Testing requirements

Each handler and command has tests for:

- Allowed request in the correct state.
- Unknown method, notification for a mutating method, wrong state, locked case.
- Malformed JSON, invalid JSON-RPC envelope, unknown fields, wrong types, out-of-range and oversized values.
- Forged or stale handles; handles from another case.
- Duplicate request ID (idempotent result).
- Timeout and cancellation; sidecar crash mid-request; store consistency afterwards.
- Error responses contain no paths, stack traces or secrets; stdout contains only protocol frames.
- Version handshake mismatch.
- Custody entry written for every successful mutation and absent for rejected requests.

## Review checklist

- Entrypoint remains thin; files within limits.
- Allow-list unchanged or change reviewed; no new capability or plugin without an ADR.
- All boundary data validated; limits enforced before allocation.
- No secrets or class E data in logs, errors or protocol traces.
- Tests cover success, denial, malformed input and failure modes.
- Standards and forensic evidence recorded in the handoff.
