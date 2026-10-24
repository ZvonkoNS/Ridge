# Handoff_51.md

Date/time (ISO 8601 with offset): 2026-10-24T22:00+02:00
Author/agent: Claude Code (claude-fable-5-1), end-user review follow-up: research mode and the grayscale default (ADR-015)
Project: Ridge
Branch: `afis-research-mode-33` (stacked on `afis-capture-check-32`; local commit only, nothing pushed)
Base commit: `4ddbb40` (tip of `afis-capture-check-32`, Handoff_50)
Latest commit: see `git log afis-research-mode-33`

## 1. Scope

Requested change: from the end-user review, the examiner's and investigator's shared complaint that the method variants are engineering on screen, and the examiner's wish for the grayscale image as the primary comparison export and for plainer words about NFIQ 2.

Completed work:

- **Research mode (ADR-015, proposed).** The review panel has a "Research mode" switch, off by default and per session, with the note that it shows the unvalidated ADR-014 variants, that switching it off puts every variant back to its default, and that it is for research and the validation study, not for casework. `ParametersForm` takes `research` and renders the `MethodVariants` fieldset only when it is on; `withoutVariants(params)` resets the five variant fields when it is switched off, so a job can never carry a variant the examiner cannot see. The CLI keeps its flags under their unvalidated labels; every report records the variants a job used either way.
- **Grayscale as the default comparison image.** The GUI already showed and exported the grayscale export first; `ridge-case export-all` now exports `export-gray` by default (`--role export` for the binary ones), and the case summary names grayscale exports (the `export-gray` role was missing from its labels). PRD FR-37 records the default.
- **NFIQ 2 words.** The examiner guide says what an NFIQ 2 score on a photograph is worth: a weak hint about the image, not a statement about the photograph, the finger or a search; the report's existing "indicative only" label is unchanged.
- ADR-015 row in the architecture's ADR table (Proposed); PRD FR-37 and FR-44 amendments; CHANGELOG; README; examiner guide ("Research mode", "What an NFIQ 2 score is worth here", and the variants line of "Jobs and review").

Out of scope: a role or permission model for research mode (Ridge has one identity per examiner; the switch is a session setting, not an authorisation); removing the variants from the CLI.

## 2. Current repository state

Git status summary: committed on `afis-research-mode-33`.

Recent commits: `4ddbb40` (Handoff_50) and the stack below.

## 3. Standards applicability and evidence

Project standards profile updated: not needed (ADR-014's exception row covers the variants; ADR-015 changes where they are shown, not what they do).

| Standard/control/rule | Applies? | Evidence produced | Exception/deviation |
| --- | --- | --- | --- |
| Forensic UI rules (all parameters used for an output are visible and match the report) | Yes | Leaving research mode resets the variants, so the hidden fieldset never holds an active setting; the job summary still names any variant a report records | None |
| ADR discipline (defaults changed by a recorded decision) | Yes | ADR-015 row; PRD FR-37 and FR-44 amended | ADR-015 is proposed, awaiting the owner |
| WebView holds no security logic | Yes | The switch is display state; the sidecar and Rust validate the options as before | None |

Standards checks or tools run: section 9.

Exceptions, deviations or evidence gaps: none.

Steps outside coding work: the owner accepts or amends ADR-015.

## 4. Forensic impact

Output pixels changed: no.

Defaults or recorded parameters changed: the default role of `ridge-case export-all` is now `export-gray` (the GUI's default was already the grayscale export). No recorded field changed; the exported file's role and hash are in the export index as before.

Revalidation decision required / recorded: not applicable.

Examiner-facing wording changed (checked against forbidden claims): "Research mode" and its note; "binary comparison export(s)" and "grayscale comparison export(s)" in the case summary; the guide's NFIQ 2 paragraph. No identification or validation claim.

Data classes touched: none.

## 5. Files changed

| File | Purpose of change |
| --- | --- |
| `gui/src/screens/ParametersForm.tsx`, `gui/src/screens/MethodVariants.tsx`, `gui/src/screens/ReviewPanel.tsx` | `research` prop, `withoutVariants`, `RESEARCH_NOTE`, the switch |
| `gui/src/screens/CaseSummary.tsx` | Role labels |
| `src/ridge/case/cli.py` | `export-all --role` default |
| `gui/src/test/research.test.tsx` (new), `tests/test_export_all.py` | Tests (section 9) |
| `docs/prd.md`, `docs/architecture.md`, `CHANGELOG.md`, `README.md`, `docs/examiner_guide.md` | ADR-015, requirements, changelog, usage, guide |
| `Instruction_documentation/Handoff/Handoff_51.md` (new) | This handoff |

## 6. Data store, records and formats

None.

## 7. Configuration, keys and CI

None.

## 8. Security

No change to any trust boundary.

## 9. Tests

Tests added or updated:

- `gui/src/test/research.test.tsx` (new): the variants fieldset is absent without research mode and present with it; `withoutVariants` resets the five variant fields and keeps the other settings.
- `tests/test_export_all.py`: `export-all` without `--role` writes the grayscale exports (the index lists only `export-gray`).

Commands run:

```bash
.venv/Scripts/python.exe -m ruff check src tests tools && .venv/Scripts/python.exe -m ruff format --check src tests tools   # clean
.venv/Scripts/python.exe -m mypy                                                        # Success: no issues found in 201 source files
.venv/Scripts/python.exe -m pytest tests/test_export_all.py -q                          # 7 passed
cd gui && npm run lint && npm run typecheck && npx prettier --check . && npm test -- --run   # 35 files, 127 tests passed; prettier clean
.venv/Scripts/python.exe tools/gate.py docs   # pass
```

Determinism and golden results: unaffected.

Tests not run and why: the full `gate.py all` (stack top, at the end of this run); the Rust crate is unchanged on this branch; Tauri WebDriver E2E (profile exception).

Required tests still missing: none.

## 10. Release readiness

Release type: internal build. Ready: as part of the stack. Blockers: none. Rollback: revert the commit.

## 11. Open risks and known issues

- Research mode is a session switch, not an authorisation: any examiner can turn it on. If the laboratory wants it restricted, that needs a store-level setting under the FQM's key (a follow-up, not started).

## 12. Recommended next work

Examiner annotations as signed custody entries with an annotated-print export (next branch), then linked zoom and pan between the original and the output with the marking tool.

## 13. First thing the next agent/developer should read or do

`gui/src/screens/ReviewPanel.tsx` (the switch) and ADR-015's row in `docs/architecture.md`.
