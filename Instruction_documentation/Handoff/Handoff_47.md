# Handoff_47.md

Date/time (ISO 8601 with offset): 2026-10-24T17:50+02:00
Author/agent: Claude Code (claude-fable-5-1), autonomous window of 2026-10-24 (Handoff_35 section 1), items 12 to 14 of the AFIS-readiness assessment
Project: Ridge
Branch: `afis-docs-31` (stacked on `afis-method-rectify-30`; local commit only, nothing pushed)
Base commit: `0fca537` (tip of `afis-method-rectify-30`)
Latest commit: see `git log afis-docs-31`

## 1. Scope

Requested change: the organisational items of the assessment: a questionnaire for the AFIS team behind OQ-4, a pilot protocol template around rank-k hit rates, and capture guidance for the originals. Documents only; no code change.

Completed work:

- **`docs/afis_integration_questionnaire.md`.** Thirty questions in seven groups (system and workflow, accepted image inputs, records and metadata, scale and uncertainty, search output for a pilot, transfer and custody, pilot and sign-off), each with why it matters for Ridge and an answer cell, and a closing section on what engineering will do with the answers (export defaults, FR-41 record writer as an ADR, FR-38 fields, pilot protocol).
- **`docs/pilot_protocol.md`.** A template: purpose and limits (a measurement, not a validation; every candidate is the examiner's to conclude), roles with the rule that engineering and coding agents never handle real data, preconditions, the data decision left to the DPO and the FQM (consented volunteers or closed cases, with the considerations of each), design (unit, Wilson-interval sample-size table, arms: default, no reference, sweep, grayscale, one ADR-014 variant at a time; capture-condition codes), the step-by-step procedure, the ranks CSV and the `ridge-validate --ranks` command (FR-43), analysis and acceptance against PRD §12's provisional targets (OQ-7), a report template with a fixed non-claim statement, risks and sign-off.
- **`docs/capture_guidance.md`.** Guidance for investigators: camera settings, the scale reference (ruler or ISO/IEC 7810 ID-1 card in the plane of the pad; photograph anyway when none is available, Ridge says so), framing and a straight-on view with slight rolls, focus and distance, diffuse light without glare, handling the original (no edits, keep metadata, transfer unchanged), a capture note, a what-to-avoid table, what Ridge does with the photograph, and a one-page checklist.
- Links: PRD OQ-4 and OQ-6 rows point to the documents; README's documentation table lists them; CHANGELOG entry.
- Correction: Handoff_46's pending line for Handoff_45's worktree gate now points here (section 9).

Out of scope: answering the questions (owners: Product Owner, AFIS team, DPO, FQM); any real data.

## 2. Current repository state

Git status summary: committed on `afis-docs-31`.

Recent commits: `0fca537` (Handoff_46), `91ea2e0` (Handoff_45) and the earlier stack below.

## 3. Standards applicability and evidence

Project standards profile updated: not needed.

| Standard/control/rule | Applies? | Evidence produced | Exception/deviation |
| --- | --- | --- | --- |
| Forensic standard (no claims of identification, matching, validation or certification) | Yes | Every document states that a search hit is a candidate for the examiner and a pilot result is a measurement, not a validation | None |
| Biometric data rules (synthetic only; engineering and agents never handle real data) | Yes | Pilot protocol section 2 and section 4 make the rule part of the pilot; the data decision is assigned to the DPO and the FQM | None |
| ISO/IEC 19795-1 (identification metrics) | Yes | Rank-k hit rates with Wilson intervals and the CMC curve, computed by `ridge-validate --ranks` | None |
| ANSI/NIST-ITL, ISO/IEC 39794-4, WSQ (exchange) | Informational | The questionnaire asks which edition and format the AFIS reads; nothing is implemented until OQ-4 is answered | None |

Standards checks or tools run: section 9.

Exceptions, deviations or evidence gaps: none.

Steps outside coding work: the Product Owner sends the questionnaire; the DPO and the FQM take the data decision; the FQM approves the capture guidance.

## 4. Forensic impact

Output pixels changed: no.

Defaults or recorded parameters changed: none.

Revalidation decision required / recorded: not applicable.

Examiner-facing wording changed (checked against forbidden claims): the three documents; each carries the non-claim statement.

Data classes touched: none.

## 5. Files changed

| File | Purpose of change |
| --- | --- |
| `docs/afis_integration_questionnaire.md` (new) | Questions for the AFIS team (OQ-4) |
| `docs/pilot_protocol.md` (new) | Pilot protocol template |
| `docs/capture_guidance.md` (new) | Capture guidance and checklist |
| `docs/prd.md`, `README.md`, `CHANGELOG.md` | Links from OQ-4 and OQ-6, the documentation table, the changelog |
| `Instruction_documentation/Handoff/Handoff_46.md` | The pending gate line points to this handoff |
| `Instruction_documentation/Handoff/Handoff_47.md` (new) | This handoff |

## 6. Data store, records and formats

None.

## 7. Configuration, keys and CI

None.

## 8. Security

No code change. The documents tell investigators to transfer originals unchanged and keep pilot data out of engineering's reach.

## 9. Tests

Tests added or updated: none (documents).

Commands run:

```bash
.venv/Scripts/python.exe tools/gate.py docs   # pass
# Handoff_45's branch (afis-method-frequency-29, 91ea2e0) in a worktree: python tools/gate.py test   # GATE45_RESULT
```

Determinism and golden results: unaffected.

Tests not run and why: the full `gate.py all` on the stack top follows in the closing handoff; the GUI gate's `npm ci`/build steps; Tauri WebDriver E2E (profile exception).

Required tests still missing: none for documents.

## 10. Release readiness

Release type: documentation. Ready: yes. Blockers: none. Rollback: revert the commit.

## 11. Open risks and known issues

- The questionnaire's usefulness depends on the AFIS team's answers; until OQ-4 is answered, FR-41 (exchange format) stays open and the pilot cannot start.
- The pilot protocol's sample sizes make large differences visible only; a validation study needs the FQM's plan (OQ-6, OQ-7).

## 12. Recommended next work

The full `python tools/gate.py all` on the stack top, the closing handoff of the autonomous window, and then the decision whether to push the eleven stacked branches and open their pull requests.

## 13. First thing the next agent/developer should read or do

`docs/pilot_protocol.md` section 4 (the data decision) and `docs/afis_integration_questionnaire.md`.
