# Handoff_52.md

Date/time (ISO 8601 with offset): 2026-10-24T23:10+02:00
Author/agent: Claude Code (claude-fable-5-1), end-user review follow-up (examiner's item): annotations as signed records
Project: Ridge
Branch: `afis-annotations-34` (stacked on `afis-research-mode-33`; local commit only, nothing pushed)
Base commit: `d534862` (tip of `afis-research-mode-33`, Handoff_51)
Latest commit: see `git log afis-annotations-34`

## 1. Scope

Requested change: from the end-user review, the examiner's need to chart: mark minutiae on the output and have the markings in the record. This branch is the record, the export and the listing; the marking tool in the viewer and the linked views follow on the next branch.

Completed work:

- **Annotation sets (PRD FR-55, ADR-016 proposed; `ridge.case.annotations`).** `add_annotation(case, signer, job_id, sha256, marks, note, replaces)` records an `examiner.annotation` custody entry for one output image (print, export or export-gray) of one job: the image's SHA-256, role and size (read from the stored PNG's header in one logged read), the numbered marks (whole pixels inside the image; kind ending, bifurcation or other; optional label of at most 40 printable characters without bidirectional controls; at most 500 marks), an optional note (2000 characters) and the `replaces` seq of an earlier set of the same image. The chain head is signed right after the entry (`chain.sign`), so each set is covered by a signature at once. `list_annotations` recovers the signature that followed each set; `current_annotations` leaves out replaced sets. Refusals: another job's image, an evidence image, a mark outside the image, a bad kind, an oversized or bidirectional label, an unknown field, an empty or oversized set, `replaces` pointing elsewhere.
- **Annotated image (`ridge.case.annotation_image`).** `export_annotated(case, seq, dest)` draws the set's marks on a copy of the stored image (outline per kind: circle, square, triangle; the mark's number beside it; kinds and labels stay in the record) and writes it as a plaintext PNG through `publish_logged`, with an `annotation.export` entry naming the set (`annotation_seq`), the source hash, the file name, the written file's hash and the mark count. Deterministic; refuses an existing file unless `overwrite`, a non-PNG name, and an image whose size no longer matches the set.
- **Entry points.** CLI `ridge-case annotate`, `annotations`, `export-annotated` (`ridge.case.cli_annotations`); sidecar `annotation.add`, `annotations.list`, `annotation.export`; Rust `add_annotation` (bounded marks, allow-listed kinds, one-line labels), `list_annotations`, `export_annotated` (native PNG save dialog), registered in the allow-list, `generate_handler!` and the main capability; GUI `AnnotationsPanel` under each job in **Jobs**: the sets with their mark counts by kind, replaced sets marked, the note, and "Save annotated image...".
- **Readable report.** `render_report_html` takes the job's sets and lists them after the notes, escaped, with the statement that marks are not a match, a count of agreement or an identification; `export_report_html` and the disclosure package pass them.
- Docs: PRD FR-55; architecture (annotations paragraph, sidecar method table, ADR-016 row); CHANGELOG; README; examiner guide ("Jobs and review" item 5).

Out of scope: the marking tool in the viewer and the linked views (next branch, FR-56); per-mark corrections (a set replaces a set); any interpretation of marks.

## 2. Current repository state

Git status summary: committed on `afis-annotations-34`.

Recent commits: `d534862` (Handoff_51) and the stack below.

## 3. Standards applicability and evidence

Project standards profile updated: not needed.

| Standard/control/rule | Applies? | Evidence produced | Exception/deviation |
| --- | --- | --- | --- |
| Custody and signatures (every mutation logged in the chain; signed records) | Yes | The set is one custody entry followed at once by `chain.sign`; the export is logged with both hashes; tests check the order and the hashes | None |
| Validation at every boundary (CLI, sidecar schema, Rust struct, module) | Yes | `check_marks` in the module; `-32602` for a non-list; Rust `deny_unknown_fields`, bounded `Vec`, kind allow-list, label and note cleaning | None |
| Forensic wording (no match, no count of agreement, no identification) | Yes | The report section, the GUI note and the docs say so; Ridge never aggregates marks | None |
| Safe output (no silent overwrite, atomic publish, logged) | Yes | `publish_logged`; `OutputExistsError` tested | None |
| Trojan-source resistance in free text | Yes | Labels and notes refuse control and bidirectional characters (module and Rust); escaped in HTML | None |

Standards checks or tools run: section 9.

Exceptions, deviations or evidence gaps: none.

Steps outside coding work: the owner accepts or amends ADR-016.

## 4. Forensic impact

Output pixels changed: no. The annotated image is a derived plaintext export, never a stored item, and never replaces an output.

Defaults or recorded parameters changed: none. New custody actions `examiner.annotation` (with `chain.sign` following) and `annotation.export`.

Revalidation decision required / recorded: not applicable (no method change).

Examiner-facing wording changed (checked against forbidden claims): "Examiner annotations", the panel's note, the report section text, the CLI lines; no identification or match claim.

Data classes touched: synthetic only.

## 5. Files changed

