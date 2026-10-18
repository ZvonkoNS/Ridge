# Handoff_15.md

Date/time (ISO 8601 with offset): 2026-10-18T03:30+02:00 (autonomous development window started 2026-10-18 about 01:30+02:00)
Author/agent: Claude Code (claude-opus-5-5)
Project: Ridge
Branch: `m4-gui` → `main`
Base commit: `eca5087` (Merge pull request #13)
Latest commit: see the pull request

## 1. Scope

Requested change: the product owner asked for 12 hours of autonomous development ("as many features as possible") with full authority to decide, and to be **extremely sparing with GitHub Actions**.

Completed work on this branch:

| Area | What |
| --- | --- |
| Desktop GUI (M4, FR-50 to FR-53) | **`gui/`, Tauri 2.12.1 + React 19 + TypeScript 6 + Motion 14.** The Rust core spawns the sidecar over stdio. It exposes 29 allow-listed commands with `deny_unknown_fields` requests and validation, opens native dialogs from Rust (the WebView never sends a path), runs a passphrase prompt window (ADR-010), limits navigation to the app origin, denies new windows, and remembers the last store. The WebView provides the store screen (first-run identity, cases, new case) and the case screen: evidence import, side-by-side review with exhibit labels and live scale bars, keyboard viewer, region and ruler tools, jobs with verified reports, export and reproduction, references and comparison sheets, verify, legal hold, processing record, stored items with export. Architecture §7.3 describes it |
| Sidecar | `handlers.py` (402 lines) is split into `session.py`, `store_methods.py`, `case_methods.py` and `job_methods.py`; `handlers.py` keeps the registry only. New methods: `store.identity`, `store.limits`, `case.info`, `case.hold`, `preview.region`, `minutiae.get`. `preview.get` also returns the size of the source image |
| Fix | `OpenCase.set_legal_hold` did not add the `case.hold` entry to the open case's `entries`. In a long-lived session (the sidecar), a processing record exported after a hold therefore failed its own sequence check. Regression test: `test_a_hold_in_an_open_session_keeps_verify_and_records_intact` (it failed before the fix) |
| Limits of use (PRD §12 item 8) | `src/ridge/case/limits.py`. The file is `limits-of-use.json` in the store, placed by the Forensic Quality Manager; Ridge ships none. The parser is strict and fails closed. Each job records the file's hash in `job.start` and a `limits_of_use` section in the signed report, with plain-language warnings. A job outside the limits is not refused. CLI: warnings in `extract`, `ridge-case limits --store / --check`, and the section in the report text view. GUI: the job outcome and a limits card |
| Minutiae overlay (FR-40) | GUI overlay on the print or the export: off by default, a logged read, circles for endings and squares for bifurcations, labelled unvalidated and orientation-only |
| Gates | `python tools/gate.py gui` (`tools/gate_gui.py`, part of `all`) runs: npm ci, ESLint (strict type-checked), tsc, Prettier, Vitest with axe, build, a check that the development preview is absent from the build, npm audit, npm licences, cargo fmt, clippy `-D warnings`, cargo test (including a live Rust↔sidecar test), cargo-audit and cargo-deny |
| CI (minimal Actions) | `ci.yml` ignores `gui/**`. New `gui.yml` runs the GUI gate **on demand and for release tags only**. No new workflow runs on pull requests |
| Docs | ADR-010 (passphrase prompt window), ADR-011 (hand-written IPC types, no isolation pattern yet); architecture §5, §7.3, §8.1, §8.3, §13; PRD FR-40, FR-50 to FR-53, §12; standards profile (GUI stack, ES2022 target, exceptions); GUI standards status; write-path audit P6, P9; README |

Out of scope:

- release packaging of the sidecar (signed PyInstaller one-folder build in the Tauri bundle);
- Tauri WebDriver E2E;
- a manual screen-reader pass;
- OS-native passphrase dialogs.

All four are recorded as exceptions in the standards profile.

## 2. Current repository state

- Branch `m4-gui`, pushed. The pull request lists the commits.
- Local tool additions on the development workstation:
  - Rust 1.98.0, installed next to the default toolchain and pinned by `gui/src-tauri/rust-toolchain.toml`; the default was not changed;
  - `cargo-audit` 0.22.2 and `cargo-deny` 0.20.2 in `~/.cargo/bin`;
  - rustup updated itself to 1.29.1 during the toolchain install.

## 3. Standards applicability and evidence

Project standards profile updated: yes (section 3 GUI stack and ES2022 target; section 5 TypeScript and Rust rows; section 7 evidence rows; section 8: GUI rules closed and new exception rows).

| Standard/control/rule | Applies? | Evidence produced | Exception/deviation |
| --- | --- | --- | --- |
| `desktop_gui_tauri_standards.md` §1–§13 | Yes | Rust capability/CSP/navigation tests; DevTools smoke run on the built app (`tools/gui_smoke.mjs`: inline script blocked by CSP, remote fetch blocked, WebView storage empty, the prompt window cannot call `list_items`, the main window cannot call `passphrase_submit`, `dialog.open` denied, sidecar answered) | Passphrase window instead of an OS dialog (ADR-010); no WebDriver E2E; GUI CI on demand only |
| OWASP ASVS 5.0 (V1 encoding, V2 validation, V5 files, V14 config) for the GUI | Yes | Validation of every WebView value in Rust, then again in the sidecar; no paths from the WebView; strict CSP; no remote content | None new |
| WCAG 2.2 AA (FR-53) | Yes | axe-core in Vitest on the store, case, prompt, limits and inventory views (no violations); keyboard viewer; typed alternatives to dragging (SC 2.5.7); 24 px targets | Manual NVDA/VoiceOver pass not done (exception) |
| Supply chain (SSDF, `desktop_gui_tauri_standards.md` §11) | Yes | Exact npm versions, `ignore-scripts`, `npm audit` (0 vulnerabilities), npm licence allow-list, `Cargo.lock`, cargo-audit, cargo-deny (licences, sources, bans) | Two Linux-only Rust advisories and the MPL-2.0 crates through Tauri, recorded with reasons |
| Forensic UI rules (§6) | Yes | Exhibit labels with SHA-256; "Processed image - not an identification" on every output (test); nearest neighbour above 100 % (test); zoom and interpolation always stated; job parameters shown as signed | None |
| ISO/IEC 17025 7.2.2 (validation limits as warnings) | Yes | Limits-of-use mechanism, 22 tests | Values to come from the validation report |

Standards checks or tools run: see section 9.

Steps outside coding work:

- Security Owner review of ADR-010;
- the Forensic Quality Manager provides the `limits-of-use.json` values after validation;
- the product owner reviews the GUI.

## 4. Forensic impact

- Output pixels changed: **no**. Pipeline, export, minutiae and image I/O are unchanged; the arm64 workflow is not triggered.
- Defaults or recorded parameters changed: no.
- Job reports gain a `limits_of_use` section. Reports without it remain valid, and verification and reproduction are unaffected.
- `job.start` custody entries gain `limits_of_use` (the file hash, or null).
- Revalidation decision required: no (no pixel change).
- Examiner-facing wording, checked against the forbidden claims:
  - outputs say "Processed image - not an identification";
  - the minutiae overlay says "unvalidated … never used for matching";
  - limits wording states deviations from the laboratory's file ("outside the limits of use") and never claims validation by Ridge.
- Data classes: only synthetic data was used. The preview images are drawn procedurally in the browser. No real images were opened, and no OS keystore entry was created on the workstation: the smoke run cancelled the first-run prompt.

## 5. Files changed

See the pull request diff (105 files). Main areas: `gui/` (new), `src/ridge/sidecar/`, `src/ridge/case/limits.py`, `jobs.py`, `reports.py`, `cli.py`, `cli_records.py`, `store.py`, `tools/gate_gui.py`, `tools/gui_icons.py`, `tools/gui_smoke.mjs`, `.github/workflows/`, `docs/`, `Instruction_documentation/`.

## 6. Data store, records and formats

- Report: `limits_of_use` section (architecture §8.3).
- Custody: `job.start.limits_of_use`.
- Store: optional `limits-of-use.json` (plaintext, no personal data).
- No migration is needed: old reports and stores stay valid.
- Write paths: P6 and P9 updated in the write-path audit (GUI exports, remembered store). The GUI adds no other write path.

## 7. Configuration, keys and CI

- New: `RIDGE_DEV_STORE`, read by **debug builds only** to preselect a store for development and E2E. Release builds read only the remembered store.
- The sidecar's environment is scrubbed of `PYTHON*` variables and `PYTHON_KEYRING_BACKEND`.
- Key custody: unchanged. The GUI uses the same identity and case keys through the sidecar.
- CI:
  - `ci.yml` ignores `gui/**`;
  - `gui.yml` is new (on demand and `v*` tags) and pins `actions/setup-node` v7.0.0 at commit `820762786026740c76f36085b0efc47a31fe5020`, resolved through the GitHub API;
  - `.gitleaks.toml` skips untracked GUI build output.

## 8. Security

- Trust boundaries (architecture §7.3):
  - TB2 (WebView → Rust): capability per window, build-time command allow-list, label checks, typed requests;
  - TB3 (Rust → sidecar): bounded lines, timeouts, a version check, no retries.
- Threat-model notes:
  - a compromised main WebView cannot reach the passphrase, paths, the dialog plugin or the network (CSP `connect-src` is limited to IPC);
  - service workers are blocked (`worker-src 'none'`), so the prompt window's page cannot be intercepted.
- Found and fixed while testing a release build:
  - WebView2 honoured `WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS=--remote-debugging-port=…` in release builds, so a same-user process could attach DevTools and call commands such as `preview` on an unlocked case;
  - release builds now remove the WebView2 and WebKit inspector variables at startup (`WEBVIEW_ENV` in `gui/src-tauri/src/lib.rs`);
  - verified: with the variable set, the release build no longer opens the port.
- Open risks:
  - the ADR-010 residual risk (the prompt is a WebView);
  - the limits file is plaintext and unsigned (its hash is in every report). An FQM signature would make it tamper-evident before use (recommended next step).

## 9. Tests

Tests added:

- Python: `tests/test_sidecar_gui_methods.py`, `tests/test_limits_of_use.py`, `tests/test_limits_cli.py`;
- Rust: 26 unit tests including the live sidecar test;
- Vitest: 37 tests in 7 files, including axe checks.

Commands run (development workstation, Windows 11 x86-64, Python 3.13, Node 22.17, Rust 1.98.0):

```bash
python tools/gate.py all     # result recorded in the pull request
node tools/gui_smoke.mjs 9333 <scratch>   # all checks as listed in section 3
```

- Determinism and golden results: unchanged, because no pixel-affecting code changed.
- Not run:
  - Tauri WebDriver E2E (not implemented);
  - GUI on Linux and macOS (`gui.yml` runs on demand);
  - manual screen-reader pass.

## 10. Release readiness

- Release type: internal engineering build.
- Ready for casework: no (M5).
- Blockers for a GUI release:
  - sidecar packaging;
  - E2E;
  - screen-reader pass;
  - Security Owner review of ADR-010;
  - owner names.

## 11. Open risks and known issues

- The ADR-010 exception (passphrase WebView window).
- The limits-of-use file is unsigned.
- Two Rust advisories ignored (Linux GTK stack).
- MPL-2.0 crates through Tauri.

## 12. Recommended next work

1. Sidecar packaging (PyInstaller one-folder, signed) and a Tauri bundle, then a full-matrix release dry run (`ci.yml` full and `gui.yml`).
2. Signed limits-of-use files (FQM key) and their verification before use.
3. Tauri WebDriver E2E on Windows.

## 13. First thing the next agent/developer should read or do

Run `python tools/gate.py all` (this now includes the GUI gate: Node 22, Rust via the pinned toolchain, cargo-audit and cargo-deny). Then try the GUI:

```bash
python tools/gui_icons.py
cd gui
npm ci
npm run tauri dev
```

Use a synthetic store only.
