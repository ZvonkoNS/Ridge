# Installers

Engineering builds of the Ridge desktop application for Windows, built from the commit named in
`Instruction_documentation/Handoff/Handoff_56.md`. They are **unsigned** and **not for casework**:
an operational release needs code signing with the laboratory's certificate and the approvals of the
release checklist (`Instruction_documentation/release_readiness_checklist.md`).

| File | What it is | Installs |
| --- | --- | --- |
| `Ridge_0.2.0_x64-setup.exe` | Per-user installer (NSIS). No administrator rights needed. | `%LOCALAPPDATA%\Ridge` |
| `Ridge_0.2.0_x64_en-US.msi` | Per-machine installer (WiX MSI). Needs an administrator. | `C:\Program Files\Ridge` |
| `SHA256SUMS.txt` | The SHA-256 of both files. | – |

Both bundle the frozen Python engine (`resources/sidecar/ridge-sidecar.exe`) that the application talks
to over stdio; nothing is downloaded at install time and the application never opens a network socket.

## Check before installing

```powershell
Get-FileHash .\installers\Ridge_0.2.0_x64-setup.exe -Algorithm SHA256
```

Compare the value with `SHA256SUMS.txt`. Windows will warn that the publisher is unknown, because the
files are unsigned.

## Install and uninstall

- Per user: run `Ridge_0.2.0_x64-setup.exe` (or `Ridge_0.2.0_x64-setup.exe /S` for a silent install). Uninstall
  from Windows Settings or with `%LOCALAPPDATA%\Ridge\uninstall.exe /S`.
- Per machine: run the `.msi` as an administrator. Uninstall from Windows Settings.

The per-user installer was smoke-tested on the build machine (silent install, the installed engine's version
and a capture check over stdio, the application started and closed, silent uninstall); the MSI was built and
hashed but not installed there.

## macOS and Linux

Tauri builds the `.dmg` and the `.AppImage` only on their own platforms, and this repository's CI builds no
bundles on macOS or Linux runners yet. Build them on such a machine with the steps in the repository README
("Building the desktop application"), or add a bundle job to `.github/workflows/gui.yml`.
