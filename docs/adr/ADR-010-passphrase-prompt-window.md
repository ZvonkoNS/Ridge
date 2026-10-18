# ADR-010: The passphrase is entered in a separate prompt window owned by the Rust core

| Field | Value |
| --- | --- |
| Status | Accepted for engineering builds (2026-10-18, autonomous development window). **Security Owner review pending**; recorded as an exception in the standards profile. |
| Context | PRD FR-50, SEC-3, SEC-8; architecture §7.3, §9.2 (TB2); `desktop_gui_tauri_standards.md` §1, §3 |
| Supersedes | The open item "native passphrase prompt per OS" in Handoff_12 and Handoff_13 |

## Context

`session.unlock`, `identity.create` and `case.create` carry the examiner passphrase. Architecture §7.3 says the Rust core sends them "from a native prompt, never from the WebView", because the main WebView renders case data and is untrusted (TB2).

Tauri v2 has no password dialog. A true OS prompt would need different code on each platform:

- Windows: `CredUIPromptForWindowsCredentialsW`, through `unsafe` FFI, which the app crate forbids;
- macOS: an `NSAlert` with an `NSSecureTextField`, through `objc2`;
- Linux: a helper process such as `zenity`, which means shell access.

Only Windows can be tested on the development workstation.

## Decision

The passphrase is typed in a **separate, Rust-owned window** (`passphrase`). That window:

- loads its own bundled page (`gui/passphrase.html`). It shows no case data and no examiner-supplied text except the case reference the examiner just typed;
- has its own capability file (`capabilities/passphrase.json`) with exactly three commands: `passphrase_context`, `passphrase_submit` and `passphrase_cancel`. The main window's capability does not include them. Each handler also checks the calling window's label;
- is owned by the main window, has the same CSP (including `worker-src 'none'`, so no service worker can intercept its page), the same navigation lock and new-window denial;
- sends the passphrase to the Rust core only. The core uses it in the sidecar call itself (`identity.create`, `case.create` + `session.unlock`, or `session.unlock`) and returns only the non-secret result to the waiting main-window command.

Rust holds the passphrase in `Zeroizing` buffers, including the serialised JSON-RPC line. It allows five attempts per prompt, then closes the prompt. A prompt left open for 10 minutes is cancelled.

## Consequences

- The main WebView never receives the passphrase, even if its JavaScript were compromised.
- The prompt is still a WebView, not an OS dialog. Residual risks are:
  - code injected into the bundle at build time (mitigated by the supply-chain controls on npm and Cargo);
  - other same-origin windows. Only Ridge's own two windows exist; new windows are denied and workers are blocked.
- Memory hygiene is best effort. The WebView's own copies of the typed string cannot be zeroised from Rust.
- An OS-native prompt can replace the window later without changing any other code: only `prompt.rs` and `windows.rs` would change, because the broker interface stays (`prompt::ask`).

## Alternatives considered

| Option | Why not now |
| --- | --- |
| Passphrase field in the main window | The main WebView renders case data; it must never see the secret (TB2). |
| OS-native dialogs per platform | `unsafe` FFI or a shell helper. Two of three platforms cannot be tested here. |
| Terminal prompt from the sidecar | No terminal in a desktop app. |
