# Handoff_21.md

Date/time (ISO 8601 with offset): 2026-10-18T10:30+02:00 (autonomous development window, continued)
Author/agent: Claude Code (claude-opus-5-5)
Project: Ridge
Branch: `m4-gui-7` → `main`
Base commit: `cbeee62` (Merge pull request #19, Handoff_20)
Latest commit: see the pull request

## 1. Scope

Requested change: continue autonomous development (product owner, 2026-10-18), sparing GitHub Actions. PR #19 (Handoff_20) was merged at `cbeee62`. Before the merge, its four Codex findings were fixed in `c493c8d` (recorded in Handoff_20 §1), answered and resolved, and both CI and the local gate were green.

Completed work on this branch:

| Area | What |
| --- | --- |
| Workstation check | `ridge-case workstation --store S [--register R] [--json]`, sidecar `store.workstation`, Tauri `workstation_check`, and a store-screen card ("This workstation"). It reports the build commit, the platform and whether its architecture has reference results, libraries and HEIF support, whether the OS keystore holds the device secret (only looked up, never shown), the identity, the store's cases by state, and the limits of use (signature, covered architectures, NFIQ 2 minimum). With `--register` it also says whether the store's key is registered. Each finding is ok, note or problem; the command exits 1 on a problem. It reads only, and it validates nothing |
| Hardening | `identity.json` and `case.json` are read within a 64 KiB bound. Every malformed form is an `IntegrityError`: not JSON, not UTF-8, missing fields, or broken base64. Before, they raised a raw JSON, key or base64 error, which was an internal error in the sidecar and stopped `verify-store`. `unlock_identity` reads the file once |
| Custody log search | Sidecar `log.entries` takes `text` (1–100 characters, case-insensitive); GUI Records search box for a hash, a job id or note text |
| JSON for scripts | `ridge-case jobs --json`, `ridge-case notes --json` |
| About Ridge | Case-screen dialog: version and commit, what Ridge is and is not, where data lives, how exported files are checked. One `Dialog` component now holds the focus, Escape and Tab handling for it and the shortcut list. Self-review after the pull request opened found that a re-render briefly moved focus to the opener; `1ac2e5e` keeps the latest `onClose` in a ref, so the focus handling runs once per opening (`dialog.test.tsx`) |
| Code health | `src/ridge/case/case_model.py` takes the case records and rules out of `store.py` (381 → 317 lines): file names and schemas, roles, `CaseMeta`, `StoredItem`, text validation and `publish_logged`. Callers import them from there |

Codex review of PR #20 (two P2 findings), fixed on this branch:

- a missing `kdf` field in `identity.json` or `case.json` still raised a raw `KeyError`, which stopped `verify-store`. The field is now read inside the malformed-record boundary, an `IntegrityError` (`test_store_verify.py::test_a_case_file_missing_a_field_is_a_fault_not_a_crash`, plus a missing-`kdf` case in each malformed-file test);
- the dialog focus finding is the one already fixed in `1ac2e5e` (above).

Out of scope (unchanged):

- installer build and code signing;
- Tauri WebDriver E2E;
- manual screen-reader pass;
- ADR-012 (owner decision).

## 2. Current repository state

- `main` is at `cbeee62`. This branch is ahead of it; see the pull request.
- No new dependencies or tools.

## 3. Standards applicability and evidence

Project standards profile updated: no new exception.

| Standard/control/rule | Applies? | Evidence produced | Exception/deviation |
| --- | --- | --- | --- |
| OWASP ASVS V5 (input validation), CWE-20, CWE-400 | Yes | Bounded reads and typed refusals for `identity.json` and `case.json`: `test_case_crypto.py` (10 malformed forms), `test_case_store.py` (6) | None |
| Key management (ADR-004), CWE-200 | Yes | The workstation check never shows the device secret and creates nothing: `test_workstation.py` checks that no secret bytes appear and that the keystore and store are unchanged | None |
| ISO/IEC 17025 7.11 (control of data and software, information only) | Partly | The workstation check states the build, platform and limits coverage. It says on its face that it does not validate the method or the installation | Method validation stays open (OQ-6, OQ-15) |
| WCAG 2.2 AA | Yes | Workstation findings carry their level in words as well as colour; About dialog focus handling; axe checks in Vitest | Manual screen-reader pass open |

## 4. Forensic impact

- Output pixels changed: no.
- Recorded parameters: unchanged.
- Examiner-facing wording: the workstation check ("it does not validate the method or the installation"), About Ridge ("does not identify anyone or decide whether prints match").
- Data classes: synthetic data only.

## 5. Files changed

See the pull request. Main areas:

- `src/ridge/case/workstation.py` (new), `case_model.py` (new), `store.py`, `identity.py`, `cli_store.py`, `cli_notes.py`, `cli_records.py`;
- `src/ridge/sidecar/`;
- `gui/src-tauri/src/commands/store.rs`, the allow-lists;
- `gui/src/` (WorkstationCheck, Dialog, AboutRidge, CustodyLog);
- tests;
- `docs/architecture.md`, README, CHANGELOG.

## 6. Data store, records and formats

- No migration and no new format. Existing stores, cases and identities open unchanged.

## 7. Configuration, keys and CI

- No changes.

## 8. Security

- The workstation check reads the OS keystore entry to say whether it is present; the value is discarded and never shown, logged or sent to the WebView.
- Open: ADR-012 (device-secret recovery), ADR-010 review, unsigned installer.

## 9. Tests

- Added:
  - Python: `test_workstation.py` (8), malformed identity (10) and case files (6), `jobs`/`notes --json`, log search;
  - Vitest: workstation card (2), About Ridge (1), log search (1), dialog focus across re-renders (1).
- Changed: the notes Vitest flow (it types two notes and runs axe) has a 15 s timeout. It took 5.27 s against the 5 s default in the first gate run, while other test runs loaded the machine.
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

- Until ADR-012 is decided, losing an examiner's OS keystore loses that examiner's cases. The workstation check now shows when the secret is missing.
- Custody log search matches the entry's JSON text, so a field name such as `sha256` matches every entry that has one.

## 12. Recommended next work

1. Decide ADR-012, OQ-8 and OQ-9.
2. Release dry run: frozen sidecar, installer build, code signing.
3. Manual screen-reader pass (NVDA, VoiceOver) of the store and case screens.

## 13. First thing the next agent/developer should read or do

Run `python tools/gate.py all`. Read `CHANGELOG.md` and ADR-012.
