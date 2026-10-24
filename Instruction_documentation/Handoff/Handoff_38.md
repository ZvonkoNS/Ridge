# Handoff_38.md

Date/time (ISO 8601 with offset): 2026-10-24T11:45+02:00
Author/agent: Claude Code (claude-fable-5-1), autonomous window of 2026-10-24 (Handoff_35 section 1), item 3 of the AFIS-readiness assessment
Project: Ridge
Branch: `afis-export-formats-22` (stacked on `afis-scale-reference-21`; local commit only, nothing pushed)
Base commit: `9638b0a` (tip of `afis-scale-reference-21`, including the assertion fix found by that branch's test gate)
Latest commit: see `git log afis-export-formats-22`

## 1. Scope

Requested change: item 3 of the assessment: exchange file formats for exports, and a note when an export is enlarged beyond the photo's resolution.

Completed work:

- **TIFF and BMP on export (PRD FR-32).** `ridge-case export CASE SHA --to file.tif` (or `.tiff`, `.bmp`), the GUI save dialog's TIFF and BMP types, and `export-all --format tiff|bmp` (CLI, GUI "File format for image exports", sidecar `case.export_all` `format`) convert one of Ridge's own image outputs on the way out: the stored PNG is decoded with bounds (PNG only, 8-bit grayscale only, at most 50 MP) and re-encoded from its pixels as uncompressed baseline TIFF (resolution in ppi, no other tags) or 8-bit BMP (pixels per metre), pixel-identical. New modules `src/ridge/export/formats.py` (pure) and `src/ridge/case/export_file.py` (the logged write). The custody entry `artefact.export` carries `format` and `written_sha256` beside the stored `sha256`; `EXPORTS.csv` gains `format` and `written_sha256`; `case.export` returns both. Images without a recorded resolution (the print, debug images) are refused for conversion with a message, because an exchange file would be read at a software default; other roles and other suffixes copy the stored bytes as before.
- **Resolution note.** `export.resolution_note` is recorded when the comparison export was enlarged more than 1.05 times to reach its resolution (for example 1000 ppi from a modest photo), shown in the CLI, the readable reports and the GUI summary.
- Docs: PRD FR-32; architecture §7.3 rows and §8.3 paragraph; CHANGELOG; README; examiner guide (Exports).

Out of scope: WSQ, JPEG 2000 and ANSI/NIST-ITL containers (OQ-4); items 4 to 14.

## 2. Current repository state

Git status summary: committed on `afis-export-formats-22`.

Recent commits: `9638b0a` (assertion fix), `640ff04` (Handoff_37), `fb5261d` (Handoff_36), `d799929` (Handoff_35) below this one.

## 3. Standards applicability and evidence

Project standards profile updated: not needed (no new dependency or exception; TIFF 6.0 baseline and BMP are output encodings of the already-vetted Pillow).

| Standard/control/rule | Applies? | Evidence produced | Exception/deviation |
| --- | --- | --- | --- |
| TIFF 6.0 baseline (uncompressed grayscale, resolution tags) | Yes (new output encoding) | `tests/test_export_formats.py`: Compression 1, ResolutionUnit inch, 500 ppi, only baseline tags, pixels identical, deterministic bytes | None |
| FR-12 metadata minimisation | Yes | Conversions are encoded from pixels and the recorded resolution only; the tag set is checked in tests | None |
| FR-22/FR-25 single logged export path | Yes | Conversions go through `publish_logged`; the entry names stored and written hashes | None |
| Coding standards: bounded decoding (CWE-400) | Yes | Pixel count checked before the pixels are read; PNG signature and mode checked; corrupt data is a typed `DecodeError` | None |
| Execution rules: export formats are high risk | Yes | Threat note in section 8; tests for success, refusal, part-way failure and index | None |

Standards checks or tools run: section 9.

Exceptions, deviations or evidence gaps: none.

Steps outside coding work: the AFIS team should say which of PNG, TIFF or BMP their import tools take (OQ-4); the conversions are lossless, so the choice does not affect validation.

## 4. Forensic impact

Output pixels changed: no. Conversions are pixel-identical re-encodings of stored exports, written outside the store; stored artefacts are unchanged.

Defaults or recorded parameters changed: no parameter changed. Reports gain `export.resolution_note` (conditional); custody entries gain `format`/`written_sha256` when a conversion was written; `EXPORTS.csv` gains two columns.

Revalidation decision required / recorded: not required (no method change; the exchange file holds the same pixels at the same declared resolution).

Examiner-facing wording changed (checked against forbidden claims): new CLI/GUI wording about file formats and the resolution note; no claim of identification or validation.

Data classes touched: synthetic only.

## 5. Files changed

| File | Purpose of change |
| --- | --- |
| `src/ridge/export/formats.py` (new) | Formats, suffix mapping, bounded PNG decode, TIFF/BMP encoders, `convert_png` |
| `src/ridge/case/export_file.py` (new) | `export_item` (logged, with format and written hash), `converted_name` |
| `src/ridge/case/export_all.py` | `fmt` argument, `Written` records, index columns |
| `src/ridge/case/export_step.py` | `resolution_note` |
| `src/ridge/case/report_lines.py`, `src/ridge/case/reports.py`, `src/ridge/case/report_html.py` | "Resolution" line and row |
| `src/ridge/case/cli.py`, `src/ridge/case/cli_extract.py` | `export` conversion, `export-all --format`, the resolution note line |
| `src/ridge/sidecar/case_methods.py`, `src/ridge/sidecar/handlers.py` | `case.export` result fields, `case.export_all` `format` |
| `gui/src-tauri/src/dialogs.rs`, `gui/src-tauri/src/commands/case.rs` | Multi-type save dialog, `export_all` format, image export types |
| `gui/src/ipc/types.ts`, `gui/src/ipc/commands.ts`, `gui/src/screens/Inventory.tsx`, `gui/src/screens/ReviewPanel.tsx`, `gui/src/screens/JobSummary.tsx` | Format choice for bulk export, export result message, resolution note |
| `tests/test_export_formats.py` (new), `tests/test_export_file.py` (new), `tests/test_export_all.py`, `tests/test_case_export.py`, `gui/src/test/overlay.test.tsx` | Tests (section 9) |
| `docs/prd.md`, `docs/architecture.md`, `docs/examiner_guide.md`, `CHANGELOG.md`, `README.md` | Requirements, design, guide, changelog, usage |
| `Instruction_documentation/Handoff/Handoff_38.md` (new) | This handoff |

## 6. Data store, records and formats

Case-store, custody-log or report format changes (M1+): `artefact.export` entries may carry `format` and `written_sha256`; reports may carry `export.resolution_note`; `EXPORTS.csv` has two more columns (readers by column name are unaffected).

Migrations and recovery notes: none.

Run-record or export format changes: new export encodings TIFF and BMP (outside the store only).

Write paths added or changed: `export_file.export_item` writes through `publish_logged` to an examiner-chosen path, like `OpenCase.export`; no new location class. `direct_mutation_authorization_audit.md` lists the export path already; no change in where plaintext may land.

## 7. Configuration, keys and CI

None.

## 8. Security

Decoder, limit or allow-list changes: a new decode of Ridge's own PNG for conversion, limited to PNG, mode L and 50 MP, with corrupt data mapped to `DecodeError`; the GUI's bulk-export format allow-list in Rust and the sidecar.

Trust-boundary changes: `case.export_all` gains an optional string checked on both sides; the save dialog offers three file types and the sidecar decides by suffix.

Threat-model notes: a converted file leaves the store with a different hash than the stored item; the custody entry records both so a received file can still be matched. No metadata is copied into the exchange files.

Open security risks: none.

## 9. Tests

Tests added or updated:

- `tests/test_export_formats.py` (new): suffix and format checks; TIFF lossless, uncompressed, baseline tags only, resolution, deterministic; BMP lossless with pixels per metre; PNG as stored; refusals (not PNG, colour, no resolution, too large, truncated, unknown format); encoder argument validation.
- `tests/test_export_file.py` (new): conversion logged with both hashes; PNG and non-image items as stored; the print refused with no file written; converted names; bulk export with a format and the index columns; CLI `export` and `export-all --format`; sidecar `case.export` and `case.export_all` with a format, unknown format refused.
- `tests/test_export_all.py`: adapted to the `Written` records and the fake export's signature; `tests/test_case_export.py`: the resolution note at 1000 ppi and its absence at 500 ppi, the CLI line.
- `gui/src/test/overlay.test.tsx`: bulk export sends the format.
- Rust unit tests unchanged (compile and pass with the new types).

Commands run:

```bash
.venv/Scripts/python.exe -m ruff check src tests tools && .venv/Scripts/python.exe -m ruff format --check src tests tools   # clean
.venv/Scripts/python.exe -m mypy                                                        # Success: no issues found in 177 source files
.venv/Scripts/python.exe -m pytest tests/test_export_formats.py tests/test_export_file.py tests/test_export_all.py tests/test_case_export.py tests/test_sidecar.py tests/test_case_reports.py tests/test_report_html.py tests/test_case_cli.py -q
# 103 passed in 272 s
cd gui && npm run lint && npm run typecheck && npx prettier --check . && npm test -- --run   # 30 files, 114 tests passed
cd gui/src-tauri && cargo fmt --check && cargo clippy --locked --all-targets -- -D warnings && cargo test --locked   # pass
.venv/Scripts/python.exe tools/gate.py docs   # pass
.venv/Scripts/python.exe tools/gate.py test   # started on this commit in a separate worktree; result in the next handoff
```

Determinism and golden results: no pipeline change; TIFF and BMP bytes are deterministic for the same Pillow version (tested).

Tests not run and why: the full `gate.py all` (runs on the stack top); the GUI gate's `npm ci`/build steps (toolchain unchanged since Handoff_35); Tauri WebDriver E2E (profile exception); an AFIS import of the TIFF/BMP files (needs the AFIS team).

Required tests still missing: none for this item.

## 10. Release readiness

Release type: internal build. Ready: as part of the stack. Blockers: none from this branch. Rollback: revert the commit; files already converted stay valid exports with their logged hashes.

## 11. Open risks and known issues

- Whether a given AFIS import tool accepts these TIFF or BMP files is for the AFIS team to confirm (OQ-4); the encodings are the plainest baseline forms.

## 12. Recommended next work

Item 4 of the assessment: submission record fields and the AFIS submission cover sheet.

## 13. First thing the next agent/developer should read or do

Handoff_35 section 12 for the order of the stack; this branch's `git show --stat`.
