# Handoff_9.md

Date/time (ISO 8601 with offset): 2026-10-17T10:05+02:00
Author/agent: Claude Code (claude-opus-5-5), autonomous development window
Project: Ridge
Branch: `m5-case-reports` (built on `m5-validation-metrics`) → PR after PRs #5, #6 and #7

## 1. Scope

Verified access to job reports (new **PRD FR-28**). Until now a signed report could only be checked as part of `ridge-case verify`. Examiners could not read a report or hand it to anyone else.

| Part | What |
| --- | --- |
| `ridge.case.reports` | `list_jobs` derives every job from the custody log: ok, failed (with its error) or open (started, never closed). `resolve_job` accepts a full UUID or a unique prefix of 8 or more characters, matched only against ids in the verified log, so caller input never builds a path (CWE-22). `load_report` checks three things. The report's hash must match the `report.sign` entry. Its signature must verify with the store's identity. It must name its own job and case. `export_report` writes the canonical bytes and a base64 detached signature (`PATH.sig`). It refuses to replace either file unless asked. `check_exported_report` verifies an exported pair offline: canonical form, the key id derived from the embedded public key, the signature, and optionally an expected key id. `render_report` gives a plain-text view with control characters replaced (CWE-150) |
| `ridge-case jobs` / `report` / `check-report` | List jobs; show (`--json` for the signed bytes) or export (`--to`) a verified report; verify an exported report without a passphrase or store |
| Sidecar | `case.jobs`, `report.get`, `report.export` (architecture §7.3) |
| `ridge.case.processing_record` (PRIV-3) | `ridge-case log --to PATH` logs `log.export`, signs the custody head, then writes all decrypted entries, the case id and the examiner public key as readable JSON (`ridge.processing-record/1`), so every exported entry is covered by a signature. `ridge-case check-log` recomputes sequence numbers and hash links and verifies every signed head. It requires the record to end with the signed `log.export`, whose case id must match the envelope (PR #8 review), and optionally checks the expected key id. A failed write is logged as a failed `log.export`. Sidecar: `log.export` |
| Custody | New actions `report.read`, `report.export` and `log.export`; `ridge-case jobs` only reads the log and adds no entry, like `list` |

## 2. Evidence

`tests/test_case_reports.py` covers:

- job listing for every outcome;
- prefixes, ambiguity, unsigned jobs, and traversal-shaped ids;
- tampered signature and sealed report files;
- a validly signed report that names another case;
- an unknown signing key;
- export, the no-overwrite rule (also when only the `.sig` exists), and overwrite;
- offline checks against edited, reformatted, wrongly keyed and malformed reports, non-JSON input and oversized files;
- rendering, including escape-sequence neutralisation.

`tests/test_processing_record.py` covers:

- signed, complete exports;
- the overwrite rule;
- a foreign identity;
- a logged failed write;
- edited, re-linked (forged), removed and appended entries;
- stripped signatures and an edited case id;
- malformed identity, entries and signatures;
- NaN, non-JSON and oversized files.

`test_failed_exports_leave_nothing_behind` covers the new rule that a report, signature or item export that fails part-way (second file or custody append) leaves no plaintext behind (`store.publish_logged`, PR #8 review).

The CLI and sidecar end-to-end tests also exercise the new commands. `reports.py` and `processing_record.py` have 100 % line and branch coverage.

## 3. Forensic impact

- Reports become usable records (ISO/IEC 17025 7.5, ISO/IEC 27037/27042). An exported report is exactly what was signed, so a reviewer can check it independently.
- **Limit:** the report carries its own public key. A valid signature shows only that the holder of that key signed it. The reviewer must compare the key id with the examiner's published identity (`ridge-case identity show`), which is what `--key-id` does. The CLI says so when `--key-id` is missing.
- The DPO gets a processing record they can verify themselves (LED Art. 25-style logging, PRIV-3). It contains the actors and file labels in plaintext.
- Reading and exporting reports is logged (FR-22). The exported report holds the case reference and file labels in plaintext, so the examiner chooses where it goes (FR-25).

## 4. Open items

- **CI is blocked:** GitHub Actions is not starting jobs because of an account billing or spending-limit problem (seen on 2026-10-17 at about 09:50+02:00). Every branch was verified with the local gate instead. PRs #5, #6 and #7 stay open until the CI matrix (3 OS × Python 3.12–3.14) is green.
- Who receives exported reports, and where the examiner identity is published for key-id comparison, is a laboratory QMS decision (OQ-8, out-of-band countersigning).

## 5. First thing to do

Restore GitHub Actions billing and re-run CI on PRs #5 → #6 → #7 → this branch, then merge them in that order. Next, read `src/ridge/case/reports.py`.
