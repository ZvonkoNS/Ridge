# Repository Agent Instructions

This file is the root bridge for coding agents (Claude Code and others) working on Ridge. Keep it at the repository root together with `Instruction_documentation/`. `CLAUDE.md` imports this file.

Ridge extracts fingerprints from photos of fingers for forensic casework. It is an image-enhancement aid for a fingerprint examiner; it never identifies anyone and never makes conclusions. Finger photos and extracted prints are special-category biometric data.

Before any implementation work, read these files in order:

1. `AGENTS.md`
2. `Instruction_documentation/README.md`
3. `Instruction_documentation/standards_applicability_and_compliance_matrix.md`
4. `Instruction_documentation/Project_Standards_Profile.md`
5. `Instruction_documentation/forensic_evidence_and_biometric_data_standards.md`
6. `Instruction_documentation/execution_rules.md`
7. `Instruction_documentation/coding_standards.md`
8. `Instruction_documentation/testing_and_codex_quality_gates.md`
9. The latest file in `Instruction_documentation/Handoff/`
10. `docs/prd.md`
11. `docs/architecture.md`
12. Any task-relevant document: `Instruction_documentation/` files for architecture, case store, write paths, entrypoints and sidecar, configuration and secrets, desktop GUI, release; ADRs (section 13 of `docs/architecture.md`, later individual files in docs/adr/)

`docs/prd.md`, `docs/architecture.md` and `tools/gate.py` are project files outside this pack. ADRs live in section 13 of `docs/architecture.md` until docs/adr/ is created. If a referenced file is missing, report it; do not invent its content.

## Mandatory agent behaviour

- Start every substantial feature, fix, refactor, dependency upgrade or pull request by identifying the applicable language, security, forensic, biometric, privacy, testing and documentation standards, and the forensic impact (can output pixels, defaults or examiner-facing wording change?).
- Keep `Instruction_documentation/Project_Standards_Profile.md` current; record exceptions there before making high-risk changes that need one.
- Apply the latest stable published edition of each applicable standard. Drafts only when the profile adopts them.
- When standards conflict, follow the stricter rule unless the profile records a reviewed exception with risk, compensating control and owner approval.
- Do not claim certification, accreditation, method validation, legal compliance or third-party conformity. Ridge outputs must never be described as an identification or match.
- Do not implement until you have identified impacted files and modules, data classes, trust boundaries, write paths, security and forensic implications, unchanged behaviour, applicable standards, evidence required and required tests.
- Never request, open, attach or process real finger photos, case material, volunteer data or outputs derived from them. Use synthetic data only. Never commit images or other biometric data.
- Never modify original evidence; never overwrite outputs silently (only the explicit `--overwrite` flag of `docs/prd.md` FR-11, outside the case store); keep decoding bounded and allow-listed.
- Preserve working behaviour unless the task explicitly changes it. Golden outputs (`tests/golden/`) change only with an ADR and human approval.
- Keep changes minimal, secure, reversible, traceable and test-covered.
- Never move security-critical logic into the GUI WebView; it is untrusted. Trusted layers are the Python core and the Tauri Rust core.
- Never place secrets, passphrases or keys in code, argv, environment variables, logs, reports, fixtures or docs.
- Never weaken validation, limits, hashing, custody, auditability, determinism or error visibility to make a task easier.
- Keep entrypoints (CLI handlers, sidecar JSON-RPC handlers, Tauri commands) around 20-30 lines by delegating to small modules.
- Keep source files around 300 lines; split by responsibility before adding behaviour.
- Run `python tools/gate.py all` (plus the GUI gates once `gui/` exists) before proposing a merge or release.
- Do not claim tests passed unless the exact command ran successfully in the current workspace. If a gate, test or check cannot run, state exactly what was not run and why.
- Work only within the task's scope; other engineers or agents may be editing other files at the same time.
- Create the next consecutive handoff (`Instruction_documentation/Handoff/Handoff_<N>.md`) before ending a substantial task, including standards impact, forensic impact, evidence produced and unresolved exceptions.

The reusable pack contains no PRD. Ridge's product requirements are in `docs/prd.md`.
