# ADR-011: Hand-written IPC types checked by tests; no Tauri isolation pattern for now

| Field | Value |
| --- | --- |
| Status | Accepted (2026-10-18) |
| Context | `desktop_gui_tauri_standards.md` §4 (isolation pattern) and §7 (IPC type generation): the two GUI decisions it left open |

## Decision 1: IPC types

The request and result types of the 27 Tauri commands are **written by hand** on both sides:

- Rust request structs use `#[serde(deny_unknown_fields)]`;
- TypeScript types live in `gui/src/ipc/types.ts`.

They are not generated. Correctness is enforced instead by:

- the Rust request types themselves, plus unit tests that refuse unknown fields, wrong types and out-of-range values;
- the sidecar's own schemas, which refuse unknown or mistyped parameters (Python tests);
- Vitest tests that check the exact request shape each wrapper sends (`gui/src/test/ipc.test.ts`);
- a live test in which the Rust core talks to the real sidecar over stdio (`sidecar::tests::the_real_sidecar_answers_over_stdio`).

Generators such as `specta` or `ts-rs` would add build-time dependencies and code generation for 27 small types. Revisit when the IPC surface grows or a type mismatch slips through.

## Decision 2: Tauri isolation pattern

The isolation pattern injects a sandboxed iframe that can inspect and modify IPC messages before they reach the core. **It is not adopted for now**, because:

- every command already validates its input in Rust;
- the sidecar validates everything again;
- the WebView loads no remote content and runs a strict CSP;
- the npm dependency set is small, pinned and audited, and lifecycle scripts are disabled.

The isolation pattern would mostly protect against a compromised npm dependency tampering with IPC calls. The Rust-side validation already bounds what such a call can do: no paths, no passphrases, and only the allow-listed commands.

Revisit if a third-party UI component with a large dependency tree is added, or before the first release if the Security Owner asks for it.
