# Handoff_17.md

Date/time (ISO 8601 with offset): 2026-10-18T06:30+02:00 (autonomous development window, continued)
Author/agent: Claude Code (claude-opus-5-5)
Project: Ridge
Branch: `m4-gui-3` → `main`
Base commit: `179f49d` (Merge pull request #15, Handoff_16)
Latest commit: see the pull request

## 1. Scope

Requested change: continue autonomous development (product owner, 2026-10-18), sparing GitHub Actions. PR #15 (Handoff_16) was merged at `179f49d` after its four Codex threads were fixed and resolved and CI was green.

Completed work on this branch:

| Area | What |
| --- | --- |
| Store verification (FR-24) | `ridge-case verify-store`, sidecar `store.verify` (Rust core only) and GUI "Verify all cases...". One passphrase checks every case: hashes, custody chains and signatures. Each check is logged in its case. Cases that cannot be checked are named, never skipped. A case open in another window makes the store check fail, because it is then incomplete |
| Store overview (FR-26) | `ridge-case overview`, sidecar `store.overview` (Rust core only, prompt purpose `store_overview`) and GUI "Show case details...". With one passphrase it lists every case's reference, retention date, legal hold and evidence/job counts. Cases past retention without a hold are marked. Nothing is written or logged, and nothing is ever disposed |
| Examiner notes (new FR-29) | Custody action `examiner.note` on the case, a job or a stored item. Notes are append-only; a correction is a new note naming the one it corrects. Control characters and bidirectional overrides are refused, in the sidecar and in the Rust core. Available as `ridge-case note` / `notes`, sidecar `note.add` / `notes.list`, Tauri `add_note` / `list_notes`, and a notes panel on each report and in Records |
| Signed limits of use (PRD §12 item 8) | `ridge-case fqm-key` creates the Forensic Quality Manager's passphrase-sealed Ed25519 key, and `ridge-case limits --sign` writes `limits-of-use.json.sig`. A store with a signature has it verified before every job. A changed file, a changed or foreign signature, or a signature without its file stops jobs (fail closed). Reports, the CLI and the GUI name the signing key, to be matched against the laboratory's register |
| Disclosure package | `ridge-case package CASE --to NEW_FOLDER` (GUI → Records) writes the signed processing record, every signed report and a signed RFC 8785 manifest. It contains no images. `ridge-case check-package` verifies offline: the manifest, every file, nothing added or removed, the record, each report's signature, and that each report is the one the custody log signed (a swapped valid report fails even with a re-signed manifest) |
| Review fixes (PR #16, Codex) | A locked case is a store-check problem (CLI exit 1, "NOT CHECKED"). Verification results are scoped to the store they came from. A failure while writing the package manifest is logged as `package.export` failed, and a folder without a signed manifest is refused by `check-package`. A correction keeps the scope of the note it corrects; a conflicting job or item is refused |
| GUI | Keyboard shortcuts: `?` opens a list in a modal that returns focus; Alt+1–4 switch sections; nothing fires while typing. The case screen warns when the retention date has passed without a hold. A report can be compared with another job's report: only the differing settings, input and Ridge version are shown, and the outputs are not ranked. The dev preview mocks the new commands |

Out of scope (unchanged):

- installer build and code signing;
- Tauri WebDriver E2E;
- manual screen-reader pass.

## 2. Current repository state

- `main` is at `179f49d`. This branch is ahead of it; see the pull request.
- No new tools or dependencies.

## 3. Standards applicability and evidence

Project standards profile updated: no new exception. The open item "limits-of-use file is unsigned" (Handoff_16 §8) is closed by signed limits.

| Standard/control/rule | Applies? | Evidence produced | Exception/deviation |
| --- | --- | --- | --- |
| ISO/IEC 17025 §7.5 technical records | Yes | Examiner notes: append-only, attributed, timed, corrections traceable; `tests/test_notes.py` | None |
| ISO/IEC 27037/27042 integrity | Yes | Store verification; disclosure package with signed manifest; `tests/test_store_verify.py`, `tests/test_package.py` (edit, add, remove, swap, re-sign) | None |
| PRD §12 item 8, SEC-9 fail closed | Yes | Signed limits with tamper tests (`tests/test_limits_signing.py`) | Key register is organisational (out of band) |
| LED Art. 4(1)(e), 5 retention | Yes | Store overview and retention warning; Ridge never disposes on its own | None |
| CWE-150, Trojan Source (CVE-2021-42574 class) | Yes | Notes refuse control characters and bidi overrides; CLI output sanitised | None |
| WCAG 2.2 AA | Yes | axe checks on overview, notes, shortcuts dialog, comparison table | Manual screen-reader pass open |
| `desktop_gui_tauri_standards.md` §3, §4 | Yes | New commands validate in Rust (`validate::note`, UUIDs, hashes) and are in the allow-list and capability; passphrase purposes stay in the prompt window | None |

## 4. Forensic impact

- Output pixels changed: no.
- Recorded parameters: unchanged.
- New records:
  - custody actions `examiner.note` and `package.export`;
  - report field `limits_of_use.signed_by` (absent in older reports; the renderers handle both);
  - file formats `ridge.limits-signature/1`, `ridge.fqm-key/1`, `ridge.package/1`.
- Examiner-facing wording:
  - comparison: "Comparing settings does not rank the outputs";
  - signed limits: "confirm it is the FQM's key";
  - retention: "Ridge never disposes of a case by itself";
  - package: "It contains no images".
- Data classes: synthetic data only. The package deliberately excludes images (data minimisation).

## 5. Files changed

See the pull request. Main areas:

- `src/ridge/case/` (new: `store_verify.py`, `store_overview.py`, `notes.py`, `limits_signing.py`, `package.py`, `cli_store.py`, `cli_notes.py`, `cli_limits.py`, `cli_package.py`; changed: `limits.py`, `cli.py`, `cli_records.py`, `cli_common.py`);
- `src/ridge/sidecar/`;
- `gui/src-tauri/src/` (new commands `store_overview`, `verify_store`, `add_note`, `list_notes`, `export_package`; `validate::note`; `dialogs::new_folder`);
- `gui/src/` (StoreCases, NotesPanel, ShortcutsHelp, JobCompare, ParameterList, records and case screens);
- tests and docs.

## 6. Data store, records and formats

- New files in a store: optional `limits-of-use.json.sig`.
- New exported formats (architecture §8): the signature of the limits file, the FQM key file (kept off examiner workstations) and the disclosure package.
- No migration: old reports without `signed_by` render as before.
- Write paths:
  - package: a new folder that must not exist (native dialog in the GUI);
  - FQM key and signature: never overwrite without `--overwrite`;
  - notes: the custody log only.

## 7. Configuration, keys and CI

- New key type: the FQM signing key (Ed25519, sealed with Argon2id + AES-256-GCM under the FQM passphrase; no OS keystore, so the file moves with the FQM).
- No new configuration keys and no CI changes.

## 8. Security

- Signed limits close the "examiner loosens the limits unnoticed" gap: a changed file stops jobs. Removing the signature is visible in every later report as `signed_by: null`.
- A disclosure package cannot be altered without detection. The custody log binds every report hash, and the log is signed by the examiner key.
- Notes cannot disguise their content (no bidi overrides) and cannot be edited.
- Open (unchanged): ADR-010 review; installer not code-signed.

## 9. Tests

- Added:
  - Python: `test_store_verify.py` (5), `test_store_overview.py` (3), `test_notes.py` (12), `test_limits_signing.py` (12), `test_package.py` (10);
  - Rust: note validation, prompt purpose descriptions;
  - Vitest: store verify, store overview, notes, records (package), limits signer, case keys/retention/comparison.
- Commands: `python tools/gate.py all` on this branch; the result is recorded in the pull request.
- The dev preview was checked in the built-in browser with synthetic data: overview, notes, shortcuts dialog and comparison table.
- Not run:
  - `tauri build` installers;
  - GUI on Linux and macOS (`gui.yml` on demand);
  - WebDriver E2E.

## 10. Release readiness

- Internal engineering build.
- Not ready for casework (M5).
- GUI release blockers unchanged: installer and signing, E2E, screen-reader pass, ADR-010 review, owner names.

## 11. Open risks and known issues

- The FQM key register is organisational: Ridge shows key ids, the laboratory must say which key is its FQM's.
- A package carries its own public key, like reports and records; the key id must be checked out of band (`--key-id`).

## 12. Recommended next work

1. Laboratory procedure for registering examiner and FQM key ids (OQ-9), referenced from the reports.
2. Tauri WebDriver E2E on Windows with synthetic stores.
3. Installer build and code signing.

## 13. First thing the next agent/developer should read or do

Run `python tools/gate.py all`. For the new records, try them on a synthetic store:

```bash
ridge-case note <case> "text" --job <job-id>
ridge-case package <case> --to <new-folder>
ridge-case check-package <new-folder>
```
