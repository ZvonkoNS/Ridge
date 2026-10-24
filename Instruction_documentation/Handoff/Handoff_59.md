# Handoff_59.md

Date/time (ISO 8601 with offset): 2026-10-25T06:30+02:00
Author/agent: Claude Code (claude-fable-5-1), installers rebuilt from main
Project: Ridge
Branch: `main`
Base commit: `7353b0b` (Handoff_58)
Latest commit: see `git log main`

## 1. Scope

Requested change: rebuild the Windows installers from `main`, run the installer smoke test, replace the files and hashes under `installers/`, and push to `main`.

Completed work:

- Sidecar frozen from the clean `main` checkout: stamp `7353b0b`, `dirty: false`; `frozen archive ok: 937 modules, keystore backend keyring.backends.Windows, 7 decoders, 5 feature modules`; `native decoders ok` including `_imagingft.*`; `frozen sidecar ok: Ridge 0.2.0 7353b0b..., protocol ridge.sidecar/1, reads HEIF, checks a synthetic photo`.
- Bundles built with `npx tauri build --config src-tauri/tauri.release.conf.json`: MSI 83.36 MiB, per-user NSIS setup 58.42 MiB.
- Installer smoke test (release checklist, "From M4") on the per-user setup: silent install exit 0 into `%LOCALAPPDATA%\Ridge`; the installed engine answered `ridge.version` with Ridge 0.2.0, commit `7353b0b...`, protocol `ridge.sidecar/1`, source `build`, and passed the capture check of a synthetic photo (verdict ok, finger located); the application started and was still running after 8 s, then was closed; silent uninstall exit 0, binary removed. The MSI was built and hashed, not installed (per-machine, administrator).
- `installers/` replaced: both files, `SHA256SUMS.txt`, and the README's commit reference.

| File | Bytes | SHA-256 |
| --- | --- | --- |
| `installers/Ridge_0.2.0_x64_en-US.msi` | 87409724 | `5a425a01d4d93502faeac175a1fd74b0261087624b4e7f93e0c93c49941ab159` |
| `installers/Ridge_0.2.0_x64-setup.exe` | 61258621 | `b1b2ced4db22f21b84f3f1dbc9bcb75c21791aed28bd5e5216d64485d39833b9` |

Out of scope: code signing; macOS and Linux bundles; a release tag.

## 2. Current repository state

Git status summary: committed on `main` and pushed (the owner asked for a direct push); no feature branches, no open pull requests.

## 3. Standards applicability and evidence

Project standards profile updated: not needed.

| Standard/control/rule | Applies? | Evidence produced | Exception/deviation |
| --- | --- | --- | --- |
| Release checklist "From M4" (frozen sidecar checks, bundles, per-user install smoke test) | Yes | Section 1 | Code signing and the E2E suite as in the profile; MSI not installed |
| Artefacts built from a clean tree | Yes | Stamp `dirty: false` on `7353b0b` | None |

Standards checks or tools run: section 9.

Exceptions, deviations or evidence gaps: as above.

Steps outside coding work: code signing at release.

## 4. Forensic impact

None (no code change; the bundled engine is `main`'s).

## 5. Files changed

| File | Purpose of change |
| --- | --- |
| `installers/Ridge_0.2.0_x64_en-US.msi`, `installers/Ridge_0.2.0_x64-setup.exe`, `installers/SHA256SUMS.txt`, `installers/README.md` | Rebuilt installers, hashes, commit reference |
| `Instruction_documentation/Handoff/Handoff_59.md` (new) | This handoff |

## 6. Data store, records and formats

None.

## 7. Configuration, keys and CI

None.

## 8. Security

No change.

## 9. Tests

```bash
.venv/Scripts/python.exe tools/build_sidecar.py   # on 7353b0b, clean tree: the three "ok" lines of section 1
cd gui && npx tauri build --config src-tauri/tauri.release.conf.json   # Finished 2 bundles
# installer smoke test (scratchpad script, the release checklist's steps): all steps passed (section 1)
.venv/Scripts/python.exe tools/gate.py docs   # pass
```

Determinism and golden results: unaffected (no code change).

Tests not run and why: the MSI install (administrator); macOS and Linux bundles (platform); code signing (certificate).

## 10. Release readiness

Internal engineering build of `main`, unsigned, not for casework; the operational-release blockers are unchanged (Handoff_34, Handoff_48).

## 11. Open risks and known issues

- Two more large binaries in the repository's history (Handoff_57 section 11); release assets or Git LFS remain the lighter channel.

## 12. Recommended next work

Code signing and the release checklist when the owners decide on a release; a macOS and Linux bundle job if those installers are wanted.

## 13. First thing the next agent/developer should read or do

`installers/README.md` and this handoff's hash table.
