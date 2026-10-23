# Handoff_30.md

Date/time (ISO 8601 with offset): 2026-10-19T14:00+02:00 (renumbered 2026-10-22)
Author/agent: Claude Code (claude-opus-5-5)
Project: Ridge
Branch: `m5-missing-engine-13` → `main`
Base commit: `3c765dd` (Merge pull request #25, Handoff_26); `main` merged in at `6b79307` (Merge pull request #27, Handoff_27), then at `36e264a` (Merge pull request #28, Handoff_28 and Handoff_29)
Latest commit: see the pull request

This handoff was written as Handoff_27 on this branch. Other pull requests merged their handoffs into `main` first: PR #27 merged Handoff_27, then PR #28 (photo metadata) merged Handoff_28 and Handoff_29. Each time `main` was merged in, this handoff moved to the next free number (27 → 28 → 30). The handoffs from `main` are unchanged.

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

- This branch adds the four source changes below and this handoff as PR #26 against `main` (product owner, 2026-10-19): `9a347c0`, the review fix `00a28ba`, a merge of `main` at `6b79307` (PR #27), `11843da`, then a merge of `main` at `36e264a` (PR #28). Not merged into `main`.
- Both merges of `main` conflicted only on a handoff that both sides had added (Handoff_27, then Handoff_28). Each was resolved by keeping `main`'s file and renaming this one. No source file conflicted. PR #27 changed none of this branch's files. PR #28 added the metadata commands to `lib.rs`'s `invoke_handler`; git merged that cleanly with this branch's one-line launch-closure change, and the merged `lib.rs` differs from `main` only by that line.
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
| `Instruction_documentation/Handoff/Handoff_30.md` | This handoff |

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

After merging `main` at `6b79307` (2026-10-22), `python tools/gate.py all` **failed** at `deps`, because of vulnerability advisories published since 2026-10-19, not because of this change. `main` pins the same versions, so it fails the same check:

```
=== gate: deps
Found 24 known vulnerabilities in 1 package
pillow 12.3.0  CVE-2026-112390 … CVE-2026-112901 (24 IDs)  Fix Versions 13.0.0
=== FAILED: deps
```

The gate stops at the first failure, so the rest was run separately on the merged tree:

| Check | Result |
| --- | --- |
| docs, lint, format, typecheck, test (gate) | Passed; pytest 790 passed, 3 skipped, coverage 97.51% |
| sast (gate) | Passed |
| `pip_audit` of `requirements-dev.lock` (second half of `deps`) | **Failed**: `certifi 2026.7.22` PYSEC-2026-4320 (fix 2026.10.19), `uv 0.13.1` PYSEC-2026-4321 (fix 0.13.4) |
| `gate.py secrets licenses sbom gui` | secrets, licenses and sbom passed. gui: lint, typecheck, format, Vitest (101 passed) and build passed; it **failed** at `npm audit --audit-level=moderate`: `vite 8.3.0–8.3.2`, high (GHSA-698v-4r3x-3vcv, GHSA-r825-w8mm-5pxw, GHSA-587h-7wmj-h5pm, GHSA-9jrq-w75r-8gcw, GHSA-rq7h-c2jc-7f22, GHSA-vfpm-58rq-9qcg), fix `vite@8.3.5`, outside the declared range |
| cargo steps of the gui gate, run directly in `gui/src-tauri` | `fmt --check`, `clippy --all-targets -D warnings`, `test` with `RIDGE_REQUIRE_SIDECAR=1` (36 passed), `cargo audit --deny warnings` and `cargo deny check` all passed. Not run: the npm licence check, the npm CycloneDX SBOM and `cargo cyclonedx` (they come after `npm audit` in the gate) |

After merging `main` at `36e264a` (PR #28, 2026-10-22; the worktree `.venv` was re-installed from both lock files and `pip install -e .`), the same checks were run again. The result is the same: `python tools/gate.py all` **failed** at `deps` on the same 24 Pillow 12.3.0 advisories. Everything before that gate passed: pytest **867 passed**, 3 skipped, coverage **96.71%**. The dev-lock audit failed on the same certifi and uv advisories. In `gate.py secrets licenses sbom gui`, secrets, licenses and sbom passed, and gui passed Vitest (**108 passed**) and the build, then failed at `npm audit` on the same Vite advisories. All cargo steps passed: 36 Rust tests, including `a_missing_engine_asks_for_a_reinstall_every_time`, `no_engine_file_is_not_found` and the live sidecar test. The same three gui steps were not run.

The dependency upgrades are not part of this change; see §11 and §12.

Determinism and golden results: not affected; `tests/golden/` untouched.

Tests not run and why: the change was not exercised in a built release bundle (an installed build with its engine removed); the unit tests cover the classification and the notice.

Required tests still missing: none for this change.

## 10. Release readiness

Release type: internal build.

Ready: in review as a pull request. Not ready to merge while the `deps` and `gui` gates fail (§9).

Blockers: the new dependency advisories (§11), which also block `main`. Code signing and the other items in Handoff_26 §10 remain.

Rollback or mitigation: revert the four source files; no data or format depends on them.

## 11. Open risks and known issues

- `sidecar.rs` exceeds the file-size guideline (pre-existing).
- Since 2026-10-22 the `deps` and `gui` gates fail on `main` and on every branch, because of new advisories: Pillow 12.3.0 (24 CVEs, fix 13.0.0), certifi and uv (dev lock), and Vite 8.3.0–8.3.2 (npm audit). Pillow is the image decoder. A major upgrade can change decoded pixels and so the per-architecture goldens, which needs an ADR and human approval, and the advisories have to be reviewed against Ridge's allow-listed, bounded decoding. No merge should happen on a failing gate until this is settled.

## 12. Recommended next work

1. A separate dependency-security change, before any merge: review the Pillow 13.0.0 advisories and upgrade it with a golden-impact check (ADR if goldens change), and bump certifi, uv and Vite to fixed versions. Then re-run `python tools/gate.py all`.
2. Answer and resolve the review threads on the pull request; merge on green CI and a green local gate.
3. Split `sidecar.rs`: the process transport (`spawn`, `ChildTransport`, `launch`, `locate`) apart from the `Sidecar` restart and protocol logic, and move the tests with them.
4. Optionally: let the core's start messages carry their own next step everywhere, so the start screen stops appending advice (removes the two duplicated cases in §1).

## 13. First thing the next agent/developer should read or do

Read this handoff and the pull request. Launch the GUI only from an installed build or `npx tauri dev`, not from `target/release/deps/`.
