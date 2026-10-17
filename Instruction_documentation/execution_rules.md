# Execution Rules

Last verified: 2026-10-16
Mandatory workflow for coding agents (Claude Code and others) and human contributors on Ridge.

## Core rule

Do not start implementation until the task, impacted behaviour, forensic impact, applicable standards, risks, required tests and completion evidence are understood well enough to make a safe, minimal change.

If information is missing, make a documented assumption only for low-risk work. For anything touching the pipeline, decoding, output writing, hashing, custody, reports, keys, exports, sidecar or GUI IPC, record assumptions in the handoff (and the profile if standards change) before editing.

## Pre-work checklist

Before editing code, identify:

- The request and intended outcome; in-scope and out-of-scope behaviour.
- The relevant requirement in `docs/prd.md` and design in `docs/architecture.md` (including its ADR table).
- The latest handoff in `Instruction_documentation/Handoff/` and its open risks.
- Applicable standards from `standards_applicability_and_compliance_matrix.md` and `Project_Standards_Profile.md`.
- Modules affected (`src/ridge/...`, `fingerprint_extract.py` shim, `tools/`, `tests/`, planned `case/`, `custody/`, `report/`, `export/`, `quality/`, `minutiae/`, `sidecar/`, `gui/`).
- Data classes touched (E, C, I, S) and trust boundaries crossed (file system, decoder, configuration, sidecar stdio, WebView IPC).
- Forensic impact: can output pixels, defaults, recorded parameters or examiner-facing wording change?
- Determinism impact: threads, dependency versions, platform-specific code paths.
- Security, privacy, performance, accessibility and maintainability risks.
- Tests, scans, reviews and gates required.

## Standards impact assessment

For every substantial change, answer:

- Does it add or change an input format, decoder, output format, export format, dependency, platform, data store or process boundary?
- Does it change evidence handling, hashing, custody, reports, signatures, keys, encryption, logging or retention?
- Does it change pipeline numerics or defaults (method change, revalidation decision required)?
- Does it touch class E data paths, or add any network, telemetry or update capability (forbidden without profile change)?
- Does it introduce a trained model or other component that could be an AI system (AI Act reassessment)?
- Does it affect JSON contracts, timestamps, Unicode paths or floating-point tolerances?
- What evidence is required before release?

If the answer to any is yes, update the profile, tests and handoff.

## Implementation workflow

1. Read the required documentation (`AGENTS.md` reading order).
2. Inspect the existing implementation and tests before changing them.
3. Make the smallest safe change that satisfies the requirement.
4. Keep security, integrity and validation in the trusted layers (Python core, Tauri Rust core).
5. Respect file and function limits (`coding_standards.md`).
6. Add or update tests with the change; synthetic data only.
7. Run targeted tests after each meaningful change.
8. Run `python tools/gate.py all` before proposing a merge (plus GUI gates from M4).
9. Review the diff for behaviour changes, exposed secrets, class E data, weakened controls and standards gaps.
10. Update documentation and create the next handoff.

Work only on files within the task's scope. Another engineer or agent may be editing other parts of the repository at the same time; do not reformat, move or "fix" files outside the agreed scope.

## High-risk change rules

High risk for Ridge:

- `src/ridge/pipeline/` numerics, constants or defaults; `src/ridge/image_io.py`; limits and allow-lists.
- Output naming, writing, overwrite protection, directories.
- Hashing, run records, custody log, job reports, signatures, keys, case store, retention and deletion.
- Export formats and anything sent toward AFIS workflows.
- Sidecar protocol, Tauri commands, capabilities, CSP, packaging and update channel.
- Dependency upgrades of numpy, OpenCV, Pillow, pillow-heif or anything with native code.
- CI configuration, Actions pins, permissions, release signing.

High-risk changes require: standards impact assessment, threat-model note, tests for success, failure, boundary and regression paths, golden and determinism results, review focused on security and forensic impact, rollback or recovery notes, and a handoff entry with evidence and open risks.

## Coding-agent behaviour

Coding agents must:

- Read the relevant files before editing and state assumptions in the handoff.
- Never ask for, open, view, attach or process real finger photos, case material, volunteer data or outputs derived from them. Use synthetic data and numeric summaries.
- Avoid broad rewrites unless the task requires them; preserve public CLI options, exit codes and library API unless the task changes them.
- Never invent files, environment variables, gates or test results; if `tools/gate.py` lacks a gate named here, say so instead of claiming it ran.
- Never hide tool errors or scanner failures; document commands that could not run and why.
- Never update golden data, lower coverage, or disable rules to make a change pass.
- Never claim compliance, validation, accreditation or certification.
- Never commit, push or create releases unless the user asked for it.

## Data store execution rules (case store, M1)

- Schema changes require versioned migrations with recovery notes; old cases either open or fail with a clear, typed error.
- SQL uses parameterised statements only; SQLite dialect features are documented.
- Every mutating operation writes its custody entry in the same transaction or fails.
- RLS/RBAC rules are not applicable (single examiner); see `backend_database_rls_rpc_standards.md` for the trigger.

## Security execution rules

- Keep privileged operations in the Python core or Tauri Rust core; the WebView only displays and requests.
- Least privilege for files, processes, CI tokens and capabilities.
- Safe defaults: deny by default, explicit allow-lists, strict validation, bounded resources, redacted logging.
- Never place passphrases, keys or tokens in argv, environment variables, logs, run records or reports.
- Never log pixel data, full paths of originals at default level, or unnecessary personal data.
- Map recurring findings to CWE and add regression tests.

## Testing execution rules

- Reproduce bugs with a failing test before fixing.
- Test malformed, missing, oversized, duplicate, colliding and hostile inputs.
- Test determinism and golden outputs for any pipeline-adjacent change.
- From M1, test custody and report verification against tampering.
- From M4, test IPC denial paths.
- Run the smallest relevant test first, then the full gate. Do not merge with failing or skipped required gates unless an approved exception exists.

## Documentation execution rules

Update documentation when behaviour, standards applicability, inputs/outputs, configuration, environment variables, dependencies, security posture, forensic rules, release procedure or exceptions change. Product requirements go to `docs/prd.md`, design and ADRs to `docs/architecture.md` (or `docs/adr/` once created), rules to this pack. Runtime code never imports documentation.

## Completion criteria

A task is complete only when:

- Required behaviour is implemented and unchanged behaviour is protected.
- Applicable standards and forensic rules are satisfied or exceptions are recorded.
- Tests and gates ran, or are listed as not run with reason and risk.
- Security, data class handling and determinism were reviewed.
- Documentation and the next consecutive handoff are written.
- The verification summary (format in `testing_and_codex_quality_gates.md`) lists exact commands and results.
