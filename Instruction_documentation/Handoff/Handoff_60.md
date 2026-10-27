# Handoff_60.md

Date/time (ISO 8601 with offset): 2026-10-26T17:16+01:00
Author/agent: Claude Code (claude-fable-5-1)
Project: Ridge
Branch: `main` (working tree; nothing committed, per the owner's standing instruction)
Base commit: `22b681b` (Handoff_59)
Latest commit: `22b681b` (no commit in this handoff)

## 1. Scope

Requested change: the owner asked whether photos that hold a usable print can be marked without AI, then asked for "the read-only folder triage command on the capture check, with a sorted CSV index and the indicative-only wording", and then for a GUI element for it.

Completed work:

- `ridge-case triage FOLDER [--to INDEX.csv] [--recursive] [--max-files N] [--json]` (PRD FR-57, new): runs the capture check (FR-54) on every file of a folder that has an allow-listed image extension, each read once and read-only through `read_bounded` and the allow-listed decoder, and lists the files in a reading order: `finger-ridges` (skin colour located a finger and its patches show a clear ridge wave), `ridges-no-finger` (a clear ridge-like wave, no finger located: a finger in grey or odd light, or a texture), `finger-unclear`, `nothing`, `refused`; within a group the clearer wave first, then the relative name. No trained model: the grouping is the capture check's own "located" and "clarity" findings.
- A CSV index (`COLUMNS` in `src/ridge/triage.py`: order, group, relative POSIX name, bytes, SHA-256, size in pixels, finger located and share, ridge spacing, clarity, glare share, the check's verdict and findings, or the reason a file was refused), written only on request, as a new `.csv` outside the scanned folder through `publish` (atomic, never replacing a file); its SHA-256 is reported. The destination is checked before the long read and again before writing (`run_triage`).
- A JSON record `ridge.triage/1`: version, folder, counts, group legend, the capture check's thresholds, every row with its capture-check record, the notice; with an index, its path and hash.
- Sidecar method `folder.triage` (`path`, optional `recursive`, `max_files`, `dest`; `src/ridge/sidecar/store_methods.py`, schema in `handlers.py`), Tauri command `triage_folder` (`gui/src-tauri/src/commands/triage.rs`: the folder from a native folder dialog, the index from a native save dialog, `max_files` 300, timeout 45 min; registered in `list.rs`, `mod.rs`, `lib.rs` and granted in `capabilities/main.json`) and the store-screen card **Which photos first?** (`gui/src/screens/TriageFolder.tsx`: "Include subfolders", "Also save the index as a CSV file", the button, the summary with the groups and their counts, the index path and SHA-256, a table of every row, the notice; a refusal as an alert; a cancelled dialog shows nothing). The development preview (`gui/src/dev/preview.ts`) answers `triage_folder` with six invented file names.
- Subfolders only on request, never through a link; a link with an image extension, a non-image, a file over a limit, a corrupt file or an unreadable file becomes a `refused` row and never stops the run; other Ridge errors and bugs propagate to the CLI boundary as before (exit 1 or 3). A folder with no photos, a non-folder, or a folder above `--max-files` (default 1000, hard maximum 10 000; 300 from the GUI) is refused before any photo is read.
- Wording: every terminal output, the JSON record, the card and the README call the result a reading order for an examiner who still looks at every photo, name the groups by what was measured, and say nothing about usable prints or identification.
- Documentation: PRD FR-57 and risk R-14; architecture section 6 (module), section 7.3 (sidecar method) and section 9.1 (input-handling row); README (feature bullet, start-to-finish block, new section "Many photos: which to look at first", desktop section, photographing section); examiner guide section "Which photos first?"; CHANGELOG; write path P11 in `direct_mutation_authorization_audit.md`.

Out of scope (recommended next work, section 12): progress and cancellation during a long triage; a faster capture check; calibration of the thresholds; any change to pipeline numerics; signing the index or logging the reads in a custody log (the triage runs before import, with no case, like `check-photo FILE`).

## 2. Current repository state

Git status summary: uncommitted on `main`: `src/ridge/triage.py` (new), `src/ridge/case/cli_triage.py` (new), `tests/test_triage.py` (new), `src/ridge/case/cli.py`, `src/ridge/sidecar/store_methods.py`, `src/ridge/sidecar/handlers.py`, `gui/src-tauri/src/commands/triage.rs` (new), `gui/src-tauri/src/commands/{list,mod}.rs`, `gui/src-tauri/src/lib.rs`, `gui/src-tauri/capabilities/main.json`, `gui/src/screens/TriageFolder.tsx` (new), `gui/src/test/triage.test.tsx` (new), `gui/src/screens/StoreScreen.tsx`, `gui/src/ipc/{types,commands}.ts`, `gui/src/dev/preview.ts`, `gui/src/styles/app.css`, `docs/prd.md`, `docs/architecture.md`, `docs/examiner_guide.md`, `README.md`, `CHANGELOG.md`, `Instruction_documentation/direct_mutation_authorization_audit.md`, this handoff. No branch, no pull request: the owner decides whether this goes to a branch and PR (the usual flow) or is committed on `main`.

Recent commits: `22b681b` installers rebuilt (Handoff_59); `7353b0b` AFIS-readiness stack closed (Handoff_58).

## 3. Standards applicability and evidence

Project standards profile updated: not needed (no new exception; no new dependency, format, decoder, platform, store or process boundary; no new Tauri plugin).

| Standard/control/rule | Applies? | Evidence produced | Exception/deviation |
| --- | --- | --- | --- |
| Forensic rules section 1 (no identification, no ranking of candidates, no quality "pass"; forbidden claims) | Yes | The order ranks photos by a measurement, never candidates or sources; `NOTICE`, `GROUP_TEXT`, CLI help, card text, README and PRD wording reviewed against the forbidden-claims list; the Python and Vitest tests assert the notice on every output | None |
| Forensic rules sections 3 to 5 (originals read-only, bounded allow-listed decoding, every input and output hashed) | Yes | `read_bounded` + `check_bytes` (same bytes hashed and decoded); per-file SHA-256 in the index; the index's SHA-256 printed and shown; the test snapshots bytes and timestamps of every original before and after | None |
| No silent overwrite; outputs never in input folders (PRD FR-11; write-path audit) | Yes | `check_destination` (exists, `.csv`, existing parent, not inside the scanned folder by absolute or resolved path) + `publish`; audit row P11; tests for each refusal with nothing written; the sidecar test shows nothing written next to the photos | None |
| GUI standards section 3 (IPC allow-list; the WebView never sends a path; thin typed handlers with `deny_unknown_fields`) | Yes | `triage_folder` takes `{recursive, save_index}` only; folder and index come from native dialogs in the Rust core; the command is in `list.rs` (build-time permissions and capability) and `lib.rs`; clippy `-D warnings` clean | None |
| CWE-22, CWE-59, CWE-150, CWE-367, CWE-400/770 | Yes | Relative POSIX names only; links never followed (folders or files); `common.say` neutralises names on the terminal, React escapes them in the card; atomic publish; byte, pixel and file-count limits; a 45-minute sidecar timeout bounded by the GUI's 300-photo limit | None |
| EU AI Act applicability (PRD section 5, OQ-3) | Yes | No trained model added; deterministic signal processing only, so the existing assessment of the extraction stands; NFIQ 2 is not used by the triage | None |
| GDPR / LED (special-category data at scale) | Yes | The triage reads a whole folder of potential biometric material; the DPIA (OQ-16) should name this pre-import use. Step outside coding work, below | None |
| Coding standards (file and function sizes, mypy strict, ruff, docstrings, typed errors, no printing in library code; TypeScript strict, ESLint, Prettier; Rust fmt and clippy) | Yes | `triage.py` 295 lines, `cli_triage.py` 46 lines, `triage.rs` 59 lines, `TriageFolder.tsx` about 150 lines; handlers about 20 lines; gates in section 9 | None |
| Determinism (same input, version, parameters, OS and CPU architecture give identical output) | Yes | Platform-independent listing order; fixed number formatting; the test asserts identical index bytes from two runs | None |
| Testing rules (synthetic data only; malformed, oversized, hostile and refused inputs; GUI render, error and cancelled states; accessibility) | Yes | Synthetic fingers, a grey finger, a stripe texture, a plain frame, a non-image, an unreadable file, a link (when the account may create one); sidecar schema refusals; Vitest with axe | None |

Standards checks or tools run: section 9.

Exceptions, deviations or evidence gaps: none new.

Steps outside coding work (validation, DPIA, legal, owner approvals):

- DPO: add the pre-import folder triage to the DPIA (OQ-16): it processes every photo of a folder, including photos of people and places, to find fingers; nothing is stored except the index the examiner asks for.
- Forensic Quality Manager: the groups rest on the capture check's provisional thresholds (set on synthetic fingers); the pilot (OQ-6) should record how often each group is right, especially textures in `ridges-no-finger` and dark or unevenly lit skin that the colour gate does not locate.

## 4. Forensic impact

Output pixels changed: no (no pipeline code touched; goldens untouched).

Defaults or recorded parameters changed: none. The triage records the capture check's thresholds in its JSON record; it changes none of them.

Revalidation decision required / recorded: none required (no method change). The triage is a pre-import aid, like the capture check, and is labelled indicative.

Examiner-facing wording changed (checked against forbidden claims): new wording only. `NOTICE` ("a reading order for the examiner, who still looks at every photo ... says nothing about identification"), the group legend, the CLI help, the card text, the README and examiner-guide sections and PRD FR-57 avoid "usable", "no print", "score", "quality" as a judgement, "select" and "match". The card's badges carry no colour that could read as a verdict.

Data classes touched and how class E data stayed out of repository and agent session: only synthetic images, generated in `tests/synthetic.py` and in the test module, were used; the development preview invents file names and numbers only; nothing was committed; the index holds file names, measurements and hashes (class C), never pixels.

## 5. Files changed

| File | Purpose of change |
| --- | --- |
| `src/ridge/triage.py` (new) | Listing, per-file capture check, grouping and reading order, CSV index, destination checks, `run_triage`, JSON record, terminal text |
| `src/ridge/case/cli_triage.py` (new) | `ridge-case triage` command (thin handler) |
| `src/ridge/case/cli.py` | Registers the command |
| `src/ridge/sidecar/store_methods.py`, `src/ridge/sidecar/handlers.py` | Sidecar method `folder.triage` and its parameter schema |
| `tests/test_triage.py` (new) | Reading order and groups, index bytes and determinism, untouched originals, refused destinations and folders, record and text, unreadable file and link, CLI, sidecar |
| `gui/src-tauri/src/commands/triage.rs` (new), `commands/list.rs`, `commands/mod.rs`, `lib.rs`, `capabilities/main.json` | Tauri command `triage_folder`: folder dialog, optional save dialog, one sidecar call; allow-list, registration and the main window's grant |
| `gui/src/screens/TriageFolder.tsx` (new), `gui/src/screens/StoreScreen.tsx` | The card "Which photos first?" on the store screen |
| `gui/src/ipc/types.ts`, `gui/src/ipc/commands.ts` | `Triage`, `TriageRow`, `TriageGroup`; `ipc.triageFolder` |
| `gui/src/test/triage.test.tsx` (new) | Reading order, groups, notice, saved index, refusal, cancelled dialog, measured column, axe |
| `gui/src/dev/preview.ts` | Synthetic `triage_folder` answer for `npm run dev` |
| `gui/src/styles/app.css` | Scrolling row table |
| `docs/prd.md` | FR-57; risk R-14 |
| `docs/architecture.md` | Section 6 module list; section 7.3 sidecar method; section 9.1 input-handling row |
| `docs/examiner_guide.md` | Section "Which photos first?" |
| `README.md` | Feature bullet; start-to-finish example; "Many photos: which to look at first"; desktop section; photographing section |
| `CHANGELOG.md` | Unreleased entry |
| `Instruction_documentation/direct_mutation_authorization_audit.md` | Write path P11 |
| `Instruction_documentation/Handoff/Handoff_60.md` (new) | This handoff |

## 6. Data store, records and formats

Case-store, custody-log or report format changes (M1+): none. The triage runs without a case and writes no custody entry (the folder is not yet evidence); the same holds for `check-photo FILE`.

Migrations and recovery notes: none.

Run-record or export format changes: new record `ridge.triage/1` (JSON on `--json` and over the sidecar) and the CSV index (`COLUMNS`), both documented in PRD FR-57, architecture section 7.3 and the README. Neither is signed; the index's SHA-256 is printed and shown so the examiner can note it.

Write paths added or changed: P11 (the index) added to `direct_mutation_authorization_audit.md`; from the GUI the destination comes only from a native save dialog opened by the Rust core.

## 7. Configuration, keys and CI

New or changed configuration keys or `RIDGE_*` variables: none.

Key-custody or signing changes: none.

CI changes: none. The Tauri permission for `triage_folder` is generated by `build.rs` from `list.rs`, as for every command.

## 8. Security

Threat-model note: the folder and everything in it is untrusted. File names reach the terminal only through `common.say` (control and hidden characters shown as `<U+XXXX>`), the CSV through the `csv` module (quoted) and the card through React's escaping; names the file system could not decode are escaped so the index stays valid UTF-8. Links are never followed, whether to folders or files. Every file passes the same byte, pixel and format limits as any Ridge input, and the file count is capped before any read. The destination is validated twice (before the long read, before writing) and published atomically; nothing is ever written inside the scanned folder. One file's refusal never stops the run; non-Ridge exceptions still reach the CLI boundary as internal errors. The WebView sends two booleans; the Rust core opens the dialogs and sends absolute paths to the sidecar, which validates them again.

Performance observation (not changed here): one capture check costs about 3.4 s whatever the photo's size, because `estimate_period` and `ridge_signal_strength` each compute the same patch spectra in `ridge.pipeline.period._trusted_patches` (about 1.6 s each, FFTs over rescaled patches). A folder of 300 photos (the GUI's limit) therefore takes about 17 minutes with the sidecar busy and no progress shown; 1000 photos on the command line about an hour. A cache of the patch spectra inside one check would roughly halve this; it touches `src/ridge/pipeline/`, so it is its own behaviour-preserving change with determinism tests.

## 9. Tests

Targeted (main tree, 2026-10-26):

```bash
.venv/Scripts/python.exe -m ruff check src/ridge tests/test_triage.py            # All checks passed!
.venv/Scripts/python.exe -m mypy src/ridge/triage.py src/ridge/case/cli_triage.py src/ridge/sidecar/store_methods.py src/ridge/sidecar/handlers.py tests/test_triage.py   # no issues
.venv/Scripts/python.exe -m pytest tests/test_triage.py -q                       # 8 passed (about 80 s: the capture check costs about 3.4 s per synthetic photo)
.venv/Scripts/python.exe tools/gate.py docs                                      # all 1 gate(s) passed
# gui/ (PowerShell)
npm run lint        # exit 0
npm run typecheck   # exit 0
npx vitest run src/test/triage.test.tsx   # 4 passed
# gui/src-tauri (PowerShell)
cargo fmt --check                          # exit 0 (after cargo fmt)
cargo clippy --all-targets -- -D warnings  # exit 0
```

Manual check in the development preview (`npm run dev`, mocked core, synthetic names): the card renders on the store screen, the button lists six invented files in reading order with the groups, the saved-index line and the notice.

Full gates:

```bash
# Python gates, main tree, final code (background run; log kept in the session scratchpad)
.venv/Scripts/python.exe tools/gate.py docs lint format typecheck test sast deps secrets licenses sbom
# all 10 gate(s) passed: docs, lint, format, typecheck, test, sast, deps, secrets, licenses, sbom
# test: 1014 passed, 3 skipped in 996 s; branch coverage 97 %
# GUI gate (PowerShell), with the dev app stopped
.venv/Scripts/python.exe tools/gate.py gui
# all 1 gate(s) passed: gui (npm ci, lint, typecheck, prettier, vitest 41 files / 144 tests, build, npm audit,
# licences, preview absent from dist, cargo fmt, clippy, cargo test 36 passed with the live sidecar test,
# cargo audit, cargo deny, SBOMs)
```

Two earlier GUI gate runs failed and are recorded here because they changed the tree: the first stopped at `npm ci` with EPERM, because `npm run tauri dev` was running and held a rolldown native binding open, and it left `node_modules` half-deleted (repaired by stopping the app and running `npm ci --no-audit`; never run the GUI gate beside the dev app). The second failed the Rust test `each_window_is_granted_exactly_its_own_commands` because `gui/src-tauri/capabilities/main.json` did not yet grant `allow-triage-folder`; granted, and the third run passed.

Determinism and golden results: no pipeline change; `tests/test_characterization.py` runs inside the test gate.

Tests not run and why: the full matrix on Windows, Linux and macOS runners (runs on demand or for a release tag, per the owner's decision); Tauri WebDriver E2E (profile exception); the MSI install (administrator); the native dialogs of `triage_folder` (no automated test drives a native dialog, as for every other dialog command). The symlink assertions in `tests/test_triage.py` run only where the account may create links (the same rule as `tests/test_hardening.py`).

Required tests still missing: calibration of the groups on real photographs in the pilot (synthetic fingers only here).

## 10. Release readiness

Internal engineering build; not for casework (M5). No installer rebuilt: the installers under `installers/` predate this work.

## 11. Open risks and known issues

- Thresholds are the capture check's provisional ones (synthetic fingers): periodic textures (fabric, wood grain, corrugated card) land in `ridges-no-finger` by design, and skin that the colour gate does not locate (dark skin in dim light, coloured light, gloves) moves a finger from `finger-ridges` to `ridges-no-finger` or `nothing`. The order is therefore a reading order, never a filter; R-14 records the misuse risk.
- The triage's reads are not in any custody log and the index is not signed (pre-import, no case). If a laboratory wants the triage of a folder recorded, the index's SHA-256 and a note in the case are the current means.
- About 3.4 s per photo (section 8); in the GUI a 300-photo folder keeps the sidecar busy for about 17 minutes with a busy line but no progress or cancel.
- The DPIA does not yet name the pre-import triage (OQ-16).

## 12. Recommended next work

1. Progress and cancellation for the GUI triage (the sidecar checks one photo per request, or reports progress), so that a long folder does not block the sidecar silently.
2. A behaviour-preserving cache of the patch spectra in the capture check (own PR, pipeline area, determinism and golden tests).
3. Pilot calibration of the capture-check thresholds, with the triage groups counted per folder.
4. Optional: when a folder's photos are later imported into a case, record the triage index's hash as an examiner note.

## 13. First thing the next agent/developer should read or do

Read `src/ridge/triage.py`, `tests/test_triage.py` and `gui/src/screens/TriageFolder.tsx`, then PRD FR-57 and R-14. Confirm with the owner whether this work goes to a branch and pull request (the usual flow, `ridge-pr-workflow`) or stays on `main`. Nothing is committed.