| File | Purpose of change |
| --- | --- |
| `src/ridge/case/annotations.py` (new), `src/ridge/case/annotation_image.py` (new) | The record, validation, listing; drawing and the logged export |
| `src/ridge/case/cli_annotations.py` (new), `src/ridge/case/cli.py` | `annotate`, `annotations`, `export-annotated` |
| `src/ridge/sidecar/case_methods.py`, `src/ridge/sidecar/handlers.py` | `annotation.add`, `annotations.list`, `annotation.export` |
| `src/ridge/case/report_html.py`, `src/ridge/case/package.py` | The report section; the package passes the sets |
| `gui/src-tauri/src/commands/annotations.rs` (new), `commands/mod.rs`, `commands/list.rs`, `src/lib.rs`, `capabilities/main.json` | Commands and registration |
| `gui/src/components/AnnotationsPanel.tsx` (new), `gui/src/screens/JobsSection.tsx`, `gui/src/ipc/types.ts`, `gui/src/ipc/commands.ts`, `gui/src/dev/preview.ts` | The panel, its placement, types, calls, preview mocks |
| `tests/test_annotations.py` (new), `gui/src/test/annotations.test.tsx` (new) | Tests (section 9) |
| `docs/prd.md`, `docs/architecture.md`, `CHANGELOG.md`, `README.md`, `docs/examiner_guide.md` | Requirements, design, ADR-016, changelog, usage, guide |
| `Instruction_documentation/Handoff/Handoff_52.md` (new) | This handoff |

## 6. Data store, records and formats

New custody entries: `examiner.annotation` {`job_id`, `sha256`, `image` {`role`, `width`, `height`}, `marks` [{`n`, `x`, `y`, `kind`, `label`}], `note`, `replaces`} followed by `chain.sign`; `annotation.export` {`annotation_seq`, `job_id`, `sha256`, `file`, `written_sha256`, `marks`}. No schema version bump: entries are additive and older readers list them as custody entries of an unknown kind.

A defect found and fixed during the work: the export entry first carried a field named `seq`, which overwrote the entry's own sequence number in `CustodyLog.append`; it is now `annotation_seq`. The test asserts the entry's own `seq` is untouched.

## 7. Configuration, keys and CI

None.

## 8. Security

Two new mutating sidecar methods (one logged read plus two appends; one logged plaintext write to a dialog-chosen path) and one read method, all behind strict schemas and the unlocked-case state; three new allow-listed commands. Free text is cleaned in the module and in Rust and escaped in HTML. No new trust boundary.

## 9. Tests

Tests added or updated:

- `tests/test_annotations.py` (new): a set is logged, signed at once and listed with its signature; replacing keeps the earlier set; the refusals of section 1; the annotated image is written, logged with its hash, deterministic, refused for an existing file and a non-PNG name; the readable report lists the sets with escaped labels and notes; CLI annotate/annotations/export-annotated and a refused mark; sidecar add (with `replaces`), list, `-32602` for a non-list, `-32000` for a bad kind, export, and a relative path refused.
- `gui/src/test/annotations.test.tsx` (new): the panel lists a job's sets with counts by kind, marks the replaced set, saves an annotated image with the suggested name and notifies (axe clean); the empty state; a cancelled dialog is silent; the set line wording.

Commands run:

```bash
.venv/Scripts/python.exe -m ruff check src tests tools && .venv/Scripts/python.exe -m ruff format --check src tests tools   # clean
.venv/Scripts/python.exe -m mypy                                                        # Success: no issues found in 205 source files
.venv/Scripts/python.exe -m pytest tests/test_annotations.py tests/test_report_html.py tests/test_notes.py tests/test_sidecar.py tests/test_package.py tests/test_case_cli.py tests/test_record_html.py -q   # 78 passed in 107.27s (0:01:47)
cd gui && npm run lint && npm run typecheck && npx prettier --check . && npm test -- --run   # 36 files, 130 tests passed
cd gui/src-tauri && cargo fmt --check && cargo clippy --locked --all-targets -- -D warnings && cargo test --locked   # pass, 36 tests
.venv/Scripts/python.exe tools/gate.py docs   # pass
```

Determinism and golden results: unaffected (no pipeline change); the annotated PNG is deterministic (tested).

Tests not run and why: the full `gate.py all` (stack top, at the end of this run); Tauri WebDriver E2E (profile exception).

Required tests still missing: none for the record; the marking tool's tests come with it.

## 10. Release readiness

Release type: internal build. Ready: as part of the stack. Blockers: none. Rollback: revert the commit (custody entries already written stay in the log, as every entry does).

## 11. Open risks and known issues

- The annotated image uses Pillow's default font for the mark numbers; its exact pixels depend on the Pillow version, so the written hash is deterministic per installation, not across Pillow upgrades. The record, not the picture, is authoritative.
- A set replaces a set: there is no per-mark correction. Examiners who want to adjust one mark record a new set naming the old one.

## 12. Recommended next work

The marking tool in the review panel's output viewer and the linked zoom and pan between the original and the output (FR-56), then the full gate on the stack top and the closing handoff.

## 13. First thing the next agent/developer should read or do

`src/ridge/case/annotations.py` and ADR-016's row in `docs/architecture.md`.
