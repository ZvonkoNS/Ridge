# Handoff_20.md

Date/time (ISO 8601 with offset): 2026-10-18T09:35+02:00 (autonomous development window, continued)
Author/agent: Claude Code (claude-opus-5-5)
Project: Ridge
Branch: `m4-gui-6` → `main`
Base commit: `26e478e` (Merge pull request #18, Handoff_19)
Latest commit: see the pull request

## 1. Scope

Requested change: continue autonomous development (product owner, 2026-10-18), sparing GitHub Actions. PR #18 (Handoff_19) was merged at `26e478e`. Before that, its four Codex threads were fixed in `c06f18e` (recorded in Handoff_19 §1), answered and resolved, and both CI and the local gate were green.

Completed work on this branch:

| Area | What |
| --- | --- |
| Export all (FR-32) | `ridge-case export-all CASE --to NEW_FOLDER [--role ...]`, sidecar `case.export_all`, Tauri `export_all` (role allow-listed in Rust, native dialog for the new folder), and Records inventory buttons "Export all N comparison exports / processed prints...". Each file leaves through the single export path, one `artefact.export` each, under a safe, unique name. `EXPORTS.csv` lists file, SHA-256, role, job and label; labels are kept from being read as spreadsheet formulas (CWE-1236) |
| Copy buttons | Copy the full SHA-256 of inventory items and of a report's input, and the signing key id. A failed copy says so, and the result is announced in a status region for screen readers |
| ADR-012 (proposed) | Recovering the OS-keystore device secret, without which a store backup cannot be opened elsewhere. Four options are compared; the recommendation is a recovery file sealed under a separate recovery passphrase. **Needs a decision by the Security Owner and the product owner**; nothing is implemented |
| Code health | `ridge-case extract` moved to `cli_extract.py`; `cli.py` is back to 254 lines |

Codex review of PR #19 (four P2 findings), fixed on this branch:

- the bulk-export folder is created private (`0o700`);
- file names are distinct without regard to case, using the full SHA-256 and then a counter when a name is taken (hash prefixes can be made to collide);
- a failure part-way keeps the exported files, which are already logged, writes the index of exactly those, and reports "stopped after N of M". A failure on the first file removes the empty folder;
- the copy result is announced in a `role="status"` region (the button's label names the value, so its text change alone was not announced).

Out of scope (unchanged):

- installer build and code signing;
- Tauri WebDriver E2E;
- manual screen-reader pass.

## 2. Current repository state

- `main` is at `26e478e`. This branch is ahead of it; see the pull request.
- No new dependencies or tools.

## 3. Standards applicability and evidence

Project standards profile updated: no new exception.

| Standard/control/rule | Applies? | Evidence produced | Exception/deviation |
| --- | --- | --- | --- |
| PRD FR-32, ISO/IEC 27037 (controlled release of copies) | Yes | Every bulk export is logged per file; `tests/test_export_all.py` (new folder only, unknown role, empty role, unique names, index, sidecar) | None |
| OWASP ASVS V5, CWE-22, CWE-1236 | Yes | Safe file names without path parts; spreadsheet-formula guard in the index | None |
| Key management (ADR-004) | Yes | ADR-012 proposal documents the recovery gap and its options | Decision pending (owner) |
| WCAG 2.2 AA | Yes | Labelled copy buttons and export buttons; Vitest checks | Manual screen-reader pass open |

## 4. Forensic impact

- Output pixels changed: no.
- Recorded parameters: unchanged.
- New file: `EXPORTS.csv` in bulk-export folders (an index; unsigned).
- Examiner-facing wording: "each export is in the custody log".
- Data classes: synthetic data only.

## 5. Files changed

See the pull request. Main areas:

- `src/ridge/case/export_all.py`, `cli_extract.py`, `cli.py`;
- `src/ridge/sidecar/`;
- `gui/src-tauri/src/commands/case.rs`;
- `gui/src/` (Inventory, CopyButton);
- tests;
- `docs/adr/ADR-012-device-secret-recovery.md`, architecture, README, CHANGELOG.

## 6. Data store, records and formats

- No migration.
- Bulk exports write into a new folder only.

## 7. Configuration, keys and CI

- No changes.

## 8. Security

- Bulk export adds no new path for data to leave the store: it calls the single logged export path once per item.
- Open: ADR-012 (device-secret recovery), ADR-010 review, unsigned installer.

## 9. Tests

- Added:
  - Python: `test_export_all.py` (7: also colliding names, and a failure part-way);
  - Vitest: export-all buttons, copy button with its announcement (2).
- Commands: `python tools/gate.py all` on this branch; the result is recorded in the pull request.
- Not run:
  - `tauri build` installers;
  - GUI on Linux and macOS;
  - WebDriver E2E.

## 10. Release readiness

- Internal engineering build.
- Not ready for casework (M5).
- Blockers unchanged; ADR-012 is added to the decisions the owners need to make.

## 11. Open risks and known issues

- Until ADR-012 is decided, losing an examiner's OS keystore loses that examiner's cases.
- `src/ridge/case/store.py` is still 381 lines (pre-existing). Splitting it is recommended before its next behaviour change.

## 12. Recommended next work

1. Decide ADR-012, OQ-8 and OQ-9.
2. Release dry run: frozen sidecar (checked 2026-10-18), installer build, code signing.
3. Split `store.py` by responsibility before its next behaviour change.

## 13. First thing the next agent/developer should read or do

Run `python tools/gate.py all`. Read `CHANGELOG.md`, `docs/verification_guide.md` and ADR-012.
