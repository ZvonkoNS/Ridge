# Handoff_19.md

Date/time (ISO 8601 with offset): 2026-10-18T08:40+02:00 (autonomous development window, continued)
Author/agent: Claude Code (claude-opus-5-5)
Project: Ridge
Branch: `m4-gui-5` → `main`
Base commit: `a238076` (Merge pull request #17, Handoff_18)
Latest commit: see the pull request

## 1. Scope

Requested change: continue autonomous development (product owner, 2026-10-18), sparing GitHub Actions. PR #17 (Handoff_18) was merged at `a238076` after its local gate and CI were green.

**PR #17 review fixes**, merged with PR #17 and recorded here as Handoff_18 promised:

- `check-log --register` now takes the time from the signed `log.export` entry, not the unsigned envelope.
- The sidecar answers input refusals with their own code, -32001. A batch import continues only after those; a custody, storage or lock failure ends it.
- With `--html` and `--register` the signer is checked before a readable copy is written.

Completed work on this branch:

| Area | What |
| --- | --- |
| Check exported files | GUI store-screen card and `ridge-case check PATH` verify a report, processing record, custody head, key card, key register, limits file or package folder by its schema (sidecar `files.check`, Tauri `check_exported` with native dialogs). With a key register, the signer is named. No store is needed and nothing is written |
| Case summary | `ridge-case status [--json]`, sidecar `case.status`, and a "Case summary" card at the top of Records: stored items by role, jobs by outcome, signed reports, notes, the last verification and the last custody-head export. It reads only |
| Store backups | `ridge-case backup` / `check-backup` and GUI "Back up this store...". The backup is an encrypted byte copy into a new folder, copied in chunks, with `BACKUP-MANIFEST.json`. No passphrase is needed. A folder that is not a Ridge store, open or disposing cases and links are refused; every other case is locked during the copy. **A backup does not hold the OS-keystore device secret** (stated in the CLI, the GUI and the docs) |
| Commit in reports (FR-34) | `ridge.build_info`: the release build stamps the commit and a dirty flag into the frozen sidecar (`tools/build_sidecar.py`); a development checkout reads git's files, without running git; otherwise `unknown`. Reports record `commit` and `commit_source`, and the text, HTML and GUI views show them |
| Measure | A view-only tool in report and job-result viewers. Two points give their distance in pixels. Millimetres appear only where the output's scale is known (comparison export, or print through the scale-bar scale), with the method and uncertainty. Nothing is recorded |
| JSON outputs | `overview --json`, `status --json`, `verify --json`, `verify-store --json`, for laboratory scripts and monitoring |
| CLI parity | `notes --item`, `log --kind`, and note counts per job in the GUI jobs list |
| Docs | `docs/verification_guide.md` for reviewers, the DPO and the FQM; `CHANGELOG.md` (forensic impact, known issues); four STRIDE rows covering keys, packages and limits, HTML copies and backdating |
| Review fixes (PR #18, Codex) | A key card checked with a register must be registered for its role, valid on its signed date, and registered to the holder it names. A backup destination inside the store is refused, as is a folder that is not a store, and every case is locked during the copy. The case summary, last-verified line and custody log reload after every logged action. Measure points are cleared when a new job result replaces the image |
| Code health | `prompt.rs` split into the broker and `prompt_calls.rs`, one sidecar call per purpose |

Out of scope (unchanged):

- installer build and code signing;
- Tauri WebDriver E2E;
- manual screen-reader pass.

## 2. Current repository state

- `main` is at `a238076`. This branch is ahead of it; see the pull request.
- No new dependencies or tools.

## 3. Standards applicability and evidence

Project standards profile updated: no new exception.

| Standard/control/rule | Applies? | Evidence produced | Exception/deviation |
| --- | --- | --- | --- |
| ISO/IEC 27037 preservation | Yes | Encrypted backups with a hash manifest; `tests/test_backup.py` (edit, add, remove, manifest; an open case refused; the copy opens) | Device-secret backup is a laboratory procedure (open item) |
| PRD FR-34 (version and commit) | Yes | `tests/test_build_info.py` (branch, packed refs, worktree, detached, traversal, unknown) | None |
| ISO/IEC 17025 §7.5, §7.11 | Yes | Case summary, verification JSON, file checks naming the signer; `tests/test_file_check.py`, `tests/test_case_status.py` | None |
| OWASP ASVS V5, V12 (files) | Yes | Backups refuse links and unsafe manifest paths; file check dispatches only known schemas | None |
| WCAG 2.2 AA | Yes | axe checks on the check-files card; status regions for the measuring readout | Manual screen-reader pass open |
| `desktop_gui_tauri_standards.md` §3, §4 | Yes | New commands (`check_exported`, `case_status`, `backup_store`) are allow-listed and validated; dialogs are opened by the Rust core | None |

## 4. Forensic impact

- Output pixels changed: no.
- Recorded parameters: unchanged.
- Reports gain `ridge.commit` and `ridge.commit_source`. Reproduction lists a different commit as an environment change, as intended.
- New files:
  - `BACKUP-MANIFEST.json` (`ridge.store-backup/1`);
  - `ridge/_build.json` inside the frozen sidecar.
- Examiner-facing wording:
  - Measure says "View only; nothing is recorded" and gives millimetres only with a known scale and its uncertainty;
  - backups say they lack the OS-keystore secret.
- Data classes: synthetic data only.

## 5. Files changed

See the pull request. Main areas:

- `src/ridge/`:
  - new: `build_info.py`, `case/file_check.py`, `case/case_status.py`, `case/backup.py`;
  - changed: CLI modules, `jobs.py`, `reports.py`, `report_html.py`;
- `src/ridge/sidecar/`;
- `tools/build_sidecar.py`;
- `gui/src-tauri/src/` (`prompt_calls.rs`, `check_exported`, `case_status`, `backup_store`, `dialogs::pick_file`);
- `gui/src/` (CheckFiles, CaseSummary, Measure, store backup);
- tests;
- docs (`verification_guide.md`, `CHANGELOG.md`, architecture, PRD).

## 6. Data store, records and formats

- No migration.
- Backups write only into a new folder.
- File checks and the case summary write nothing.

## 7. Configuration, keys and CI

- No configuration keys and no CI changes.
- The release build needs `git` to stamp the commit.

## 8. Security

- STRIDE rows added for key spoofing, package and limits tampering, HTML copies and backdating.
- Backups are byte copies of encrypted files. Restoring needs the per-account device secret. That secret has no backup procedure yet: **a recommended next step that needs an owner decision** (escrow under a recovery passphrase versus an IT-managed keystore backup).

## 9. Tests

- Added:
  - Python: `test_file_check.py` (14), `test_case_status.py` (2), `test_backup.py` (9), `test_build_info.py` (7), and more cases in the notes, store-verify and store-overview tests;
  - Rust: input-refusal mapping, batch predicate;
  - Vitest: check files (2), case summary, store backup, jobs note counts, measuring (3).
- Commands: `python tools/gate.py all` on this branch; the result is recorded in the pull request.
- Dev preview checked in the built-in browser with synthetic data: check-files card, Measure on the comparison export.
- The frozen sidecar was built and smoke-tested on Windows. The engine's `ridge.version` now reports `commit` and `commit_source`, the GUI footer shows the short commit, and the build refuses a bundle without the stamp.
- Not run:
  - `tauri build` installers;
  - GUI on Linux and macOS;
  - WebDriver E2E;
  (the frozen sidecar was rebuilt with `tools/build_sidecar.py`. The bundle answered `ridge.version` with its build-stamped commit, and the smoke test checks that stamp.)

## 10. Release readiness

- Internal engineering build.
- Not ready for casework (M5).
- GUI release blockers unchanged: installer and signing, E2E, screen-reader pass, ADR-010 review, owner names.

## 11. Open risks and known issues

- The device secret is not covered by backups (§8).
- `commit_source: checkout` cannot rule out uncommitted changes; release builds record a dirty flag.

## 12. Recommended next work

1. Owner decision on device-secret recovery, then implement it.
2. A release dry run: `tools/build_sidecar.py` (checks the commit stamp), the installer build and code signing.
3. Decide OQ-8 and OQ-9 (countersigned heads, key register keeper).

## 13. First thing the next agent/developer should read or do

Run `python tools/gate.py all`, then read `docs/verification_guide.md` and `CHANGELOG.md`.
