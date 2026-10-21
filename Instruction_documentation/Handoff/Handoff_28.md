# Handoff_28.md

Date/time (ISO 8601 with offset): 2026-10-20T01:25+02:00
Author/agent: Claude Code (claude-opus-5-5)
Project: Ridge
Branch: `m5-photo-metadata-14`, stacked on `m5-print-area-13` (PR #27)
Base commit: `a784d37` (tip of `m5-print-area-13`)
Latest commit: see the pull request (feature commit `75ce609`, committed on 2026-10-21 at the owner's request)

## 1. Scope

Requested change: "I want all the available and possible meta data to be extracted from the images I upload. The meta data should be shown next to the image. If there is any geo location data it should be show and next to it should be a link to google maps at that exact location. The meta data should also be appended to the final report and data." (product owner, 2026-10-20)

Decisions taken with the owner before design (AskUserQuestion, 2026-10-20):

- Map link: **copy only**. Ridge shows the link with a Copy button and never opens it, so no opener, shell or network capability is added (ADR-001 and the WebView lock-down unchanged). The readable HTML report has it as an ordinary link.
- Depth: **built-in readers** (Pillow plus defusedxml). Optional ExifTool, which would decode MakerNotes, was offered and declined.
- Layout: **a panel under the photos** (not a side column).
- Images: **evidence and references**. Job reports cover evidence (jobs run on evidence only).

Completed work:

- `src/ridge/metadata/` (new, pure: bytes in, a bounded dict out, schema `ridge.photo-metadata/1`). It contains:
  - file facts;
  - every EXIF group (IFD0, Exif, GPS, interoperability, thumbnail IFD; tags in file order with their numbers, codes in words);
  - XMP via defusedxml, with lists, structures and the `xmpMM:History` edit history;
  - IPTC-IIM (records 1 and 2, UTF-8 aware);
  - the ICC header and description (hand-parsed with bounds checks);
  - PNG text, JPEG APPn/COM segments and the MPF index, and HEIF items;
  - a summary of camera, lens, software, camera-clock times, serial numbers and exposure, each line naming its tags;
  - the location: EXIF GPS, or XMP when EXIF has none, as exact rationals rounded half-even to 7 places, with altitude, GPS time, datum and horizontal error, plus a Google Maps URLs API link.
- Warnings explain what was not used: a position without its N/S or E/W reference or out of range, a 0,0 position, a non-WGS 84 datum, EXIF and XMP positions that differ, and blocks that could not be read. The embedded EXIF thumbnail and MakerNotes are recorded by size and SHA-256 only.
- Every value is made display-safe: control, bidirectional and zero-width characters are written as `<U+XXXX>`, and line breaks become spaces. The record is bounded at 2000 entries, 2000 bytes per value and 200 kB of text, with `truncated` set and a warning when anything is left out.
- Signed job reports record it as `input.metadata` (`src/ridge/case/jobs.py`), read from the same verified bytes as the pixels. Same report schema id; older reports have no `input.metadata`.
- Text and HTML reports append a "Photo metadata" section with every entry (`src/ridge/case/metadata_render.py`). The HTML rebuilds the map link from the two numbers and escapes every value. Disclosure packages get it through their HTML copies.
- Sidecar `metadata.get` (evidence or reference; outputs and minutiae refused; a logged read). Tauri command `photo_metadata` in a new `commands/metadata.rs`, with its capability.
- GUI `components/PhotoMetadata.tsx`, shown under the original and output in the review and under the images in References. It has:
  - the location with Copy buttons for the coordinates and the link, and a note that opening the link sends the position to Google;
  - the summary;
  - expandable group tables with a search;
  - embedded images and the notes on reading.

  The Jobs section shows the metadata recorded in the signed report, or says an older report has none. The dev preview has synthetic metadata.
- Dependency: `defusedxml` 0.7.1 moved from the dev lock to `requirements.lock` (same hashes; `uv pip compile` changed only that entry). The `licenses` gate allow-list gains PSF-2.0.
- Documents: PRD 0.13 (FR-36; notes on FR-12, FR-50 and FR-52; data inventory; R-13; OQ-16; traceability), architecture (modules, `metadata.get`, command count, §8.3 schema and paragraph, §9.1 control, §9.2 threats, §9.4 dependencies, ADR-013), examiner guide ("Photo metadata"), CHANGELOG, the standards profile, the forensic evidence standard (§2, §9, §14, §15) and the standards matrix (ASVS V1, V5).

Out of scope:

- Decoding vendor MakerNotes (declined), and an ExifTool adapter.
- A CLI command that shows an item's metadata without a job (`ridge-case report` already prints it for every job).
- New installers: the 0.2.0 installers do not contain this change.

## 2. Current repository state

- Committed on `m5-photo-metadata-14` (`75ce609`) and opened as a pull request stacked on PR #27 (base `m5-print-area-13`). New files: `src/ridge/metadata/` (10 modules), `src/ridge/case/metadata_render.py`, `gui/src-tauri/src/commands/metadata.rs`, `gui/src/components/PhotoMetadata.tsx`, `gui/src/lib/usePhotoMetadata.ts`, `gui/src/dev/previewMetadata.ts`, four test files and this handoff.
- PR #27 (`m5-print-area-13`) is below this branch; this work should become a stacked PR after it.

## 3. Standards applicability and evidence

Project standards profile updated: yes. It gains a technology row, the hostile-input evidence, and two section 8 rows: metadata in reports (DPO review pending, OQ-16), and the PSF-2.0 allow-list entry (owner confirmation pending).

| Standard/control/rule | Applies? | Evidence produced | Exception/deviation |
| --- | --- | --- | --- |
| Forensic: originals read-only, output pixels unchanged, goldens unchanged | Yes | Metadata read from the verified stored copy; pipeline untouched; `tests/golden/` untouched; golden comparison in the gate | None |
| FR-12: outputs carry no source metadata | Yes | `test_output_images_carry_none_of_the_metadata` (GPS-tagged input; no EXIF, no marker strings in print or export) | None |
| Reports hold no image data | Yes | Thumbnail by size and SHA-256 only; `test_the_exif_thumbnail_is_recorded_by_hash_and_size_never_its_pixels` | None |
| XML security (CWE-611, CWE-776; OWASP XXE) | Yes | defusedxml with `forbid_dtd`; entity bomb and external-entity tests (a marker file is never read) | None |
| Display safety (CWE-150, Trojan Source) | Yes | `<U+XXXX>` for hidden characters; parametrised test over seven characters; HTML escaping test | None |
| Bounded output (CWE-400, CWE-770) | Yes | Entry and byte budgets; long-value, entry-flood and byte-budget tests; byte-level fuzzing (300 examples) | None |
| Determinism (NFR-3) | Yes | Exact rationals, half-even rounding; same bytes give the same RFC 8785 bytes (test) | None |
| Offline (SEC-1, ADR-001), WebView lock-down (SEC-8) | Yes | No opener or network code; the GUI panel has no `a[href]` (test); copy-only link | None |
| Data minimisation (LED Art. 4(1)(c)) | Yes | GPS position, serials and owner names in reports at the owner's request | Profile section 8 row; DPO review pending (PRD OQ-16) |
| Licence policy | Yes | defusedxml PSF-2.0; allow-list extended | Profile section 8 row; owner confirmation pending |
| Accessibility (WCAG 2.2 AA) | Yes | Table captions and headers, `details`/`summary`, labelled search, copy status announced; axe check in `metadata.test.tsx` | Contrast by design tokens only (jsdom has no layout) |
| Wording: no identification, verification or authenticity claims | Yes | Notice "Ridge does not verify metadata ... does not by itself establish where, when or with what the photo was taken" in every record | None |

## 4. Forensic impact

Output pixels changed: no. Defaults or recorded parameters changed: no; reports gain `input.metadata`.

Revalidation decision required: none for the outputs. The metadata is a record of what the file states, not part of the method.

Examiner-facing wording changed: the new panel, report sections and notes. Checked: no identification, match, validation or authenticity claim, and every view says metadata is unverified.

Data classes touched: synthetic images only, made in memory by `tests/metadata_samples.py` and the dev preview. No real photo was opened.

## 5. Files changed

| File | Purpose of change |
| --- | --- |
| `src/ridge/metadata/__init__.py`, `values.py`, `exif.py`, `exif_names.py`, `gps.py`, `xmp.py`, `iptc.py`, `icc.py`, `containers.py`, `summary.py` (new) | Metadata readers, budgets, display safety, location and map link |
| `src/ridge/case/jobs.py` | `input.metadata` in the signed report |
| `src/ridge/case/metadata_render.py` (new), `reports.py`, `report_html.py` | "Photo metadata" in text and HTML reports |
| `src/ridge/sidecar/case_methods.py`, `handlers.py` | `metadata.get` |
| `pyproject.toml`, `requirements.lock`, `requirements-dev.lock`, `tools/gate.py` | defusedxml runtime dependency; PSF-2.0 allowed |
| `gui/src-tauri/src/commands/metadata.rs` (new), `commands/mod.rs`, `commands/list.rs`, `lib.rs`, `capabilities/main.json` | `photo_metadata` command and permission |
| `gui/src/components/PhotoMetadata.tsx` (new), `lib/usePhotoMetadata.ts` (new), `ipc/types.ts`, `ipc/commands.ts` | Panel, loader, types |
| `gui/src/screens/ReviewPanel.tsx`, `ReferencesSection.tsx`, `JobsSection.tsx`, `styles/app.css` | Panel under the photos; report view |
| `gui/src/dev/preview.ts`, `gui/src/dev/previewMetadata.ts` (new) | Synthetic metadata in the dev preview |
| `tests/metadata_samples.py`, `tests/test_metadata.py`, `tests/test_metadata_hostile.py`, `tests/test_metadata_reports.py`, `gui/src/test/metadata.test.tsx` (new) | Tests |
| `docs/prd.md`, `docs/architecture.md`, `docs/examiner_guide.md`, `CHANGELOG.md`, `Instruction_documentation/Project_Standards_Profile.md`, `forensic_evidence_and_biometric_data_standards.md`, `standards_applicability_and_compliance_matrix.md` | Documentation |

## 6. Data store, records and formats

- Job report: additive `input.metadata` (`ridge.photo-metadata/1`). Same report schema id; readers that ignore unknown fields are unaffected; reports stay well under the 1 MiB report limit (the metadata is bounded to about 200 kB of text). Reproduction compares outputs only.
- No custody-log, case-store or write-path change. `metadata.get` reads are logged as `evidence.read` or `reference.read`, like previews.

## 7. Configuration, keys and CI

- New runtime dependency `defusedxml==0.7.1` (hash-pinned, pure Python). The frozen sidecar picks it up by import; rebuild it (`python tools/build_sidecar.py`) before new installers.

## 8. Security

- New IPC command `photo_metadata`: validates a SHA-256 handle and maps to one sidecar method; the sidecar refuses unknown fields and roles other than evidence and reference.
- No new capability beyond that command; no opener, shell, fs or http permission; the navigation lock is unchanged.

## 9. Tests

Tests added:

- `tests/test_metadata.py` (25): every block of a camera JPEG, the exact location and link, words for EXIF codes, MakerNote by hash, XMP flattening, ICC/JPEG structure, determinism, hemispheres and below sea level, seven unusable positions, 0,0 and datum warnings, optional GPS fields, XMP fallback and mismatch, thumbnail by hash (and an out-of-range offset), IPTC, PNG, WebP, TIFF, HEIF, a file without metadata, rounding.
- `tests/test_metadata_hostile.py` (21): entity bomb, external entity, malformed XMP, seven hidden characters, text rules, long values, entry flood, byte budget, a huge packet, corrupt EXIF, the entry limit, non-images, byte-level fuzzing (hypothesis, 300 examples).
- `tests/test_metadata_reports.py` (9): signed report content, outputs metadata-free, text and HTML sections, hostile and forged values in HTML, older reports, sidecar `metadata.get` (evidence, reference by prefix, refusals, logged read).
- `gui/src/test/metadata.test.tsx` (7): copy-only link and coordinates with axe, groups and search, embedded images and notes, no position, report view and older reports, one logged read and a failure, placement under the photos.

Commands run:

```bash
python tools/gate.py all   # Windows 11 x86-64, Python 3.13.5, on the final working tree
```

```
=== all 11 gate(s) passed: docs, lint, format, typecheck, test, sast, deps, secrets, licenses, sbom, gui
```

- pytest: 856 passed, 3 skipped (POSIX permission bits on Windows), branch coverage 96.79 %, including the stored-golden comparison.
- Vitest: 107 passed (28 files). Rust: 34 passed; clippy, `cargo audit` and `cargo deny` clean. pip-audit: no known vulnerabilities in either lock; npm audit: 0 vulnerabilities.
- `licenses`: `defusedxml 0.7.1: Python Software Foundation License` accepted by the new allow-list entry.
- This handoff was written while that run was going; `python tools/gate.py docs` was run again afterwards with it in place and passed.

Found and fixed during the work:

- A GPS position without its N/S reference was mapped south of the equator: an empty string counted as a substring of "NS". It is now refused with a warning (the test failed before the fix).
- A metadata failure after the image opened could have been reported as a corrupt image and failed a job. The typed error now covers opening only, and every block is guarded.
- The editing tool turned escapes of bidirectional and zero-width characters into literal invisible characters in the source. Bandit B613 and ruff caught it; the characters are now built with `chr()`.
- A first gate run stopped at `lint` (one line over 120 characters in a new test); fixed before the run above.

Visual check: in the dev preview (`npm --prefix gui run dev`, mocked IPC, synthetic data), the panel sat under the photo pair. It showed the position, both Copy buttons, the note and the groups, with no link element, no horizontal overflow, theme colours in dark mode, 24 px targets and no console errors. The Jobs report view showed the recorded metadata. Screenshots could not be taken (the app window was hidden), so the checks were made through the DOM.

Tests not run and why:

- The installed Tauri application with a real photo: agents do not use real photos. The product owner can check it on a rebuilt build with a test photo from their own phone (location services on).

## 10. Release readiness

Release type: internal build. Ready: after review and merge, stacked after PR #27. Needs a rebuild of the sidecar and installers for the installed application to show it.

Rollback: revert the change. Reports made in between keep `input.metadata` and still verify and render.

## 11. Open risks and known issues

- DPO review of GPS positions, serial numbers and owner names in reports and disclosure packages, and of guidance on opening map links (PRD OQ-16, R-13).
- The owner should confirm the PSF-2.0 licence allow-list entry.
- MakerNotes are not decoded, so camera-specific facts in them (for example some phones' capture details) are not shown.
- `gui/src/screens/ReviewPanel.tsx` is 302 lines; moving `photoScale`/`outputScale` to `lib/` would bring it back under 300.

## 12. Recommended next work

1. Product owner: review the stacked pull request; merge it after PR #27, then retarget it to `main` if needed.
2. Product owner: confirm the PSF-2.0 allow-list entry; DPO: answer OQ-16.
3. Optionally a `ridge-case metadata CASE SHA [--json]` command for reviewers who work from the CLI.

## 13. First thing the next agent/developer should read or do

Read this handoff, then `src/ridge/metadata/__init__.py`, the `input.metadata` paragraph in `docs/architecture.md` §8.3 and ADR-013.
