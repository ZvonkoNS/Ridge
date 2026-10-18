# Handoff_26.md

Date/time (ISO 8601 with offset): 2026-10-18T20:00+02:00
Author/agent: Claude Code (claude-opus-5-5)
Project: Ridge
Branch: `m5-release-12` → `main`
Base commit: `253f4bd` (Merge pull request #24, Handoff_25)
Latest commit: see the pull request

## 1. Scope

Requested change: "build and smoke-test the installer — everything turnkey ready" (product owner, 2026-10-18).

PR #24 (Handoff_25) was merged at `253f4bd`. Before the merge, its three Codex findings were fixed in `3202bfa` (recorded in Handoff_25 §1), answered and resolved, and both CI and the local gate were green.

This handoff records the final Windows installers, built from that merge. No code changes.

| Artifact | Size | SHA-256 |
| --- | --- | --- |
| `Ridge_0.2.0_x64_en-US.msi` (WiX 3.14, per machine) | 86,045,758 bytes (82.06 MiB) | `cbbcb6218fe533d434195e97ee507649ac8b00caeea7e1870557d2b3ba19dab8` |
| `Ridge_0.2.0_x64-setup.exe` (NSIS 3.11, per user, no administrator rights) | 60,174,512 bytes (57.39 MiB) | `71e7828332c5703c83aef634ecd84da7e5c8428a573cd4744d1dfc34e3c01b61` |

Build, from a clean checkout of `main` at `253f4bd`:

1. `python tools/build_sidecar.py`: frozen archive checked (Windows keystore backend present). The smoke test answered `Ridge 0.2.0 253f4bdc5b4be024f04d948413cdf63d6eaab762`.
2. `npm ci` in `gui/`.
3. `npx tauri build --config src-tauri/tauri.release.conf.json`: the release Rust build, then both bundles.

The installers and a `SHA256SUMS.txt` were copied to `Ridge-release-0.2.0-253f4bd/`, next to the repository on the build workstation, outside git.

Smoke test of the per-user NSIS installer on the build workstation:

| Check | Result |
| --- | --- |
| Silent install (`setup.exe /S`) | Exit 0; installed to `%LOCALAPPDATA%\Ridge`, with the engine at `sidecar\ridge-sidecar.exe` |
| Installed engine, `ridge.version` over stdio | `commit 253f4bd…`, `commit_source: build` |
| Installed engine, `recovery.check` with a relative path | Refused (`path must be an absolute path`): the recovery methods are present. No keystore was touched |
| Start the installed app | Window "Ridge"; child processes WebView2 and `ridge-sidecar.exe` |
| Close the app | No engine left running |
| Silent uninstall (`uninstall.exe /S`) | Exit 0; the application folder removed |

Not done:

- Recovery was not exercised end to end in the installed application, because that would write a real device secret into the build workstation's Windows Credential Manager. Recovery is covered by `tests/test_recovery.py`, the sidecar tests and the GUI tests.
- **Code signing.** It needs the laboratory's code-signing certificate. Until then Windows SmartScreen warns on install, and the publisher cannot be verified.
- The MSI was built but not installed: a per-machine install needs administrator rights.
- macOS and Linux bundles.

## 2. Current repository state

- `main` is at `253f4bd`. This branch adds this handoff only.

## 3. Standards applicability and evidence

| Standard/control/rule | Applies? | Evidence produced | Exception/deviation |
| --- | --- | --- | --- |
| Release checklist (artifacts, `SHA256SUMS`, smoke test) | Yes | Hashes and smoke test above | Unsigned installers (profile exception, pending certificate) |
| Reproducibility (NFR-3), the build's own reproducibility | Partly | PyInstaller and the bundlers embed timestamps, so the installers are not bit-reproducible; the release records their SHA-256 instead (architecture §10) | Documented |

## 4. Forensic impact

- None: no code change. The installed engine reports its build commit, which reports record (FR-34).

## 5. Files changed

- `Instruction_documentation/Handoff/Handoff_26.md` (new).

## 6.–8. Data store, configuration, security

- No changes.
- Open: code signing, the NVDA pass, the laboratory procedures (recovery custody, countersigned heads), and an independent DPO and FQM before casework.

## 9. Tests

- No new tests.
- The release commit itself: `python tools/gate.py all` was run on a detached checkout of `253f4bd` (Windows 11 x86-64, Python 3.13.5) after the installers were built:

  ```
  === all 11 gate(s) passed: docs, lint, format, typecheck, test, sast, deps, secrets, licenses, sbom, gui
  ```

  - pytest: 777 passed, 3 skipped, branch coverage 97.51%.
  - Vitest: 95 passed.
  - Rust: 34 passed.

  `253f4bd` has the same tree as `3202bfa`, the gated head of PR #24.

## 10. Release readiness

- Installable Windows build: yes, unsigned.
- Before casework use:
  - code signing;
  - the NVDA pass (`docs/screen_reader_test.md`);
  - method validation (OQ-6, OQ-15);
  - independent DPO and FQM;
  - the laboratory procedures.

## 11. Open risks and known issues

- Unsigned installers.
- Interim combined owner roles.

## 12. Recommended next work

1. Sign `ridge-sidecar.exe`, `ridge-gui.exe` and both installers with the laboratory's certificate, then rebuild the checksums.
2. Run the NVDA script on the installed build and record the result.
3. Rehearse a recovery restore into a fresh test account with a synthetic store.

## 13. First thing the next agent/developer should read or do

Read this handoff and Handoff_25. Verify the installers against `SHA256SUMS.txt` before installing.
