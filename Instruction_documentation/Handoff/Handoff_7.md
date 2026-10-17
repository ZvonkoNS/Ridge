# Handoff_7.md

Date/time (ISO 8601 with offset): 2026-10-17T09:55+02:00
Author/agent: Claude Code (claude-opus-5-5), autonomous development window
Project: Ridge
Branch: `m4-sidecar` (built on `m3-minutiae`) → PR into `main` after PRs #4 and #5

## 1. Scope

**M4 backend:** the Python sidecar the Tauri GUI will drive (architecture §7.3, ADR-002; PRD SEC-1, SEC-2, SEC-8).

| Part | What |
| --- | --- |
| `ridge.sidecar.protocol` | JSON-RPC 2.0 framing: messages ≤ 1 MiB, UTF-8, duplicate keys and NaN/Infinity refused. Only objects with `jsonrpc`/`id`/`method`/`params`; no batches or notifications. Method allow-list, per-method schemas (unknown, missing or mistyped fields refused; bool never accepted as a number). Request id echoed on errors |
| `ridge.sidecar.handlers` | One session per process: unlock (UUID case id, absolute store path), lock, items, import (absolute path), job.run (all job options incl. ruler and minutiae), verify, export (absolute destination), preview (bounded downscaled PNG, read logged) |
| Idle auto-lock | The session locks itself after 15 minutes without requests (injectable clock; `session.status` reports it). Test: `test_idle_session_locks_itself` |
| `ridge.sidecar.server` | `ridge-sidecar`: serves until stdin closes, then locks the case. Oversized lines are discarded without losing sync. Errors answered safely (-32000 safe message, -32603 exception type only) |

The Tauri Rust core and the React/TypeScript WebView are **not built yet**. Their rules are in `Instruction_documentation/desktop_gui_tauri_standards.md`. Key point: the passphrase must come from a native prompt in the Rust core, never from WebView code.

## 2. Evidence

- `tests/test_sidecar.py`: 14 malformed-request cases, unsafe unlock parameters, wrong passphrase, the full workflow (unlock → import → job with ruler and minutiae → preview → export → verify → lock), the stream with oversized lines, safe internal errors, and the binary stdio entry point.
- The offline test (`tests/test_offline.py`) covers the new package (no network imports).
- The full gate run is recorded in the PR.

## 3. Forensic and security impact

- No change to extraction, exports or records.
- Previews put biometric pixels on the IPC channel to the GUI, by design for review; each preview read is logged in the custody log.
- The sidecar trusts its parent (the Rust core) to filter WebView requests; it still validates every argument (defence in depth).

## 4. Open items

- Tauri v2 shell: capability allow-list, CSP, native passphrase prompt, packaging the sidecar (PyInstaller) and signing.
- The React UI, with Motion animations that respect `prefers-reduced-motion`, and WCAG 2.2 AA.

## 5. First thing to do

Run `python tools/gate.py all`, then read architecture §7.3 and `desktop_gui_tauri_standards.md`.
