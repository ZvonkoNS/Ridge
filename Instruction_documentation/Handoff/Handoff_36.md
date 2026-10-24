# Handoff_36.md

Date/time (ISO 8601 with offset): 2026-10-24T11:20+02:00
Author/agent: Claude Code (claude-fable-5-1), autonomous window of 2026-10-24 (see Handoff_35 section 1)
Project: Ridge
Branch: `afis-deps-20` (stacked on `afis-gray-export-19`; local commit only, nothing pushed)
Base commit: `d799929` (tip of `afis-gray-export-19`)
Latest commit: see `git log afis-deps-20`

## 1. Scope

Requested change: none directly. `python tools/gate.py all` on the previous branch failed in `deps` and in the GUI gate's `npm audit` on advisories published after the last audit (Handoff_31, 2026-10-23); the locks had not been touched. Without this fix no branch of the stack can pass the full gate.

Completed work:

- `requirements-dev.lock`: `filelock` 4.2.0 → 4.2.4 (CVE-2026-112906, -112907, -112913, -112914, -112937, -112940; fix 4.2.1) and `setuptools` 84.0.0 → 84.2.1 (GHSA-xmj3-9gf7-h52w; fix 84.1.0), compiled with the command recorded in the lock's header (`uv pip compile … --upgrade-package filelock --upgrade-package setuptools`). Six lines changed; nothing else moved. The runtime lock (`requirements.lock`) was clean and is unchanged.
- `gui/package-lock.json`: `npm audit fix --audit-level=moderate` moved the transitive development package `fast-uri` out of the vulnerable range (GHSA-w74x-v6f9-j3xg, -xhq7-xmqj-769h, -wjr9-j795-jxcr, -333x-w4r6-6crp; one package changed, `package.json` unchanged).
- The development virtualenv was re-synced from the lock (`pip install --require-hashes --no-deps -r requirements-dev.lock`).

Out of scope: `requirements-build.lock` still pins `setuptools` 84.0.0. It is not audited by the `deps` gate and it decides the frozen sidecar build (architecture §10); upgrading it is a release-build change for the Quality/Release Owner to schedule with the next build (`tools/build_sidecar.py` smoke test), not for a stack about exports.

## 2. Current repository state

Git status summary: committed on `afis-deps-20`.

Recent commits: `d799929` (item 1, Handoff_35) below this one.

## 3. Standards applicability and evidence

Project standards profile updated: not needed (the dependency-audit row already describes the gate; no new dependency, licence or native code).

| Standard/control/rule | Applies? | Evidence produced | Exception/deviation |
| --- | --- | --- | --- |
| SEC-6 dependency audit; NIST SSDF PW.4 | Yes | `python tools/gate.py deps`: both locks "No known vulnerabilities found"; `npm audit --audit-level=moderate`: 0 vulnerabilities; npm licence allow-list check passes | None |
| Coding standards, supply chain (hash-pinned locks, no new dependency) | Yes | Locks regenerated with hashes by the recorded commands; no new package | None |

Exceptions, deviations or evidence gaps: the build lock (section 1).

Steps outside coding work: none.

## 4. Forensic impact

Output pixels changed: no. These are development and GUI-build tools only; `filelock` and `setuptools` are not imported by `ridge`, and `fast-uri` is a development dependency of the GUI toolchain. No decoder, numerics or default changed.

Defaults or recorded parameters changed: no. Revalidation decision required: no. Examiner-facing wording changed: no. Data classes touched: none.

## 5. Files changed

| File | Purpose of change |
| --- | --- |
| `requirements-dev.lock` | filelock 4.2.4, setuptools 84.2.1 with hashes |
| `gui/package-lock.json` | fast-uri out of the advised range |
| `CHANGELOG.md` | Entry |
| `Instruction_documentation/Handoff/Handoff_36.md` (new) | This handoff |

## 6. Data store, records and formats

None.

## 7. Configuration, keys and CI

None.

## 8. Security

Closes the seven Python and four npm advisories above in the development toolchain. No trust-boundary change.

## 9. Tests

Tests added or updated: none (no code change).

Commands run:

```bash
.venv/Scripts/uv.exe pip compile requirements-dev.in --universal --python-version 3.12 --generate-hashes -o requirements-dev.lock --upgrade-package filelock --upgrade-package setuptools
.venv/Scripts/python.exe -m pip install --require-hashes --no-deps -r requirements-dev.lock
.venv/Scripts/python.exe tools/gate.py deps          # requirements.lock and requirements-dev.lock: No known vulnerabilities found
cd gui && npm audit fix --audit-level=moderate && npm audit --audit-level=moderate   # found 0 vulnerabilities
.venv/Scripts/python.exe -c "from gate_gui import npm_licences_ok; ..."           # npm licences ok: True
cd gui/src-tauri && cargo audit --deny warnings && cargo deny --locked check          # pass (Rust unchanged)
.venv/Scripts/python.exe tools/gate.py docs          # pass
```

Determinism and golden results: not affected (no runtime change); the full test gate ran on the previous branch (Handoff_35) with identical runtime dependencies.

Tests not run and why: the full `gate.py all` was not repeated here (only the two lock files changed; the gates that read them, `deps`, the npm audit and the licence check, were run); it runs on the stack top before any merge.

## 10. Release readiness

Release type: internal build. Ready: as part of the stack. Blockers: none from this branch. Rollback: revert the commit (the advisories then return).

## 11. Open risks and known issues

- `requirements-build.lock` keeps setuptools 84.0.0 (section 1).

## 12. Recommended next work

Item 2 of the assessment (scale reference objects and the no-reference notice), on the next branch.

## 13. First thing the next agent/developer should read or do

Handoff_35 section 12 for the order of the stack.
