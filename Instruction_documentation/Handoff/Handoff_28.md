# Handoff_28.md

Date/time (ISO 8601 with offset): 2026-10-19T14:00+02:00 (renumbered 2026-10-22)
Author/agent: Claude Code (claude-opus-5-5)
Project: Ridge
Branch: `m5-missing-engine-13` → `main`
Base commit: `3c765dd` (Merge pull request #25, Handoff_26); `main` merged in at `6b79307` (Merge pull request #27, Handoff_27)
Latest commit: see the pull request

This handoff was written as Handoff_27 on this branch. PR #27 (print area) merged its own Handoff_27 into `main` first, so this one became Handoff_28 when `main` was merged in; Handoff_27 is unchanged.

## 1. Scope

Requested change: report a missing processing engine accurately instead of telling the examiner to "Restart Ridge" (product owner, 2026-10-19).

What happened: the GUI was started from `gui/src-tauri/target/release/deps/ridge_gui.exe`, a cargo hard-link copy of `target/release/ridge-gui.exe`. A release build looks for the engine only at `<resource dir>/sidecar/ridge-sidecar.exe`; next to `deps/` there is none, so the start failed with `NotFound`. The start screen then showed "The processing engine is not available: the processing engine could not be started. Restart Ridge; if this persists, report it." Restarting cannot fix a missing file. The engine itself was fine: `target/release/sidecar/ridge-sidecar.exe` answered `ridge.version` (0.2.0, `ridge.sidecar/1`, commit `253f4bd`).

Completed work:

- `Sidecar::ensure_started`: a launch that fails with `io::ErrorKind::NotFound` gives `Unavailable` "the processing engine is missing from this installation; reinstall Ridge" (`MISSING`); every other launch error keeps "the processing engine could not be started". The path is not included: IPC errors carry no internal paths (`desktop_gui_tauri_standards.md` §8, `error.rs`).
- The sidecar remembers whether its last launch found no file (`missing`). Once the starts are used up (`MAX_STARTS`), it still reports the missing engine instead of "stopped too often; restart Ridge and report the problem". A successful launch clears it. This was the Codex finding on PR #26 (P2): with startup and store calls, four failed launches are quickly reached, and the next call gave restart advice for the same missing file. Fixed in the second commit of the pull request.
- New `sidecar::launch(program: Option<&Path>)`, moved out of the closure in `lib.rs::run()`. It returns `NotFound` when `locate` gave no path (release build without a resource dir) or when nothing is a file at that path (missing file, or a directory). Before, the no-path case was `io::Error::other`, and was reported as a failed start.
- Start screen (`StoreScreen.tsx`): the sentence after the core's message is chosen by `engineAdvice`. When the core asks for a reinstall, the notice ends "If this persists after reinstalling, report it." instead of "Restart Ridge; …". All other engine problems keep "Restart Ridge; if this persists, report it." This follows the existing practice of reading a core message by a fixed phrase (`ipc/commands.ts`, "no case is unlocked").

The examiner now sees, for a missing engine: "The processing engine is not available: the processing engine is missing from this installation; reinstall Ridge. If this persists after reinstalling, report it."

Unchanged: how the engine is located (`sidecar::locate`): the bundle's resource dir in release builds, the compile-time development virtualenv in debug builds; never `PATH`, the working directory, configuration or user input. Spawning, the scrubbed environment, the bounded restarts (`MAX_STARTS`; a failed launch still counts as a start), the version check and all other messages.

Out of scope:

- Making a copy in `target/release/deps/` work. It is a build intermediate, not an installation; examiners run the installed application.
- The duplicated advice in two other start-screen cases ("…stopped too often; restart Ridge and report the problem. Restart Ridge; …" and "internal state error; restart Ridge. Restart Ridge; …"). The first cannot occur at the start screen (it needs four failed starts); the second is pre-existing. Not changed.

## 2. Current repository state

- This branch adds the four source changes below and this handoff as PR #26 against `main` (product owner, 2026-10-19): `9a347c0`, the review fix `00a28ba`, then a merge of `main` at `6b79307` (PR #27). Not merged into `main`.
- The merge of `main` conflicted only on `Instruction_documentation/Handoff/Handoff_27.md` (both branches added one). Resolved by keeping `main`'s Handoff_27 and renaming this one; no source file conflicted. PR #27 changed none of this branch's files.
- A `.venv/` (git-ignored) was created in the worktree from `requirements.lock` and `requirements-dev.lock` (hash-checked) plus `pip install -e .`, so that the gate's mandatory live sidecar test can find `.venv/Scripts/ridge-sidecar.exe`.

## 3. Standards applicability and evidence

Project standards profile updated: not needed.

| Standard/control/rule | Applies? | Evidence produced | Exception/deviation |
| --- | --- | --- | --- |
| `desktop_gui_tauri_standards.md` §2 (engine located from the bundle only) | Yes | `locate` unchanged; `launch` only checks that the located path is a file before spawning it | None |
| `desktop_gui_tauri_standards.md` §8 (typed IPC errors, no internal paths) | Yes | The new message has no path; the `io::Error` text is dropped as before | None |
| `desktop_gui_tauri_standards.md` §9, WCAG 2.2 "clear error messages" | Yes | The notice names the actual next step (reinstall), with no contradicting advice | None |
| `coding_standards.md` (entrypoints small, files around 300 lines) | Yes | The `run()` closure shrank to one line | `sidecar.rs` is 692 lines (603 before; about 345 of code, the rest tests) and `StoreScreen.tsx` 304 lines (297 before). Pre-existing; a split of `sidecar.rs` is recommended in §12 |
| `testing_and_codex_quality_gates.md` | Yes | Tests in §9, full gate run | See §9 |

Exceptions, deviations or evidence gaps:

- File sizes as above.

Steps outside coding work: none.

## 4. Forensic impact

Output pixels changed: no.

Defaults or recorded parameters changed: no.

Revalidation decision required / recorded: not required: no processing, report or custody change.

Examiner-facing wording changed (checked against forbidden claims): yes, one engine-problem message and the start-screen advice that follows it. No identification, match, validation or certification wording.

Data classes touched: none. No images, case data or examiner data were opened or created; tests use fake transports and temporary paths only.

## 5. Files changed

| File | Purpose of change |
| --- | --- |
| `gui/src-tauri/src/sidecar.rs` | `MISSING` and the `missing` flag (classify launch errors, also after the starts are used up), `launch` (no path or no file is `NotFound`), two unit tests |
| `gui/src-tauri/src/lib.rs` | The launch closure calls `sidecar::launch` |
| `gui/src/screens/StoreScreen.tsx` | `engineAdvice`: no "Restart Ridge" next to "reinstall Ridge" |
| `gui/src/test/screens.test.tsx` | Full notice text for the failed start; new test for the missing engine |
| `Instruction_documentation/Handoff/Handoff_28.md` | This handoff |

## 6. Data store, records and formats

- No case-store, custody-log, report or export format changes. No write paths added or changed.

## 7. Configuration, keys and CI

- No configuration keys, `RIDGE_*` variables, key custody, signing or CI changes.

## 8. Security

Decoder, limit or allow-list changes: none.

Trust-boundary changes: none. The WebView still learns only the error kind and a fixed message. The added `is_file` check reads only the path `locate` produced.

Threat-model notes: `NotFound` from `spawn` itself (after the `is_file` check) can also mean a missing interpreter for a script entry point (the development virtualenv on Linux and macOS); it is reported as a missing engine too, which is accurate for that installation.

Open security risks: none added.

## 9. Tests

Tests added or updated:

- Rust `a_missing_engine_asks_for_a_reinstall_every_time`: `MAX_STARTS + 1` calls with a launch closure returning `NotFound` all give the reinstall message, including the call after the starts are used up. With `PermissionDenied`, the first `MAX_STARTS` give "could not be started" and the last "stopped too often". Both make exactly `MAX_STARTS` launches.
- Rust `no_engine_file_is_not_found`: `launch(None)`, a path that does not exist and a directory all return `NotFound` without spawning anything.
- Vitest "asks for a reinstall, not a restart, when the engine is missing" (full notice text, no "Restart Ridge"); the failed-start test now checks the full "Restart Ridge; if this persists, report it." sentence.

Commands run:

`python tools/gate.py all` in this worktree (Windows 11 x86-64, Python 3.13.5, worktree `.venv`), on the four source changes:

```
=== all 11 gate(s) passed: docs, lint, format, typecheck, test, sast, deps, secrets, licenses, sbom, gui
```

- pytest: 777 passed, 3 skipped, branch coverage 97.51%.
- Vitest: 26 files, 96 tests passed (95 before).
- Rust: 36 passed (34 before), including `the_real_sidecar_answers_over_stdio` (made mandatory by the gate) and the two new tests.
- `cargo fmt --check` and `cargo clippy --all-targets -D warnings` clean.

That run started before this handoff was written. After writing it, `python tools/gate.py docs` was run again and passed (`=== all 1 gate(s) passed: docs`).

After the review fix, `python tools/gate.py all` was run again in the same worktree:

```
=== all 11 gate(s) passed: docs, lint, format, typecheck, test, sast, deps, secrets, licenses, sbom, gui
```

pytest 777 passed, 3 skipped, coverage 97.51%; Vitest 96 passed; Rust 36 passed, including `a_missing_engine_asks_for_a_reinstall_every_time` and the live sidecar test. Only this paragraph was added afterwards; the docs gate was re-run on it.

Determinism and golden results: not affected; `tests/golden/` untouched.

Tests not run and why: the change was not exercised in a built release bundle (an installed build with its engine removed); the unit tests cover the classification and the notice.

Required tests still missing: none for this change.

## 10. Release readiness

Release type: internal build.

Ready: in review as a pull request; merge only on green CI.

Blockers: none for this change. Code signing and the other items in Handoff_26 §10 remain.

Rollback or mitigation: revert the four source files; no data or format depends on them.

## 11. Open risks and known issues

- `sidecar.rs` exceeds the file-size guideline (pre-existing).

## 12. Recommended next work

1. Answer and resolve the review threads on the pull request; merge on green CI.
2. Split `sidecar.rs`: the process transport (`spawn`, `ChildTransport`, `launch`, `locate`) apart from the `Sidecar` restart and protocol logic, and move the tests with them.
3. Optionally: let the core's start messages carry their own next step everywhere, so the start screen stops appending advice (removes the two duplicated cases in §1).

## 13. First thing the next agent/developer should read or do

Read this handoff and the pull request. Launch the GUI only from an installed build or `npx tauri dev`, not from `target/release/deps/`.
