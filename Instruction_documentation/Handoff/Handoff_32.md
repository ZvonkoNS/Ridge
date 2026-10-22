# Handoff_32.md

Date/time (ISO 8601 with offset): 2026-10-23T01:30+02:00
Author/agent: Claude Code (claude-opus-5-5), autonomous window granted by the product owner on 2026-10-22
Project: Ridge
Branch: `m5-terminal-16`, stacked on `m5-deps-15` (Handoff_31)
Base commit: tip of `m5-deps-15`
Latest commit: see the pull request

## 1. Scope

Requested change: the follow-ups Handoff_29 left open (section 11 and 12, items 3 and 4) and that the review of 2026-10-22 widened:

1. `ridge-case list` showed bidirectional and zero-width characters in stored labels and source notes as they were. The review found the same gap wherever a command printed text without `printable`: `ridge-case import` and `import-reference` print the input path; the R&D `ridge` command printed file names and its warnings unfiltered; `ridge-case` errors quote paths (`OSError.filename`, "… is not a Ridge store folder").
2. The stray fragment line at the end of `docs/architecture.md` §10 item 7.
3. The role check that `ridge-case metadata` and the sidecar's `metadata.get` both repeated.
4. Found on the way: `docs/architecture.md` §9.1 described the decompression-bomb guard as escalating Pillow's warning and setting `Image.MAX_IMAGE_PIXELS`. The code does neither (section 3).

Completed work:

- New `src/ridge/terminal.py` (51 lines, a leaf module): `HIDDEN_RANGES` (moved unchanged from `ridge.metadata.values`), `reveal(value)` (every hidden or control character as `<U+XXXX>`) and `safe(value)` (the same, keeping line breaks and tabs; a carriage return is shown, since it could overwrite the line).
- Every terminal write of the three command-line tools goes through `safe`:
  - `ridge-case`: `cli_common.say` (stdout) and the new `cli_common.warn` (stderr); `cli.py`'s error handlers and `PROBLEM:` lines, `cli_extract.py` and `cli_records.py` use `warn` instead of `print(..., file=sys.stderr)`. With `--verbose`, the traceback of an internal error goes through `warn` too.
  - `ridge` (`src/ridge/cli.py`): `_warn` and the per-file result line.
  - `ridge-validate`: its error line. Its JSON output is ASCII-only already (`json.dumps` default).
- `ridge.metadata.values.text` uses `terminal.reveal`; its output is unchanged.
- New `src/ridge/case/photo_metadata.py` (`PHOTO_ROLES`, `read_photo_metadata`), used by `cli_metadata.py` and `sidecar/case_methods.py::photo_metadata`. Same refusal message and the same logged read as before.
- `docs/architecture.md`: §6 lists `terminal.py` with its dependency rule and `photo_metadata`; §9.1 decompression-bomb row describes what the code does; §10 stray line removed.
- `Project_Standards_Profile.md` §8: a row recording the deviation from `coding_standards.md` ("Warnings that indicate risk (for example Pillow DecompressionBombWarning) are turned into errors").
- CHANGELOG: terminal output, and the PR #26 start-screen message, which had no entry.

Out of scope: GUI rendering (React text nodes; the WebView is a separate trust domain); the sidecar's JSON-RPC output (not a terminal); log records (`logging` has no handler configured in the CLIs).

## 2. Current repository state

Git status summary: committed on `m5-terminal-16`.

Recent commits: the terminal-output change, the bomb-guard documentation correction, then this handoff.

## 3. Standards applicability and evidence

Project standards profile updated: yes (one deviation row, section 1 item 4).

| Standard/control/rule | Applies? | Evidence produced | Exception/deviation |
| --- | --- | --- | --- |
| CWE-150 (terminal escape injection), CVE-2021-42574 (Trojan Source); coding standard "Neutralise control characters in any untrusted string written to a terminal or log" | Yes | `tests/test_terminal.py` (6 tests): every range boundary, layout kept, `say`/`warn`, `ridge-case import` and `list` with U+202E and U+200B in the file name and source note, a `ridge-case cases` error quoting a path with U+202E, the R&D CLI with U+202E in an input name and U+200B in a missing one | None |
| Output encoding for context (coding standard) | Yes | One sink per tool; `printable` still used for the HTML copies | None |
| FR-36 behaviour of `metadata` and `metadata.get` unchanged | Yes | `tests/test_metadata_cli.py`, `tests/test_sidecar_gui_methods.py` unchanged and passing | None |
| Coding standard, Errors: bomb warnings escalated | Yes | Profile row with reason, risk and compensating controls | Recorded deviation, pending Security Owner |
| Docs match behaviour (release blocker) | Yes | §9.1 corrected; §6 updated | None |

Exceptions, deviations or evidence gaps: the bomb-warning row above.

## 4. Forensic impact

Output pixels changed: no. No pipeline, decoder, report, custody or export code changed.

Defaults or recorded parameters changed: no.

Examiner-facing wording changed: terminal lines that contained hidden characters now show them as `<U+XXXX>` (previously `printable` showed control characters as `?` in some places, and nothing was shown in others). No identification, match or validation wording.

Data classes touched: synthetic images only (`tests/golden_cases.py` photos written to pytest temporary folders).

## 5. Files changed

| File | Purpose of change |
| --- | --- |
| `src/ridge/terminal.py` (new) | Display-safe text for terminals |
| `src/ridge/case/cli_common.py` | `say` filters; new `warn` |
| `src/ridge/case/cli.py`, `cli_extract.py`, `cli_records.py` | stderr through `warn` |
| `src/ridge/cli.py`, `src/ridge/validation/report.py` | Output through `safe` |
| `src/ridge/metadata/values.py` | Uses `terminal.reveal` (ranges moved) |
| `src/ridge/case/photo_metadata.py` (new), `cli_metadata.py`, `src/ridge/sidecar/case_methods.py` | Shared role check and read |
| `tests/test_terminal.py` (new) | Six tests (section 3) |
| `docs/architecture.md` | §6, §9.1, §10 |
| `Instruction_documentation/Project_Standards_Profile.md` | Deviation row |
| `CHANGELOG.md` | Entries |
| `Instruction_documentation/Handoff/Handoff_32.md` (new) | This handoff |

## 6. Data store, records and formats

None.

## 7. Configuration, keys and CI

None.

## 8. Security

Closes the CWE-150 / Trojan Source gap in all command-line output (Handoff_29 section 11). Threat note: file names of evidence received from third parties, source notes, metadata values and messages that quote them are attacker-controlled; on Linux and macOS a file name can contain ESC, so an unfiltered line could drive the examiner's terminal; on every platform a bidirectional override can make a displayed name read differently from the stored one.

## 9. Tests

GATE_RESULTS

## 10. Release readiness

Internal engineering build. Rollback: revert the two commits; nothing is stored or migrated.

## 11. Open risks and known issues

- The `--verbose` traceback is filtered, but Python's own last-resort handler (an exception before `main` catches it) is not; that path prints only Ridge's code locations.
- `printable` (used for HTML copies and some messages) still maps only control characters to `?`. The HTML copies are escaped and script-free; bidirectional marks in them display as in any browser. A follow-up could use `terminal.reveal` there too, which changes readable-copy wording.

## 12. Recommended next work

1. Security Owner: review the bomb-warning deviation row in the profile.
2. Consider `terminal.reveal` for labels in the HTML readable copies (wording change, needs owner agreement).

## 13. First thing the next agent/developer should read or do

Read this handoff and `src/ridge/terminal.py`; then Handoff_33 (refactoring), stacked on this branch.
