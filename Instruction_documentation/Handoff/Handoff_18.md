# Handoff_18.md

Date/time (ISO 8601 with offset): 2026-10-18T07:30+02:00 (autonomous development window, continued)
Author/agent: Claude Code (claude-opus-5-5)
Project: Ridge
Branch: `m4-gui-4` → `main`
Base commit: `73263c6` (Merge pull request #16, Handoff_17)
Latest commit: see the pull request

## 1. Scope

Requested change: continue autonomous development (product owner, 2026-10-18), sparing GitHub Actions. PR #16 (Handoff_17) was merged at `73263c6`. Before that, its four Codex threads were fixed in `3743612`, answered and resolved, and both CI and the local gate were green.

Completed work on this branch:

| Area | What |
| --- | --- |
| Readable reports (FR-28) | `ridge-case report CASE JOB --html PATH`, sidecar `report.export_html` and GUI "Save readable copy..." write an HTML page of a verified report. Every value is escaped, and a CSP allows no scripts, network, images or forms. There are no images. Parameters appear as in the signed JSON, and the job's examiner notes are in their own section, marked as not part of the signed report. The footer names the SHA-256 of the signed JSON, which stays authoritative. Logged as `report.export`, `format: html` |
| Offline readable copies | `check-report --html` and `check-log --html` verify the file first and render from the same bytes they verified. Nothing is written for a file that fails, and an existing file is never replaced. Record and report checks now work on bytes read once |
| Disclosure package | Now also holds a readable copy of each report and `processing-record.html`, listed with their hashes in the signed manifest. `check-package` refuses a report copy without its signed report, and a folder without a signed manifest |
| Custody log view | The GUI Records section shows the custody log newest first, filtered by kind and paged (sidecar `log.entries`, Tauri `custody_log` with validated kinds and page bounds). It also shows when the case was last verified, and by whom |
| Notes on photos | Examiner notes can be kept on an evidence photo, on the Evidence screen. A correction keeps the job or item of the note it corrects; a conflicting one is refused |
| Batch import | One native dialog can import up to 50 evidence photos. Each import is its own logged `case.import`. A refused photo is named and the rest continue; a locked case or a stopped engine ends the batch |
| Store screen | "Find a case" by id, or by reference once the details are read. A filter shows only cases past retention without a hold; the CLI equivalent is `ridge-case overview --due` |
| Key register (OQ-9 tool support) | `ridge.key-register/1` lists each key's holder, role (`examiner` or `fqm`) and validity. `ridge-case register --check` validates it. `check-report`, `check-log`, `check-head`, `check-package` and `limits --check` take `--register`: they name the holder and refuse a key that is unregistered, registered for another role, not yet valid, expired or revoked on the signing day |
| Key cards | `ridge-case key-card` (examiner identity or FQM key) and GUI "Register this key with the laboratory" (prompt purpose `key_card`, sidecar `identity.card`) write a self-signed `ridge.key-card/1` (proof of possession). `ridge-case register-add` checks a card and writes a new register version; the old one is never changed |
| Job comparison CLI | `ridge-case compare-jobs CASE A B` lists only the settings that differ. Both report reads are logged, and outputs are not ranked |
| Fuzzing | `tests/test_fuzz_records.py` fuzzes registers, key cards, limits files and signatures, custody heads, processing records and package manifests. They raise only their typed refusals |

Out of scope (unchanged):

- installer build and code signing;
- Tauri WebDriver E2E;
- manual screen-reader pass.

## 2. Current repository state

- `main` is at `73263c6`. This branch is ahead of it; see the pull request.
- No new dependencies or tools.

## 3. Standards applicability and evidence

Project standards profile updated: no new exception.

| Standard/control/rule | Applies? | Evidence produced | Exception/deviation |
| --- | --- | --- | --- |
| ISO/IEC 17025 §7.5, §7.11 (records, data control) | Yes | Readable copies that name the hash of the signed file; custody log view; key register with role and validity; `tests/test_report_html.py`, `test_record_html.py`, `test_key_register.py`, `test_key_card.py` | Register distribution and identity checks are organisational (OQ-9) |
| ISO/IEC 27037/27042 integrity | Yes | Package with readable copies listed in the signed manifest; offline copies only after verification | None |
| OWASP ASVS V5 (input), CWE-79, CWE-150, Trojan Source | Yes | Escaped HTML with a restrictive CSP; bidi overrides refused in register, card and note text (sidecar and Rust core); fuzz tests of six record formats | None |
| WCAG 2.2 AA | Yes | axe checks on the custody log table, store search and filter, key card form, batch import | Manual screen-reader pass open |
| `desktop_gui_tauri_standards.md` §3, §4 | Yes | New commands (`custody_log`, `export_report_html`, `export_key_card`, batch `import_evidence`) validate in Rust and are allow-listed in `list.rs` and the capability; the passphrase stays in the prompt window | None |

## 4. Forensic impact

- Output pixels changed: no.
- Recorded parameters: unchanged.
- New records:
  - `report.export` entries with `format: html`;
  - file formats `ridge.key-register/1` and `ridge.key-card/1`;
  - packages may hold `reports/<uuid>.html` and `processing-record.html`.
- Examiner-facing wording:
  - readable copies say "This page is not signed" and point to the verifiers;
  - notes in a readable copy are "not part of the signed report";
  - the comparison "does not rank the outputs";
  - key cards prove possession, "not identity".
- Data classes: synthetic data only; readable copies and packages hold no images.

## 5. Files changed

See the pull request. Main areas:

- `src/ridge/case/`:
  - new: `report_html.py`, `record_html.py`, `key_register.py`, `key_card.py`, `job_compare.py`, `cli_register.py`;
  - changed: `package.py`, `notes.py`, `reports.py`, `processing_record.py`, `custody_head.py`, the CLI modules;
- `src/ridge/sidecar/`;
- `gui/src-tauri/src/` (`commands/records.rs`, `export_key_card`, batch import, `validate::holder`);
- `gui/src/` (CustodyLog, store search and filter, key card form, evidence notes, batch import);
- tests and docs.

## 6. Data store, records and formats

- No store migration.
- New formats (architecture §8): key register, key card, readable copies (HTML, unsigned).
- Write paths:
  - readable copies and key cards: new files only (native dialog in the GUI);
  - `register-add`: a new register file, never replacing the old one;
  - batch import: one logged import per photo.

## 7. Configuration, keys and CI

- No new configuration keys and no CI changes.
- Key register and key cards are organisational artefacts: Ridge never stores them in the case store.

## 8. Security

- The readable HTML uses a strict CSP and escapes everything, so a hostile value in a report or log cannot run when the page is opened.
- Offline readable copies render only bytes that verified (no check-then-read gap).
- The key register turns "compare the key id by hand" into a checked lookup with role and validity. Signing times come from the signed files, so revocation is fully effective only together with countersigned custody heads (OQ-8).
- Open (unchanged): ADR-010 review; installer not code-signed.

## 9. Tests

- Added:
  - Python: `test_report_html.py` (3), `test_record_html.py` (3), `test_key_register.py` (16), `test_key_card.py` (5), `test_job_compare.py` (2), `test_fuzz_records.py` (7);
  - more cases in the package, notes and store-overview tests;
  - Rust: batch-import continuation, action-kind validation, holder validation, key-card prompt;
  - Vitest: custody log, evidence import, store search and filter, key card, last verified, photo notes.
- Commands: `python tools/gate.py all` on this branch; the result is recorded in the pull request.
- Dev preview checked in the built-in browser with synthetic data: custody log and last verified.
- Not run:
  - `tauri build` installers;
  - GUI on Linux and macOS (`gui.yml` on demand);
  - WebDriver E2E.

## 10. Release readiness

- Internal engineering build.
- Not ready for casework (M5).
- GUI release blockers unchanged: installer and signing, E2E, screen-reader pass, ADR-010 review, owner names.

## 11. Open risks and known issues

- The key register is not signed by Ridge. The laboratory distributes it, and reviewers confirm its SHA-256.
- Batch import stops on a locked case, so earlier photos stay imported (each logged). The GUI reports what was imported.

## 12. Recommended next work

1. Decide OQ-9 (key model, who keeps the register) and document the laboratory procedure that uses `register-add`.
2. Countersigned custody heads in the laboratory system (OQ-8), which make revocation dates fully effective.
3. Tauri WebDriver E2E on Windows with synthetic stores.

## 13. First thing the next agent/developer should read or do

Run `python tools/gate.py all`. Then try the reviewer tools on a synthetic package:

```bash
ridge-case check-package <folder> --register <lab-keys.json>
```
