# Handoff_27.md

Date/time (ISO 8601 with offset): 2026-10-19T23:45+02:00
Author/agent: Claude Code (claude-opus-5-5)
Project: Ridge
Branch: `m5-print-area-13` → `main`
Base commit: `3c765dd` (Merge pull request #25, Handoff_26)
Latest commit: see the pull request

## 1. Scope

Requested change: "I want the investigator to see where the print has been extracted from, from which part of the hand. Can you highlight the part where the print was extracted on the left image?" (product owner, 2026-10-19).

Completed work:

- The pipeline now says where the print came from. `src/ridge/pipeline/location.py` maps the working-space crop window and the kept print area back to the pixels of the photo it was given: the frame the print image shows (`box`), the outer edge of each kept area (`outline`, simplified to a quarter of a ridge spacing, at most 256 points in all), and the number of kept areas (`parts`). `ExtractionResult.location` carries it. Output pixels do not depend on it.
- Job reports record it as `measurements.print_area` (`box_px`, `outline_px`, `parts`), in the photo's pixels after EXIF orientation, the space of `roi` and `ruler`. A region of interest is added back (`jobs.print_area`).
- The sidecar's `job.run` result carries it through `measurements` unchanged; the Tauri core passes results through as JSON, so no Rust change was needed.
- GUI review panel: after a job, the original photo shows the area. A solid green line on a dark halo surrounds the area kept as the print. A dashed box marks the print image's frame. The rest of the photo is dimmed on screen only. A checkbox, "Show where the print was extracted (job xxxxxxxx)", hides or shows it (on by default). The legend uses line style rather than colour. It also says when the comparison export is mirrored, because the export then shows the area the other way round.
- Job summary (review panel and Jobs section): a "Print area" row in words, which is also what a screen reader gets, since the drawing is `aria-hidden`. Reports signed before this change say "not recorded".
- Readable reports (text and HTML) add a "Print area" line. The one-line helpers (`export_line`, `nfiq2_line`, `minutiae_line`, new `print_area_line`) moved to `src/ridge/case/report_lines.py`, so `reports.py` stays under 300 lines (309 → 276).
- Docs: architecture §8.3 (schema outline and a paragraph on `print_area`), PRD FR-50 note, examiner guide (Jobs and review, step 2), CHANGELOG.
- PR #27 review (Codex, P2): hiding the outline and then running another job kept the new job's area hidden. The switch now belongs to one job, so each new job shows its own area again (`usePrintArea`; test `shows the next job's area again after the last one was hidden`, which fails without the fix).

Out of scope:

- Past jobs: their signed reports have no `print_area` and are not changed. Run the job again to see the outline.
- Showing a past job's outline when its report is opened in the Jobs section (only the summary row is shown there).
- New installers. The 0.2.0 installers of Handoff_26 do not contain this change.

## 2. Current repository state

- `main` is at `3c765dd`. This branch adds the changes in section 5 in one commit.

## 3. Standards applicability and evidence

Project standards profile updated: not needed (no new exception).

| Standard/control/rule | Applies? | Evidence produced | Exception/deviation |
| --- | --- | --- | --- |
| Forensic: output pixels unchanged, goldens unchanged | Yes | `tests/golden/` untouched; golden comparison passes in the gate | None |
| Determinism (NFR-3) | Yes | Location is integer geometry from the same per-architecture computation; `test_crop_changes_the_frame_but_not_the_outline`, roi tests compare exact JSON | None |
| Report integrity (signed RFC 8785 report) | Yes | Additive field inside the signed report; schema id unchanged (`ridge.job-report/1`); older reports render (test) | None |
| Bounded output (CWE-400/789) | Yes | At most 256 outline points per report; `test_many_parts_are_capped_and_counted` | None |
| WebView is untrusted | Yes | The GUI only draws the area the trusted core computed and signed; no computation moved to the WebView | None |
| Accessibility (WCAG 2.2 AA) | Yes | Legend by line style, not colour; area in words in the summary; axe check in `printarea.test.tsx` | Visual contrast of the overlay on real photos not reviewed (no real photos) |
| Wording: no identification or match claims | Yes | "where the print was extracted", "area kept as the print" | None |

## 4. Forensic impact

Output pixels changed: no. Extraction, export and minutiae code paths compute the same images; only metadata was added.

Defaults or recorded parameters changed: no. `measurements` gains `print_area`.

Revalidation decision required / recorded: none required for the outputs. The outline is a display aid derived from the same print map that already cut the print.

Examiner-facing wording changed: new overlay legend, summary row and report line. Checked: no identification, match or validation claim.

Data classes touched: synthetic images only (tests and the dev preview). No real photo was opened.

## 5. Files changed

| File | Purpose of change |
| --- | --- |
| `src/ridge/pipeline/location.py` (new) | Working space → photo pixels: box, outline, parts |
| `src/ridge/pipeline/extract.py` | `ExtractionResult.location` |
| `src/ridge/case/jobs.py` | `measurements.print_area`, region of interest added back |
| `src/ridge/case/report_lines.py` (new) | Report one-line helpers, moved from `reports.py`, plus `print_area_line` |
| `src/ridge/case/reports.py`, `src/ridge/case/report_html.py` | Use `report_lines`; "Print area" line |
| `gui/src/components/PrintArea.tsx` (new) | Overlay state, SVG shape, switch and legend, summary line |
| `gui/src/components/ImageViewer.tsx` | `overlay` prop drawn under region and ruler |
| `gui/src/screens/ReviewPanel.tsx`, `gui/src/screens/JobSummary.tsx` | Overlay on the original; "Print area" row |
| `gui/src/ipc/types.ts` | `PrintArea`, `Measurements.print_area?` |
| `gui/src/styles/app.css` | `.ov-area-*`, `.area-note`, `.area-legend` |
| `gui/src/dev/preview.ts` | Synthetic print area in the dev preview |
| `tests/test_print_area.py` (new), `tests/test_sidecar_gui_methods.py`, `gui/src/test/printarea.test.tsx` (new) | Tests |
| `docs/architecture.md`, `docs/prd.md`, `docs/examiner_guide.md`, `CHANGELOG.md` | Documentation |

## 6. Data store, records and formats

- Job report: additive `measurements.print_area`. Same schema id; readers that ignore unknown fields are unaffected. Reproduction compares outputs only, so old and new reports reproduce as before.
- No custody-log, case-store or write-path change.

## 7. Configuration, keys and CI

- None.

## 8. Security

- No decoder, limit, IPC command or capability change. The overlay is SVG drawn from numbers in the signed report; React escapes attribute values.

## 9. Tests

Tests added:

- `tests/test_print_area.py` (10): box matches the output frame on four synthetic cases, outline surrounds the kept ridges, crop changes the frame but not the outline, the 256-point cap with 400 parts, shift and JSON form, the report with and without a region of interest (exact match with the crop's own location moved by the offset), text and HTML report lines, older reports.
- `tests/test_sidecar_gui_methods.py::test_job_results_say_where_the_print_came_from`.
- `gui/src/test/printarea.test.tsx` (4): outline, frame and dimming drawn on the original after a job; hide switch with an axe check; older result without the area; summary line.

Commands run:

```bash
python tools/gate.py all   # Windows 11 x86-64, Python 3.13.5, on the final working tree
```

```
=== all 11 gate(s) passed: docs, lint, format, typecheck, test, sast, deps, secrets, licenses, sbom, gui
```

- pytest: 790 passed, 3 skipped, branch coverage 97.51%, including the stored-golden comparison.
- Vitest: 99 passed (27 files). Rust: 34 passed; clippy and `cargo audit` clean.
- Earlier runs: one stopped at lint (compound asserts and a Yoda condition in the new tests, fixed). In another, the `gui` gate's `npm ci` hit `EPERM`, because the Vite dev server used for the visual check held a native module open. Both were resolved before the clean run above.

Visual check: the dev preview (`npm --prefix gui run dev`, mocked IPC, synthetic photo) showed the outline, frame, dimming and legend; the switch removed and restored the drawing; no console errors. The synthetic golden photos were also drawn with the new outline beside the pipeline's own debug region image: the outlines coincide.

Tests not run and why:

- The installed Tauri application with a real photo: real photos are not used by agents. The product owner can check it on a rebuilt build with a test case.

## 10. Release readiness

Release type: internal build. Ready: yes after review and merge. Needs a rebuild (`python tools/build_sidecar.py`, then `npx tauri build`) for the installed application to show it.

Rollback: revert the change; reports made in between keep their extra field and still verify and render.

## 11. Open risks and known issues

- The outline is about a ridge spacing accurate (the print map is smoothed at that scale); it is a display aid, the box is exact to whole pixels.
- Overlay colours were chosen for skin and background but not reviewed on real photos.

## 12. Recommended next work

1. Product owner: run a job on a test photo in a rebuilt build and confirm the outline is where expected.
2. Optionally draw a past job's outline from its verified report in the Jobs section.

## 13. First thing the next agent/developer should read or do

Read this handoff, then `src/ridge/pipeline/location.py` and the `print_area` paragraph in `docs/architecture.md` §8.3.
