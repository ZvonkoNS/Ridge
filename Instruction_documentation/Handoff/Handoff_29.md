# Handoff_29.md

Date/time (ISO 8601 with offset): 2026-10-21T16:26+02:00
Author/agent: Claude Code (claude-opus-5-5), a side session started by the FR-36 session
Project: Ridge
Branch: `claude/nostalgic-babbage-40e1ce` (worktree), cut from `origin/m5-photo-metadata-14`
Base commit: `4bf3199` (tip of `m5-photo-metadata-14`: the FR-36 feature commit `75ce609`, the Handoff_28 update `3016875` and the PR #28 review fixes; open as PR #28, stacked on PR #27). The work was started on `3016875` and moved onto `4bf3199` on 2026-10-21 by rebasing a temporary local commit, which was then undone; the docs merged without conflicts.
Latest commit: see PR #28. On 2026-10-22 the owner asked to "merge to main and commit"; this change is committed on top of `m5-photo-metadata-14` (PR #28).

## 1. Scope

Requested change: a CLI command `ridge-case metadata CASE SHA [--json]` that prints the photo metadata (FR-36) of one stored evidence or reference image without running a job, for examiners and reviewers who work from the CLI. Handoff_28 listed it as out of scope and as recommended next work (section 12, item 3).

Completed work:

- `src/ridge/case/cli_metadata.py` (new, 50 lines), registered in `src/ridge/case/cli.py` like the other `cli_*` modules. The handler:
  - unlocks the case with the examiner passphrase (read interactively, as every case command does);
  - resolves the item with `OpenCase.item` (full SHA-256 or a unique prefix of at least 8 characters);
  - refuses roles other than evidence and reference **before** any read, with the same message as the sidecar's `metadata.get`, so a refusal logs nothing;
  - calls `ridge.metadata.read_metadata(case.read(sha))`. The read is logged as `evidence.read` or `reference.read`, as `metadata.get` does.
- Text output: a header line (role, full SHA-256, the stored file name), then `ridge.case.metadata_render.metadata_text`, the report's "Photo metadata" section with every entry and the map link. Since `4bf3199` that section includes the `DISCLOSURE` line under the link (Ridge never opens it; opening it sends the position to Google), and the CLI test checks it. Every line goes through `reports.printable`. The file name is also passed through `ridge.metadata.values.text`, so a bidirectional mark in it shows as `<U+XXXX>`; `printable` alone replaces only control characters.
- `--json`: the `ridge.photo-metadata/1` record as ASCII-only JSON (`ensure_ascii=True`). It is exactly the record a job report on the photo holds in `input.metadata` (tested), so a reviewer can compare the two. ASCII-only output cannot carry a terminal escape even if a value slipped past the reader's `text` filter (defence in depth, CWE-150); a JSON parser restores the non-ASCII letters.
- Documentation: PRD FR-36 note, acceptance tests and traceability; architecture §6 (module and import rule), §7.3 (`metadata.get` row names the CLI equivalent), §8.3 (paragraph on the command); README command list; examiner guide ("Photo metadata", one paragraph); CHANGELOG.

Out of scope:

- The verification guide was not changed. It covers offline checks of exported files without a case store; this command needs the store and the passphrase.
- No change to the sidecar, the GUI, the metadata readers or report rendering.

## 2. Current repository state

Git status summary: uncommitted in the worktree. Changed: `CHANGELOG.md`, `README.md`, `docs/architecture.md`, `docs/examiner_guide.md`, `docs/prd.md`, `src/ridge/case/cli.py`. New: `src/ridge/case/cli_metadata.py`, `tests/test_metadata_cli.py`, this handoff.

Recent commits: `4bf3199` Fix the PR #28 review findings (bounded XMP coordinates, real GPS dates, link warning); `3016875` Handoff_28: record the commit and the stacked pull request; `75ce609` FR-36 feature commit; `a784d37` print-area work (Handoff_27).

## 3. Standards applicability and evidence

Project standards profile updated: not needed. No new standard, dependency, data class, data store or exception. The existing FR-36 rows (metadata in reports, DPO review pending under OQ-16) cover what this command shows.

| Standard/control/rule | Applies? | Evidence produced | Exception/deviation |
| --- | --- | --- | --- |
| FR-22 / LED Art. 25: every read logged | Yes | `test_text_lists_every_entry_with_the_map_link_and_logs_one_read` (one `evidence.read` with the SHA-256), `test_references_are_shown_and_json_output_is_ascii` (`reference.read` per call) | None |
| Fail closed; refusals log nothing (SEC-9) | Yes | `test_outputs_and_unknown_items_are_refused_before_any_read` (print and export items, unknown SHA-256, a 7-character prefix: exit 1, no stdout, custody log unchanged) | None |
| Access control: passphrase and single-writer lock | Yes | `test_a_locked_case_or_a_wrong_passphrase_shows_and_logs_nothing` (case open elsewhere, wrong passphrase: exit 1, no stdout, log unchanged) | None |
| CWE-150 terminal output; Trojan Source (CVE-2021-42574) | Yes | `test_hidden_and_control_characters_never_reach_the_terminal` (ESC in EXIF, U+202E in XMP and in the file name; text and JSON); JSON ASCII-only | None |
| Evidence immutability; read from the verified copy (forensic standard §3, §9) | Yes | The command reads only `OpenCase.read` (AES-GCM tag and SHA-256 checked); the source file is never opened | None |
| Data minimisation (LED Art. 4(1)(c)) | Yes | Prints what the GUI panel and the reports already show; nothing leaves the store as a file, and the read is logged | Covered by the existing FR-36 profile row (OQ-16) |
| Wording: no identification, verification or authenticity claims | Yes | Output repeats the record's notice that Ridge does not verify metadata | None |
| Entrypoint and file size (`coding_standards.md`) | Yes | Handler 15 lines; `cli_metadata.py` 50 lines; `cli.py` 259 lines | None |

Standards checks or tools run: see section 9.

Exceptions, deviations or evidence gaps: none new.

Steps outside coding work: none new. DPO review of metadata in reports (OQ-16) is still open and applies to this output as well.

## 4. Forensic impact

Output pixels changed: no. No pipeline, decoder, report or custody code changed; `tests/golden/` untouched.

Defaults or recorded parameters changed: no.

Revalidation decision required / recorded: none.

Examiner-facing wording changed: one new command, its help text and the docs above. Checked against the forbidden claims: no identification, match, validation or authenticity wording; the notice says metadata is not verified.

Data classes touched and how class E data stayed out of repository and agent session: synthetic images only, made in memory by `tests/metadata_samples.py` (GPS-tagged synthetic finger, IPTC JPEG, hand-built hostile EXIF and XMP) and written to pytest temporary folders. No real photo was opened.

## 5. Files changed

| File | Purpose of change |
| --- | --- |
| `src/ridge/case/cli_metadata.py` (new) | `ridge-case metadata` handler and parser |
| `src/ridge/case/cli.py` | Register the command; docstring names the module |
| `tests/test_metadata_cli.py` (new) | Six tests (section 9) |
| `docs/prd.md` | FR-36 note, acceptance tests, traceability |
| `docs/architecture.md` | §6 module and import rule, §7.3 `metadata.get` row, §8.3 paragraph |
| `README.md` | Command list |
| `docs/examiner_guide.md` | "Photo metadata": the CLI equivalent |
| `CHANGELOG.md` | Unreleased entry |
| `Instruction_documentation/Handoff/Handoff_29.md` (new) | This handoff |

## 6. Data store, records and formats

Case-store, custody-log or report format changes: none. The command appends the existing `evidence.read` / `reference.read` entries through `OpenCase.read`.

Migrations and recovery notes: none.

Run-record or export format changes: none. The JSON output is not a file format Ridge writes; it is the existing `ridge.photo-metadata/1` record printed to stdout.

Write paths added or changed: none. The custody append on a read is the existing `OpenCase.read` path; nothing is written outside the store.

## 7. Configuration, keys and CI

New or changed configuration keys or `RIDGE_*` variables: none. Key-custody or signing changes: none (the command does not unlock the identity). CI changes: none.

## 8. Security

Decoder, limit or allow-list changes: none; `read_metadata` keeps its allow-list and budgets.

Trust-boundary changes: none. The CLI reads the same verified bytes as `metadata.get`.

Threat-model notes: metadata values are attacker-controlled. Text lines pass `printable`, and the reader has already made values display-safe. The stored file name, which `printable` alone would pass with bidirectional marks, goes through `text`. JSON is ASCII-only.

Open security risks: `ridge-case list` shows stored labels and source notes through `printable` only, so a bidirectional mark in a file name would reach the terminal there (labels and source notes refuse only C0 controls and DEL, `case_model.clean_text`). Not changed here: it is outside this task (see section 11).

## 9. Tests

Tests added (`tests/test_metadata_cli.py`, 6 tests):

- text: header, notice, location, map link with the disclosure line under it, groups and entries, unique prefix, one logged `evidence.read`;
- JSON: the record equals `read_metadata` of the source bytes and the `input.metadata` of a signed job report on the same photo;
- a reference image by an 8-character prefix: ASCII-only JSON (non-ASCII IPTC text escaped and restored), text header with role `reference`, one `reference.read` per call;
- hidden and control characters (ESC in EXIF, U+202E in XMP and in the file name) never reach stdout, in text or JSON;
- print and export outputs, an unknown SHA-256 and a 7-character prefix are refused with exit 1 and nothing logged;
- a case open elsewhere and a wrong passphrase: exit 1, nothing printed, nothing logged.

Commands run (Windows 11 x86-64, Python 3.13.5; `PYTHONPATH` set to this worktree's `src`, because the shared virtualenv's editable install points at the main checkout):

```bash
python -m pytest tests/test_metadata_cli.py tests/test_metadata_reports.py -q   # 15 passed (after the rebase)
python -m ruff check / ruff format --check / mypy on the new and changed Python files   # clean (one import order fixed)
python tools/gate.py all                                 # FAILED at deps (below)
python tools/gate.py docs secrets licenses sbom gui      # the gates after deps; FAILED at gui (npm audit)
```

Both gate commands were run twice, with the same outcome: first on `3016875` plus this change, then on the final tree, `4bf3199` plus this change. The tables give the final run; the first run differed only in the test count (863 passed, coverage 96.65 %, 225 files formatted).

`python tools/gate.py all` result, gate by gate:

| Gate | Result |
| --- | --- |
| docs, lint, format, typecheck | passed (ruff clean, 226 files formatted, mypy: no issues in 166 source files) |
| test | passed: 867 passed, 3 skipped (POSIX permission bits on Windows), branch coverage 96.75 %, including the stored-golden comparison; `cli_metadata.py` fully covered |
| sast | passed (bandit; its "Test in comment" warnings are noise) |
| deps | **FAILED**: `Found 8 known vulnerabilities in 1 package`, `pillow 12.3.0`, fix version 13.0.0: CVE-2026-112895, CVE-2026-112400, CVE-2026-112397, CVE-2026-112896, CVE-2026-112897, CVE-2026-112395, CVE-2026-112404, CVE-2026-112899 |

`all` stops at the first failure, so the remaining gates were run on their own (`docs` again with this handoff in place):

| Gate | Result |
| --- | --- |
| docs | passed (handoffs consecutive up to Handoff_29) |
| secrets | passed (gitleaks: no leaks found) |
| licenses | passed (every runtime licence allowed, including defusedxml PSF-2.0) |
| sbom | passed (`build/sbom.cdx.json`) |
| gui | **FAILED** at `npm audit --audit-level=moderate`: `vite 8.3.0 - 8.3.2`, severity high, through `launch-editor` (GHSA-698v-4r3x-3vcv, GHSA-r825-w8mm-5pxw, GHSA-587h-7wmj-h5pm); fix `vite@8.3.5`, outside the stated range. Before it: `npm ci`, lint, typecheck, Prettier, Vitest (107 passed, 28 files) and the build passed |

**Neither failure is caused by this work.** Both are new advisories against unchanged lock files. This change touches no dependency, `requirements*.lock`, `pyproject.toml` or anything under `gui/`. Handoff_28's first run (pip-audit: no known vulnerabilities; npm audit: 0) passed both gates on the same locks, and its review-fix update records the same two failures on `4bf3199` itself. The same failures therefore apply to the base branch `m5-photo-metadata-14` (PR #28), PR #27 and `main`; the owner decides a separate dependency pull request. Neither upgrade was made here: Pillow is the image decoder (a pixel-affecting dependency: goldens, determinism and a revalidation decision, forensic standard §13), and Vite is a GUI build dependency outside this task.

Determinism and golden results: part of the `test` gate above (live v0 comparison and stored goldens); no pixel-affecting code changed.

Tests not run and why:

- The rest of the `gui` gate after `npm audit`: the npm licence check, the npm SBOM, `cargo fmt --check`, `cargo clippy`, `cargo test` (including the live Rust-to-sidecar test), `cargo audit`, `cargo deny` and the Cargo SBOM. The gate stops at the failed `npm audit`. This change has no GUI or Rust code, and the sidecar methods the Rust tests call are unchanged. Risk: none from this change. Whether any new Rust advisory exists is not known.
- The installed GUI application: unaffected (no GUI or sidecar change).

Required tests still missing: none known.

## 10. Release readiness

Release type: internal build.

Ready: `python tools/gate.py all` does not pass: the `deps` and `gui` gates fail on new Pillow and Vite advisories that affect the base branch and `main` equally (section 9). The owner decided on 2026-10-22 ("merge to main and commit") to commit this change on `m5-photo-metadata-14` and merge the stack (PR #27, PR #28) into `main` with these two failures open. The decision is recorded as an exception in `Project_Standards_Profile.md` section 8, and the dependency update follows as its own task.

Blockers: the Pillow 12.3.0 advisories (fix 13.0.0, a pixel-affecting upgrade) and the Vite 8.3.2 advisory (fix 8.3.5), both outside this change. FR-36's own open items (OQ-16, the PSF-2.0 licence confirmation) apply too.

Rollback or mitigation: remove `cli_metadata.py` and its registration; nothing is stored, migrated or signed by it.

## 11. Open risks and known issues

- New advisories fail the gate for every branch: 8 against `pillow 12.3.0` (pip-audit, fix 13.0.0) and one high-severity against `vite 8.3.2` through `launch-editor` (npm audit, fix 8.3.5). Pillow decodes every photo. Its upgrade is a method-relevant dependency change (`forensic_evidence_and_biometric_data_standards.md` §13, revalidation unless the Forensic Quality Manager documents why results cannot change) and needs golden, determinism and hostile-input runs on every platform. The Vite advisory concerns `launch-editor`, which the Vite dev server uses; it is not in the production bundle, but the gate counts it.
- `ridge-case list` prints stored labels (the source file names) and source notes through `printable`, which replaces control characters but not bidirectional marks or zero-width characters. At import, labels and source notes refuse only C0 controls and DEL (`case_model.clean_text`; examiner notes already refuse bidirectional overrides and isolates), so a crafted file name could display reordered text in `list`. Low impact (the SHA-256 printed next to it identifies the item) but a CWE-150 / Trojan Source gap; a shared terminal filter, for example `printable` extended to the ranges in `ridge.metadata.values`, would close it.
- `docs/architecture.md` §10 item 7 ends with a stray fragment line (`idge-sidecar.exe\` (what \`sidecar::locate\` expects).`), present on the base branch. Not touched here.
- The sidecar's `metadata.get` and this command repeat the same three-line role check and message. A shared helper in `ridge.case` would remove the duplication; it was not added, to keep the sidecar (part of the open PR #28) unchanged.

## 12. Recommended next work

1. Product owner: decide how to handle the new advisories, as their own task. This means upgrading Pillow to 13.0.0 with golden, determinism and cross-architecture runs and a revalidation decision, and Vite to 8.3.5. Or record a short, reviewed exception in the profile. Until then `deps` and `gui` fail on every branch.
2. Product owner: decide whether to commit this change on `m5-photo-metadata-14` (PR #28) or open it as a stacked pull request.
3. Close the bidirectional-mark gap in `ridge-case list`'s terminal output (section 11, first item), with a test.
4. Remove the stray fragment line in `docs/architecture.md` §10.

## 13. First thing the next agent/developer should read or do

Read this handoff and Handoff_28, then `src/ridge/case/cli_metadata.py` and `tests/test_metadata_cli.py`.
