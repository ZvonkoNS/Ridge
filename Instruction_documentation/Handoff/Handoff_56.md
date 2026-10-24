# Handoff_56.md

Date/time (ISO 8601 with offset): 2026-10-25T02:40+02:00
Author/agent: Claude Code (claude-fable-5-1), ADR-015 and ADR-016 acceptance; release build and installer check of the stack top
Project: Ridge
Branch: `afis-release-check-36` (stacked on `afis-linked-marking-35`; local commits only, nothing pushed)
Base commit: `0549dd5` (tip of `afis-linked-marking-35`, pull request #49)
Latest commit: see `git log afis-release-check-36`

## 1. Scope

Requested change: the product owner confirmed both recommendations (ADR-015 and ADR-016) and asked for a check that the installers work with the latest update.

Completed work:

- **ADR-015 and ADR-016 accepted** (2026-10-25, product owner) in the architecture's ADR table; CHANGELOG entry. ADR-014 (the method variants themselves) stays proposed, awaiting the FQM's decision as before.
- **Frozen-build checks extended** (`tools/build_sidecar.py`): the archive must now hold the capture-check and annotation modules and Pillow's drawing and font modules (`FEATURES`); the folder must hold the FreeType extension (`_imagingft.*`, used for the mark numbers on the annotated image); the stdio smoke test writes the test suite's synthetic finger photo and asks the frozen engine for `photo.check`, which must locate the finger and give no reason to retake. The checks are the same whether run by the build or afterwards on the frozen folder.
- **Release build on the committed tree (`56c15b8`, stamp `dirty: false`):**

```text
frozen archive ok: 937 modules, keystore backend keyring.backends.Windows, 7 decoders, 5 feature modules
native decoders ok: _imaging.*, _webp.*, _pillow_heif.*, libheif*, _imagingft.*
frozen sidecar ok: Ridge 0.2.0 56c15b8f0b5a2fde659b975eaf4c470a9f4edd2a, protocol ridge.sidecar/1, reads HEIF, checks a synthetic photo
Finished 2 bundles: Ridge_0.2.0_x64_en-US.msi (83.36 MiB, WiX), Ridge_0.2.0_x64-setup.exe (58.43 MiB, per-user NSIS)
```

- **Installer smoke test** (release checklist, "From M4"), on the per-user NSIS installer: silent install (exit 0) into `%LOCALAPPDATA%\Ridge`; the installed engine answered `ridge.version` with Ridge 0.2.0, commit `56c15b8f…`, protocol `ridge.sidecar/1`, commit source `build`, and passed the capture check of a synthetic photo (verdict ok, finger located); the app (`ridge-gui.exe`) started and was still running after 8 s, then was closed; silent uninstall (exit 0) removed the binary. The MSI was built and hashed but not installed: it is a per-machine package and needs an administrator.

SHA-256 of the build outputs (engineering build, unsigned, not for casework; kept in the ignored `build/` and `gui/src-tauri/target/` folders, not published):

| File | Bytes | SHA-256 |
| --- | --- | --- |
| `gui/src-tauri/target/release/bundle/msi/Ridge_0.2.0_x64_en-US.msi` | 87409724 | `9c46ebdde1760e78eabde75a605c579b5cc9b9f7795f8da2b5bb1c9503ddddb2` |
| `gui/src-tauri/target/release/bundle/nsis/Ridge_0.2.0_x64-setup.exe` | 61264564 | `b20a35eb189c14a2342e601dadb9dafb82d3245a08183c33f75b41bc5ce09905` |

Out of scope: code signing (needs the laboratory's certificate, profile §8); the macOS and Linux bundles (built on their own platforms); a version bump (0.2.0 stays until a release is tagged).

## 2. Current repository state

Git status summary: committed on `afis-release-check-36` and pushed; pull request #50 against `afis-linked-marking-35` (opened 2026-10-25 on the owner's instruction); the build outputs are in ignored folders.

Recent commits: `56c15b8` (ADR acceptance and the build check), then this handoff; `0549dd5` (Handoff_55) and the stack below.

## 3. Standards applicability and evidence

Project standards profile updated: not needed (ADR-015 and ADR-016 change the GUI's defaults and a record form; the ADR-014 exception row is unchanged).

| Standard/control/rule | Applies? | Evidence produced | Exception/deviation |
| --- | --- | --- | --- |
| Release checklist "From M4" (GUI gate, frozen sidecar, bundles, per-user install smoke test) | Yes | Section 1 and section 9 | Code signing and the E2E suite as in the profile |
| Release artifacts built from a clean tree with hashed locks | Yes | Stamp `dirty: false` on `56c15b8`; `requirements-build.lock` with hashes | SBOMs and `SHA256SUMS` are produced at release time, not for this engineering build |
| ADR discipline | Yes | Both ADRs accepted by the owner with the date | None |

Standards checks or tools run: section 9.

Exceptions, deviations or evidence gaps: the MSI was not installed (administrator rights); macOS and Linux bundles not built here.

Steps outside coding work: the FQM's decision on ADR-014 remains open; code signing at release.

## 4. Forensic impact

Output pixels changed: no.

Defaults or recorded parameters changed: none in this handoff (ADR-015's default was implemented in Handoff_51).

Revalidation decision required / recorded: not applicable.

Examiner-facing wording changed (checked against forbidden claims): none.

Data classes touched: synthetic only (the smoke tests use the test suite's synthetic finger).

## 5. Files changed

| File | Purpose of change |
| --- | --- |
| `docs/architecture.md`, `CHANGELOG.md` | ADR-015 and ADR-016 accepted |
| `tools/build_sidecar.py` | Feature modules, FreeType and the capture check in the frozen-build checks |
| `Instruction_documentation/Handoff/Handoff_56.md` (new) | This handoff |

## 6. Data store, records and formats

None.

## 7. Configuration, keys and CI

None.

## 8. Security

The build tool gained one more stdio request to the frozen engine on a synthetic file in a temporary folder; nothing else.

## 9. Tests

Commands run:

```bash
.venv/Scripts/python.exe -m ruff check tools && .venv/Scripts/python.exe -m ruff format --check tools && .venv/Scripts/python.exe -m mypy tools/build_sidecar.py   # clean
.venv/Scripts/python.exe tools/gate.py docs   # pass
.venv/Scripts/python.exe tools/build_sidecar.py   # on 56c15b8, clean tree: the three "ok" lines of section 1
cd gui && npx tauri build --config src-tauri/tauri.release.conf.json   # Finished 2 bundles (section 1)
# installer smoke test (scratchpad script, steps of the release checklist): install /S, ridge.version + photo.check over stdio, start and close the app, uninstall /S   # all steps passed
```

Determinism and golden results: unaffected (no pipeline change). The full gates ran on `0549dd5`'s stack top in Handoff_54; this branch changes only docs and the build tool.

Tests not run and why: the MSI install (administrator); macOS and Linux bundles (platform); Tauri WebDriver E2E (profile exception); code signing (certificate).

Required tests still missing: none for this scope.

## 10. Release readiness

Release type: internal engineering build, unsigned, not for casework. Ready: the bundles build, install, start and uninstall on Windows with the current stack. Blockers for an operational release: unchanged from Handoff_34 (validation, DPIA, AI Act assessment, independent owners, code signing). Rollback: not applicable (nothing deployed).

## 11. Open risks and known issues

- The installed binary is `ridge-gui.exe` under `%LOCALAPPDATA%\Ridge`; the checklist's text says "start the app" without the name, which the smoke test now encodes.
- The MSI (per-machine) remains untested by installation on this workstation.

## 12. Recommended next work

Push this branch and open its pull request above #49 if the owner wants the ADR acceptance and the stronger build check reviewed with the stack; otherwise fold the two commits into #49's branch.

## 13. First thing the next agent/developer should read or do

`tools/build_sidecar.py` (the checks) and this handoff's hash table.
