# Handoff_50.md

Date/time (ISO 8601 with offset): 2026-10-24T21:10+02:00
Author/agent: Claude Code (claude-fable-5-1), end-user review follow-up (investigator's item): the capture check
Project: Ridge
Branch: `afis-capture-check-32` (stacked on `afis-docs-31`; local commit only, nothing pushed)
Base commit: `d4e5af5` (tip of `afis-docs-31`, Handoff_49)
Latest commit: see `git log afis-capture-check-32`

## 1. Scope

Requested change: the product owner asked for the suggestions of the end-user review (an examiner and an investigator) to be implemented under the instruction documentation. This branch is the investigator's item: a verdict at the time it matters, while the finger is still in front of the camera.

Completed work:

- **Capture check (PRD FR-54, `ridge.capture`).** `check_bytes` / `check_file` decode a photo once (hashed and decoded from the same bytes, bounded by `ReadLimits`) and measure what the pipeline will see: whether skin colour locates a finger and its share of the frame (`MIN_FINGER_SHARE` 10 %), the pixels per ridge from the global spacing estimate (`MIN_PIXELS_PER_RIDGE` 6), the clarity as the median spectral peak share of the finger's patches (`MIN_CLARITY` 0.02, provisional: synthetic sharp fingers read 0.05, fingers blurred by 5 px 0.005), the share of the finger under specular highlights (`MAX_GLARE_SHARE` 5 %), and the file's provenance hints (editing or copy marks, an estimated JPEG quality under 80, no camera metadata). Each finding is `ok`, `retake` or `note`; a fixed note says the check cannot see a scale reference. `verdict` is "retake" when any finding asks for one. The record (`ridge.capture-check/1`) and the text both carry the notice that this is not a quality score and says nothing about identification. A failure to measure the spacing becomes a finding instead of an error; a refused file (not an image, too large) still raises `InputError`.
- **Entry points.** CLI `ridge-case check-photo FILE [--json]` (no case, read-only) and `ridge-case check-photo --case CASE SHA` (a stored evidence or reference image, one logged `evidence.read`/`reference.read`; outputs refused), in `ridge.case.cli_check` with `ridge.case.capture_check.check_stored_photo`. Sidecar `photo.check` (absolute path from the Rust dialog, no case needed) and `evidence.check` (`sha256`). Rust `check_photo` (native image dialog) and `check_evidence`, registered in the allow-list, `generate_handler!` and the main capability. GUI `CaptureCheckCard`: "Check a photo..." in the evidence pane when no photo is chosen, and "Capture check of this photo" under each chosen photo, with the findings as OK/Retake/Note badges, the measured values in one line and the notice.
- Docs: PRD FR-54; architecture module list and sidecar method table; CHANGELOG; README; examiner guide ("Capture check"); capture guidance section 9.

Out of scope: detecting a ruler or card in the photo (the check reminds instead); the examiner's items of the review (research mode, annotations, linked views), which follow on their own branches.

## 2. Current repository state

Git status summary: committed on `afis-capture-check-32`.

Recent commits: `d4e5af5` (Handoff_49) and the stack below.

## 3. Standards applicability and evidence

Project standards profile updated: not needed.

| Standard/control/rule | Applies? | Evidence produced | Exception/deviation |
| --- | --- | --- | --- |
| Safe file handling (read once, bounded, hash and decode the same bytes; originals read-only) | Yes | `check_file` uses `read_bounded` + `decode_image` on one buffer; the test asserts the file's mtime is unchanged | None |
| Trust boundaries (paths only from the Rust dialog; schema-checked params; GUI displays only) | Yes | `absolute()` on the sidecar path; `-32602` tests for extra or mistyped params; Rust `deny_unknown_fields` and `validate::sha256` | None |
| Forensic wording (no quality score, no identification claim) | Yes | `NOTICE` in the record, the text, the GUI and the docs; the verdict wording "no reason to photograph again was found" | None |
| Logged reads of stored class E data | Yes | `check_stored_photo` reads through `case.read` (logged); the CLI test counts the entry | None |
| Determinism | Yes | Pure measurement on decoded bytes; no randomness | None |

Standards checks or tools run: section 9.

Exceptions, deviations or evidence gaps: the thresholds are provisional and set on synthetic fingers (stated in the PRD, the code and the guide).

Steps outside coding work: the pilot adjusts the thresholds on real photographs.

## 4. Forensic impact

Output pixels changed: no.

Defaults or recorded parameters changed: none; the check produces no stored record (its stored-photo form is a logged read like `metadata.get`).

Revalidation decision required / recorded: not applicable.

Examiner-facing wording changed (checked against forbidden claims): the finding texts, "Photograph the finger again if you still can.", "No reason to photograph the finger again was found.", and the notice; no identification or quality claim.

Data classes touched: synthetic only.

## 5. Files changed

| File | Purpose of change |
| --- | --- |
| `src/ridge/capture.py` (new) | The check, its thresholds, record and text |
| `src/ridge/case/capture_check.py` (new), `src/ridge/case/cli_check.py` (new), `src/ridge/case/cli.py` | Stored-photo check with a logged read; `ridge-case check-photo` |
| `src/ridge/sidecar/store_methods.py`, `src/ridge/sidecar/case_methods.py`, `src/ridge/sidecar/handlers.py` | `photo.check`, `evidence.check` |
| `gui/src-tauri/src/commands/check.rs` (new), `commands/mod.rs`, `commands/list.rs`, `src/lib.rs`, `capabilities/main.json` | `check_photo`, `check_evidence` |
| `gui/src/components/CaptureCheckCard.tsx` (new), `gui/src/screens/EvidenceSection.tsx`, `gui/src/ipc/types.ts`, `gui/src/ipc/commands.ts`, `gui/src/dev/preview.ts` | The card, its placement, types, calls, preview mocks |
| `tests/test_capture.py` (new), `tests/test_capture_cli.py` (new), `gui/src/test/capture.test.tsx` (new) | Tests (section 9) |
| `docs/prd.md`, `docs/architecture.md`, `CHANGELOG.md`, `README.md`, `docs/examiner_guide.md`, `docs/capture_guidance.md` | Requirements, design, changelog, usage, guides |
| `Instruction_documentation/Handoff/Handoff_50.md` (new) | This handoff |

## 6. Data store, records and formats

No stored record. The check's JSON (`ridge.capture-check/1`) is returned to the caller only.

## 7. Configuration, keys and CI

None.

## 8. Security

One new read path for a file chosen in the native dialog (the same bounds and decoder as import) and one new logged read of a stored photo; two new allow-listed commands and sidecar methods with strict schemas. No write, no network, no new trust boundary.

## 9. Tests

Tests added or updated:

- `tests/test_capture.py` (new): a sharp located finger gives no reason to retake (located, spacing, clarity, no glare OK; copy, no-camera-data and scale notes; hash and size); blur, glare, a small finger and a coarse photo give their findings; an unlocated finger and a recompressed JPEG are named; the record, the text and the read-only file path; refused input raises.
- `tests/test_capture_cli.py` (new): the CLI on a file (text and JSON), on a stored photo with one more logged read and a refused unknown item; the sidecar before any case is unlocked, with a relative path refused, extra and mistyped params refused, and on a stored photo after unlock.
- `gui/src/test/capture.test.tsx` (new): the card before import lists the findings with their levels, the measured line and the notice (axe clean); a stored photo is checked by its hash; a cancelled dialog is silent; the measured line for an unlocated finger.

Commands run:

```bash
.venv/Scripts/python.exe -m ruff check src tests tools && .venv/Scripts/python.exe -m ruff format --check src tests tools   # clean
.venv/Scripts/python.exe -m mypy                                                        # Success: no issues found in 201 source files
.venv/Scripts/python.exe -m pytest tests/test_capture.py -q                             # 5 passed
.venv/Scripts/python.exe -m pytest tests/test_capture_cli.py tests/test_sidecar.py -q   # 33 passed (after two test fixes)
.venv/Scripts/python.exe -m pytest tests/test_case_cli.py tests/test_sidecar_gui_methods.py -q   # 34 passed in 67 s
cd gui && npm run lint && npm run typecheck && npx prettier --check . && npm test -- --run   # 34 files, 125 tests passed
cd gui/src-tauri && cargo fmt --check && cargo clippy --locked --all-targets -- -D warnings && cargo test --locked   # pass, 36 tests
.venv/Scripts/python.exe tools/gate.py docs   # pass
```

Determinism and golden results: unaffected (no pipeline change).

Tests not run and why: the full `gate.py all` (stack top, at the end of this run); Tauri WebDriver E2E (profile exception).

Required tests still missing: threshold calibration on real photographs (pilot).

## 10. Release readiness

Release type: internal build. Ready: as part of the stack. Blockers: none. Rollback: revert the commit.

## 11. Open risks and known issues

- The clarity threshold measures a synthetic cosine pattern's spectral peak; real skin, pores and creases spread the spectrum, so real photographs may read lower and the threshold may need lowering. The check says it is provisional.
- The check cannot see a scale reference; it reminds instead. A detector for a ruler or an ID-1 card would be a new, separate feature.

## 12. Recommended next work

The examiner's items of the review: research mode for the variants with the grayscale export as the default comparison image, examiner annotations as signed custody entries with an annotated-print export, and linked zoom and pan between the original and the output with the marking tool.

## 13. First thing the next agent/developer should read or do

`src/ridge/capture.py` and `docs/capture_guidance.md` section 9.
