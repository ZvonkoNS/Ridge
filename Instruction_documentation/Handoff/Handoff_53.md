# Handoff_53.md

Date/time (ISO 8601 with offset): 2026-10-25T00:20+02:00
Author/agent: Claude Code (claude-fable-5-1), end-user review follow-up (examiner's item): linked views and the marking tool
Project: Ridge
Branch: `afis-linked-marking-35` (stacked on `afis-annotations-34`; local commit only, nothing pushed)
Base commit: `69ba9a1` (tip of `afis-annotations-34`, Handoff_52)
Latest commit: see `git log afis-linked-marking-35`

## 1. Scope

Requested change: from the end-user review, the examiner's comparison workflow: a synchronised side-by-side of the original and the output, and marking minutiae in the viewer with the markings in the record (the record is Handoff_52's).

Completed work (GUI only; no Python or Rust change):

- **Linked views (PRD FR-56, `gui/src/lib/link.ts`).** "Link views" in the review panel drives both viewers from one shared view: the photo pixel at the centre and the screen pixels per photo pixel. The output viewer follows through the job's print area: output pixels per photo pixel from the output's width over the box's width, the box's offset, and the mirror of a comparison export. Linking starts at the area's centre with the output at its actual size. After an upright rotation or a rectification the frame is no longer a rectangle, the box is only its bounds, and the label says the link is approximate. `ImageViewer` accepts a controlled `focus` (the image pixel at its centre) beside the controlled `zoom`, derives the pan from it, and reports pans, zooms and fits as a new focus; its uncontrolled behaviour is unchanged.
- **Marking tool (`gui/src/components/MarkingPanel.tsx`).** "Mark minutiae" under the output switches the viewer to the `mark` tool: a click places a numbered mark of the chosen kind (ending, bifurcation, other) with the optional label typed beforehand, in whole pixels of the output and only on the image; unsaved marks are listed with a remove button and drawn with an asterisk; a note can be added; "Save N marks" records the set through `annotation.add` with `replaces` set to the latest current set of that image, then draws the saved set in the examiner's colour with its numbers (a checkbox hides it). Marks are drawn by the existing overlay, whose mark type gained a third kind (triangle), an optional direction (the automatic minutiae keep theirs; the examiner's marks have none) and a label.
- Docs: PRD FR-56; architecture (linked views and marking paragraph); CHANGELOG; examiner guide ("Jobs and review" items 2 and 5).

Out of scope: a direction for the examiner's marks; dragging marks; linking the export to a reference image (the References screen keeps its equal-scale zoom link).

## 2. Current repository state

Git status summary: committed on `afis-linked-marking-35`.

Recent commits: `69ba9a1` (Handoff_52) and the stack below.

## 3. Standards applicability and evidence

Project standards profile updated: not needed.

| Standard/control/rule | Applies? | Evidence produced | Exception/deviation |
| --- | --- | --- | --- |
| Forensic UI rules (original beside the processed output, no pixel change, labels) | Yes | The link is viewer geometry only; marks are SVG over unchanged pixels; the approximate case is labelled | None |
| WebView holds no security logic | Yes | Saving goes through the existing `add_annotation` command; Rust and the sidecar validate the marks | None |
| Accessibility (keyboard operation, labels) | Yes | The toggle, the kind radios, the label and note fields, the remove buttons and the save button are labelled; axe check in the marking test | Marking itself is a pointer action, as the ruler and region tools already are |
| Testing (render, interaction, geometry) | Yes | Section 9 | None |

Standards checks or tools run: section 9.

Exceptions, deviations or evidence gaps: none.

Steps outside coding work: none.

## 4. Forensic impact

Output pixels changed: no.

Defaults or recorded parameters changed: none. Nothing is recorded until the examiner saves a set (FR-55).

Revalidation decision required / recorded: not applicable.

Examiner-facing wording changed (checked against forbidden claims): "Link views", "(approximate: the finger was rotated or unrolled)", "Mark minutiae", "Marking: click the output to place a mark", "Save N marks (replaces set #k)", "Show saved marks", "Unsaved marks are numbered with an asterisk"; the annotations note is repeated. No match or identification claim.

Data classes touched: none.

## 5. Files changed

| File | Purpose of change |
| --- | --- |
| `gui/src/lib/link.ts` (new) | Link geometry |
| `gui/src/components/ImageViewer.tsx` | Controlled `focus`, the `mark` tool, examiner marks |
| `gui/src/components/ViewerOverlay.tsx`, `gui/src/lib/minutiae.ts` | Third kind, optional direction, label, examiner styling |
| `gui/src/components/MarkingPanel.tsx` (new) | `useMarking` and the panel |
| `gui/src/screens/ReviewPanel.tsx` | Link toggle, shared view, marking |
| `gui/src/styles/app.css` | Mark styles, panel layout |
| `gui/src/test/link.test.ts`, `gui/src/test/viewerlink.test.tsx`, `gui/src/test/marking.test.tsx` (new) | Tests (section 9) |
| `docs/prd.md`, `docs/architecture.md`, `CHANGELOG.md`, `docs/examiner_guide.md` | Requirements, design, changelog, guide |
| `Instruction_documentation/Handoff/Handoff_53.md` (new) | This handoff |

## 6. Data store, records and formats

None.

## 7. Configuration, keys and CI

None.

## 8. Security

No new command or method; the WebView proposes marks through the bounded `add_annotation` command.

## 9. Tests

Tests added or updated:

- `gui/src/test/link.test.ts` (new): photo to output and back with and without the mirror; the starting view and view conversion both ways; no link without an area or an output; approximate after a warp.
- `gui/src/test/viewerlink.test.tsx` (new): a controlled focus sits at the viewer's centre; arrow keys, zoom and fit report a new focus; a mark is reported in whole pixels only with the mark tool and only on the image.
- `gui/src/test/marking.test.tsx` (new): the saved set is drawn; marks are placed with kind and label, listed, removed with renumbering, saved with the note and `replaces`, and the new set is shown (axe clean); `renumber` and `latestSet`.

Commands run:

```bash
cd gui && npm run lint && npm run typecheck && npx prettier --check . && npm test -- --run   # 39 files, 137 tests passed
.venv/Scripts/python.exe tools/gate.py docs   # pass
```

Determinism and golden results: unaffected (no Python change).

Tests not run and why: the Python and Rust suites are unchanged on this branch (run on the stack top in the closing gate); Tauri WebDriver E2E (profile exception).

Required tests still missing: none.

## 10. Release readiness

Release type: internal build. Ready: as part of the stack. Blockers: none. Rollback: revert the commit.

## 11. Open risks and known issues

- The link uses the print area's box, so for a job that rotated or unrolled the finger the two viewers agree only roughly; the label says so. An exact link would map through the frame polygon.
- A mark has no direction; examiners who chart direction note it in the label or the set's note.

## 12. Recommended next work

The full gate on the stack top and the closing handoff of this follow-up run, then the decision whether to push the four new branches and open their pull requests above #45.

## 13. First thing the next agent/developer should read or do

`gui/src/components/MarkingPanel.tsx` and `gui/src/lib/link.ts`.
