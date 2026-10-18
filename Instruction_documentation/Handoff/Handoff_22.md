# Handoff_22.md

Date/time (ISO 8601 with offset): 2026-10-18T11:30+02:00 (autonomous development window, continued)
Author/agent: Claude Code (claude-opus-5-5)
Project: Ridge
Branch: `m4-gui-8` → `main`
Base commit: `d32f0ff` (Merge pull request #20, Handoff_21)
Latest commit: see the pull request

## 1. Scope

Requested change: continue autonomous development (product owner, 2026-10-18), sparing GitHub Actions. PR #20 (Handoff_21) was merged at `d32f0ff`. Before the merge, its two Codex findings (a missing `kdf` field, dialog focus on re-render) were fixed in `3a687b4` and `1ac2e5e` (recorded in Handoff_21 §1), answered and resolved, and both CI and the local gate were green.

Completed work on this branch:

| Area | What |
| --- | --- |
| Backups in the generic check | A folder holding `BACKUP-MANIFEST.json` is checked as a store backup: every file against the manifest. GUI "Check a package or backup folder..." and `ridge-case check FOLDER` verify backups as well. The Rust core allows a folder check up to an hour, because a backup is rehashed file by file. Verification guide row added |
| Workstation check | The GUI can include the key register (checkbox and native dialog opened by the Rust core). `ridge-case workstation --nfiq2 PATH [--nfiq2-arg ...]` says whether the NFIQ 2 tool is at its absolute path and which version it reports; it is asked only `--version` and never sees an image |
| Hardening | Disposal reads `case.json` and disposal records within 64 KiB. `check-package` reads each report once (bounded) and verifies and hashes the same bytes |
| Custody log view | A slow answer to an older filter or search is dropped (generation counter), so it can never replace or extend the entries of a newer query (`custody.test.tsx`) |
| About Ridge | Also on the store screen, before any store is chosen |
| Code health | The new-case form moved out of `StoreScreen.tsx` (321 → 273 lines; 295 with the About button) into `NewCaseForm.tsx`, with its first test |
| Threat model | STRIDE row for the workstation check and malformed identity or case files |

Codex review of PR #21 (one P2 finding), fixed on this branch: an NFIQ 2 tool that exists but cannot run (no execute permission, not a program, timeout, too much output) was reported only as a note, because `version()` swallows those errors. The new `Nfiq2.ask_version()` lets them through. The workstation check now reports a tool that cannot run, or that exits non-zero on `--version`, as a problem; only a clean run without a version line is a note (`test_workstation.py`).

Out of scope (unchanged):

- installer build and code signing. **The first `tauri build` downloads WiX/NSIS from the internet and was therefore not run unattended**;
- Tauri WebDriver E2E;
- manual screen-reader pass;
- ADR-012 (owner decision).

## 2. Current repository state

- `main` is at `d32f0ff`. This branch is ahead of it; see the pull request.
- No new dependencies or tools.

## 3. Standards applicability and evidence

Project standards profile updated: no new exception.

| Standard/control/rule | Applies? | Evidence produced | Exception/deviation |
| --- | --- | --- | --- |
| OWASP ASVS V5, CWE-400, CWE-367 | Yes | Bounded disposal reads. A packaged report is verified and hashed from one read: `test_package.py` passes unchanged | None |
| ISO/IEC 27037 (integrity of copies) | Yes | Backup check through the generic path: `test_backup.py` (a pass, an added file refused) | None |
| ISO/IEC 29794-4 scope note (NFIQ 2 indicative) | Yes | The workstation finding says scores are indicative. `test_workstation.py` covers a found tool, no version, a missing path and a relative path (refused, never searched on PATH) | Existing scope exception (photos outside NFIQ 2's scope) |
| WCAG 2.2 AA | Yes | Labelled register checkbox; axe check of the new-case form | Manual screen-reader pass open |

## 4. Forensic impact

- Output pixels changed: no.
- Recorded parameters: unchanged.
- Examiner-facing wording: backup check lines ("every file matches the manifest", "the manifest is not signed", the OS-keystore secret), NFIQ 2 finding ("indicative only").
- Data classes: synthetic data only.

## 5. Files changed

See the pull request. Main areas:

- `src/ridge/case/file_check.py`, `workstation.py`, `cli_store.py`, `cli_register.py`, `dispose.py`, `package.py`;
- `gui/src-tauri/src/commands/records.rs`, `store.rs`;
- `gui/src/screens/` (CheckFiles, WorkstationCheck, NewCaseForm, StoreScreen);
- tests;
- `docs/architecture.md`, `docs/verification_guide.md`, `docs/prd.md` (FR-26: backups; OQ-15: workstation check), README, CHANGELOG.

## 6. Data store, records and formats

- No migration and no new format.

## 7. Configuration, keys and CI

- No changes.

## 8. Security

- The NFIQ 2 version query runs the configured executable only at its absolute path, with an argv list and no shell, and limits its output, as jobs already do.
- Open: ADR-012 (device-secret recovery), ADR-010 review, unsigned installer.

## 9. Tests

- Added:
  - Python: backup through `check` / `check_exported`, NFIQ 2 workstation check;
  - Vitest: register checkbox and a closed dialog, the new-case form, a slow custody-log answer dropped, About Ridge on the store screen.
- Commands: `python tools/gate.py all` on this branch; the result is recorded in the pull request.
- Not run:
  - `tauri build` installers;
  - GUI on Linux and macOS;
  - WebDriver E2E.

## 10. Release readiness

- Internal engineering build.
- Not ready for casework (M5).
- Blockers unchanged.

## 11. Open risks and known issues

- The installer has never been built. The first run of `npx tauri build --config src-tauri/tauri.release.conf.json` downloads Tauri's WiX and NSIS tools; a person should run it once and record the result.
- A store backup's manifest is not signed (documented). Integrity of case contents rests on each case's custody chain and signatures.

## 12. Recommended next work

1. Decide ADR-012, OQ-8 and OQ-9.
2. Run the release dry run by hand: `python tools/build_sidecar.py`, then `npx tauri build --config src-tauri/tauri.release.conf.json`. Record the installer's SHA-256 and a manual smoke run.
3. Manual screen-reader pass (NVDA, VoiceOver).

## 13. First thing the next agent/developer should read or do

Run `python tools/gate.py all`. Read `CHANGELOG.md`, `docs/verification_guide.md` and ADR-012.
