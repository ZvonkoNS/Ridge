# Handoff_54.md

Date/time (ISO 8601 with offset): 2026-10-25T01:00+02:00
Author/agent: Claude Code (claude-fable-5-1), closing handoff of the end-user review follow-up (2026-10-24/25)
Project: Ridge
Branch: `afis-linked-marking-35` (stack top; local commits only, nothing pushed, no pull request opened for these four branches)
Base commit: `d4e5af5` (tip of `afis-docs-31`, pull request #45)
Latest commit: see `git log afis-linked-marking-35`

## 1. Scope

Requested change: the product owner asked for the suggestions of the end-user review (an examiner's and an investigator's assessment of the app) to be implemented under the instruction documentation.

What the review asked for, and what this run did:

| Suggestion | Done | Branch | Handoff |
| --- | --- | --- | --- |
| A verdict at capture time: should the finger be photographed again? | Capture check (FR-54): CLI, sidecar, GUI card before import and per photo | `afis-capture-check-32` | 50 |
| Hide the method variants behind a research mode; grayscale as the default comparison export; plainer NFIQ 2 words | Research mode switch (ADR-015), `export-all` default `export-gray`, case summary labels, guide paragraph | `afis-research-mode-33` | 51 |
| Manual minutiae marking with the markings in the record | Annotation sets as signed custody entries, annotated-image export, CLI, sidecar, Rust, panel, readable report (FR-55, ADR-016) | `afis-annotations-34` | 52 |
| A synchronised side-by-side and the marking tool in the viewer | Linked views and the marking tool (FR-56) | `afis-linked-marking-35` | 53 |
| A pilot with real photographs and real searches | Not an engineering task: the protocol and the questionnaire exist (Handoff_47); the data decision and the searches are the DPO's, the FQM's and the AFIS team's | – | – |
| The AFIS format decision and a record writer | Waits for OQ-4 (the questionnaire); a record writer before the answer would be guesswork | – | – |

The four branches continue the stack of Handoff_48 above `afis-docs-31` (pull request #45): `4ddbb40` → `d534862` → `69ba9a1` → `0e05813`, plus `763322b` on the last branch (an explicit accessible name for the link-views checkbox, found while checking the mocked GUI in a browser: the capture-check card, the hidden variants, the marking tool and the link toggle all rendered and responded).

## 2. Current repository state

Git status summary: clean on `afis-linked-marking-35` after this handoff's commit. Seventeen `afis-*` branches above `main`; the thirteen up to `afis-docs-31` are pushed with pull requests #34 to #45 (Handoff_49); the four new ones are local only.

## 3. Standards applicability and evidence

Project standards profile updated: not needed; ADR-015 and ADR-016 are proposed rows in the architecture's ADR table.

| Standard/control/rule | Applies? | Evidence produced | Exception/deviation |
| --- | --- | --- | --- |
| Forensic standard (no claims; originals read-only; everything hashed and logged) | Yes | Every new output is hashed and logged; the capture check and the annotations state what they are not | None |
| Custody and signatures | Yes | Annotation sets are signed at once; the export entry's own `seq` is untouched (a defect found and fixed, Handoff_52 §6) | None |
| Trust boundaries | Yes | New sidecar methods with strict schemas, new Rust commands with typed, bounded requests, GUI displays and proposes only | None |
| Coding standards (file sizes, entrypoints, validation) | Yes | New modules under 200 lines; handlers thin; `check_marks`, `check_bytes` validate | None |
| Testing (success, failure, boundary, regression) | Yes | Section 9 | Tauri WebDriver E2E (profile exception) |

Standards checks or tools run: section 9.

Exceptions, deviations or evidence gaps: ADR-015 and ADR-016 await the owner; the capture check's thresholds are provisional until the pilot.

Steps outside coding work: the owner decides ADR-015 and ADR-016; the DPO and FQM take the pilot's data decision; the AFIS team answers the questionnaire.

## 4. Forensic impact

Output pixels changed: no. No pipeline change in this run; goldens exact in the gates.

Defaults or recorded parameters changed: `ridge-case export-all` exports `export-gray` by default (the GUI already did). New custody actions `examiner.annotation` (followed by `chain.sign`) and `annotation.export`. No report field changed.

Revalidation decision required / recorded: not applicable.

Examiner-facing wording changed (checked against forbidden claims): per handoff; every new view states that it is not a quality score, a match, a count of agreement or an identification.

Data classes touched: synthetic only.

## 5. Files changed

Per Handoff_50 to Handoff_53, section 5.

## 6. Data store, records and formats

New custody entries as in Handoff_52 §6; no schema version bump.

## 7. Configuration, keys and CI

None.

## 8. Security

Four new allow-listed commands with their sidecar methods (`check_photo`, `check_evidence`, `add_annotation`, `list_annotations`, `export_annotated`); one new read path for a dialog-chosen file (the import's bounds and decoder); one new logged plaintext write (the annotated PNG). No new trust boundary, no network, no new dependency.

## 9. Tests

Commands run on the stack top (`0e05813`):

```bash
# in a detached worktree of 0e05813, PYTHONPATH=<worktree>/src
.venv/Scripts/python.exe tools/gate.py docs lint format typecheck test sast deps secrets licenses sbom   # all 10 gate(s) passed; test: 995 passed, 3 skipped in 1192 s; deps: no known vulnerabilities in either lock
# in the main tree at 0e05813 and again at 763322b
.venv/Scripts/python.exe tools/gate.py gui   # all 1 gate(s) passed: gui (vitest 137 tests in 39 files; cargo 36 tests; clippy, npm licences, SBOM clean); a first run collided with a dev preview server holding node_modules and was repeated alone
```

Per-branch runs are in Handoff_50 to Handoff_53.

Determinism and golden results: exact (`tests/test_characterization.py` inside the test gate).

Tests not run and why: Apple-silicon pixel tests (no arm64 machine here; the pipeline is unchanged in this run); Tauri WebDriver E2E (profile exception); the GitHub Actions matrix (runs on the pull requests once pushed).

Required tests still missing: calibration of the capture check's thresholds on real photographs (pilot).

## 10. Release readiness

Release type: internal build after merge. Ready: the stack is gated as above; merging is the owner's decision. Blockers: none for the default pipeline. Rollback: each branch is one commit and reverts cleanly in reverse stack order.

## 11. Open risks and known issues

- The four new branches sit above #45; they can be pushed and opened as pull requests #46 to #49 against each other, or squashed differently, as the owner prefers.
- Research mode is a session switch, not an authorisation (Handoff_51 §11).
- The capture check's clarity threshold was set on synthetic fingers (Handoff_50 §11).
- The linked views are approximate after an upright rotation or a rectification (Handoff_53 §11).

## 12. Recommended next work

1. Decide whether to push the four branches and open their pull requests above #45.
2. Owner: ADR-015 and ADR-016.
3. The pilot (Handoff_47) once OQ-4 and OQ-6 are answered; it also calibrates the capture check.

## 13. First thing the next agent/developer should read or do

This handoff's section 1 table, then `git log --oneline afis-docs-31..afis-linked-marking-35`.
