# Handoff_57.md

Date/time (ISO 8601 with offset): 2026-10-25T04:30+02:00
Author/agent: Claude Code (claude-fable-5-1), Codex review fixes for the stack, the README as a manual, the Windows installers in the repository
Project: Ridge
Branch: `afis-review-fixes-37` (stacked on `afis-release-check-36`; local commit only until the owner's push)
Base commit: `080d73d` (tip of `afis-release-check-36`, pull request #50)
Latest commit: see `git log afis-review-fixes-37`

## 1. Scope

Requested change: write a detailed README (installation, usage, everything), comment the code where not done, put the installers in the main folder, then push to `main` and clean the branches and the repository. Before a merge the project requires the Codex review threads to be fixed and resolved and the full gate to pass; this branch does the fixes, the README and the installers, and the merge follows once it is gated.

Completed work:

- **Eighteen Codex findings fixed** (all P2), one commit, each with a regression test in `tests/test_review_fixes.py` or the GUI tests:
  - #35 `toOptions` sends the default scale kind when no points are given, so a card kind never travels with `ruler: null` (also what "Run on all photos" sends).
  - #36 the export's resolution note and the new `export.pixels_per_photo_pixel` count the pipeline's own enlargement of a low-resolution photo (`binary.factor * output_scale`).
  - #37 the cover sheet always has a limits-of-use row: the outcome, "none configured in this store", or "not recorded in this report".
  - #38 `sweep_factors` refuses a sweep whose steps would collide after rounding, before any file is written.
  - #39 provenance distinguishes an unreadable EXIF block (`exif-unreadable`) from an absent one, and finds XMP history under any declared prefix.
  - #40 `read_ranks` refuses a row with fewer or more fields than the header; an explicitly empty rank stays "not returned".
  - #44 the rectification's reported pad half-width is the median over the rows that hold finger; outline edges are subdivided before the row-wise mapping back and bounded again to 256 points.
  - #45 the pilot protocol's ranks CSV and command match `ridge-validate` (`probe`, `rank`, `group`; repeated `--rank`).
  - #46 the capture check no longer treats a Software tag as a sign of editing; it is a neutral note.
  - #47 the research switch is disabled while a batch runs.
  - #48 annotations accept an output of a rerun job (a duplicate write under the rerun's id counts), the annotated PNG keeps the comparison export's resolution, and every mark number is kept inside the image.
  - #49 the linked views mirror only for comparison exports; a save that completes after the examiner moved to another image installs nothing there and keeps that image's unsaved marks.
- **README** rewritten as a full manual: what Ridge does, installation (installers, Python package, first-case setup), the desktop application, `ridge`, `ridge-case` by task, outputs and records, scale and AFIS submissions, variants and research mode, `ridge-validate`, how the extraction works, photographing a finger, security and privacy, configuration, development, building, troubleshooting, documentation index, limits and licence.
- **Installers** under `installers/`: the Windows MSI and per-user NSIS setup of Handoff_56 with `SHA256SUMS.txt` and a README (unsigned engineering builds; macOS and Linux bundles are built on their own platforms and are not in the repository).
- **Code comments**: docstrings are enforced by ruff's `D` rules on the Python side; the exported GUI functions and constants added in this run that lacked a doc comment got one, and one Rust helper too.

Out of scope: the merge itself (next handoff); macOS and Linux installers.

## 2. Current repository state

Git status summary: committed on `afis-review-fixes-37`.

Recent commits: `080d73d` (Handoff_56) and the stack below.

## 3. Standards applicability and evidence

Project standards profile updated: not needed.

| Standard/control/rule | Applies? | Evidence produced | Exception/deviation |
| --- | --- | --- | --- |
| Review workflow (Codex threads fixed and resolved before merge) | Yes | Each finding fixed with a test; the threads are answered and resolved when this branch is pushed | None |
| Testing (reproduce with a failing test, then fix) | Yes | `tests/test_review_fixes.py`, `gui/src/test/markingrace.test.tsx`, additions to `params.test.ts` and `test_rectify.py` | None |
| Determinism / goldens | Yes | No pipeline numerics changed; the full gate on the stack top runs before the merge | None |
| Repository hygiene (no biometric data; installers are not) | Yes | `installers/` holds two binaries and their hashes; `.gitignore` unchanged | Two large binaries (61 and 87 MB) now live in git history; a release-asset or LFS channel would be lighter (owner's call) |

Standards checks or tools run: section 9.

Exceptions, deviations or evidence gaps: none.

Steps outside coding work: none.

## 4. Forensic impact

Output pixels changed: no. The rectification's recorded `half_width_px` and the location's mapped outline change for jobs that used the `rectify` variant (unvalidated, off by default); the report gains `export.pixels_per_photo_pixel` and may now carry a resolution note for low-resolution photos that lacked one before, which is a correction.

Defaults or recorded parameters changed: none.

Revalidation decision required / recorded: not applicable (no change to the characterised pipeline; goldens exact).

Examiner-facing wording changed (checked against forbidden claims): the cover sheet's limits row texts, the capture check's software note, the provenance hint for an unreadable EXIF block; no identification claim.

Data classes touched: synthetic only.

## 5. Files changed

| File | Purpose of change |
| --- | --- |
| `src/ridge/case/export_step.py`, `cover_sheet.py`, `annotations.py`, `annotation_image.py`, `src/ridge/export/sweep.py`, `src/ridge/metadata/provenance.py`, `src/ridge/validation/report.py`, `src/ridge/pipeline/rectify.py`, `location.py`, `src/ridge/capture.py` | The fixes of section 1 |
| `gui/src/screens/ParametersForm.tsx`, `ReviewPanel.tsx`, `gui/src/components/MarkingPanel.tsx` | The GUI fixes |
| `gui/src/lib/link.ts`, `gui/src/components/CaptureCheckCard.tsx`, `AnnotationsPanel.tsx`, `gui/src/screens/MethodVariants.tsx`, `gui/src-tauri/src/commands/annotations.rs` | Doc comments |
| `tests/test_review_fixes.py` (new), `tests/test_rectify.py`, `gui/src/test/markingrace.test.tsx` (new), `gui/src/test/params.test.ts` | Tests |
| `README.md`, `installers/README.md` (new), `installers/*.msi`, `installers/*.exe`, `installers/SHA256SUMS.txt`, `docs/pilot_protocol.md`, `CHANGELOG.md` | Manual, installers, protocol fix, changelog |
| `Instruction_documentation/Handoff/Handoff_57.md` (new) | This handoff |

## 6. Data store, records and formats

Report field added: `export.pixels_per_photo_pixel`. No migration; older reports lack it and render as before.

## 7. Configuration, keys and CI

None.

## 8. Security

No new trust boundary. The annotation membership check reads the custody log instead of the deduplicated item's first job id, which is stricter about the job and no weaker about the image.

## 9. Tests

Commands run:

```bash
.venv/Scripts/python.exe -m ruff check src tests tools && .venv/Scripts/python.exe -m ruff format --check src tests tools   # clean
.venv/Scripts/python.exe -m mypy                                                        # Success: no issues found in 206 source files
.venv/Scripts/python.exe -m pytest tests/test_review_fixes.py tests/test_rectify.py tests/test_annotations.py tests/test_case_export.py tests/test_sweep.py tests/test_provenance.py tests/test_validation_metrics.py tests/test_capture.py tests/test_submission.py tests/test_print_area.py -q   # 106 passed in 204 s
cd gui && npm run lint && npm run typecheck && npx prettier --check . && npm test -- --run   # 40 files, 139 tests passed
cd gui/src-tauri && cargo fmt --check && cargo clippy --locked --all-targets -- -D warnings   # clean
.venv/Scripts/python.exe tools/gate.py docs   # pass
# the full gate on this stack top is in the next handoff
```

Determinism and golden results: the full gate (next handoff) runs `tests/test_characterization.py`; no pipeline numerics changed here.

Tests not run and why: the full `gate.py all` runs on this branch's tip before the merge (next handoff); Tauri WebDriver E2E (profile exception).

Required tests still missing: none.

## 10. Release readiness

Release type: internal build. Ready: as part of the stack. Blockers: none. Rollback: revert the commit.

## 11. Open risks and known issues

- The installers in git make every clone about 150 MB heavier; GitHub refuses files above 100 MB, and the MSI is at 87 MB. A GitHub release asset or Git LFS is the lighter channel for future builds.
- The fixes for the lower pull requests land through this branch at the top of the stack; the lower branches merge with the findings still in their code and the fix arrives when this branch merges, minutes later, in the same bottom-up pass.

## 12. Recommended next work

Gate this branch's tip (`gate.py all`), push it, open its pull request, answer and resolve the eighteen threads, merge the stack bottom-up into `main`, delete the merged branches and write the closing handoff.

## 13. First thing the next agent/developer should read or do

`tests/test_review_fixes.py` (one test per finding) and the new README.
