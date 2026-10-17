# Instruction Documentation

Last verified: 2026-10-16
Update when: coding rules, security posture, forensic rules, release gates, quality-gate commands, architecture standards, standards references or agent workflows change.

## Purpose

This folder is the engineering instruction pack for Ridge, adapted from a reusable pack. It standardises engineering behaviour, secure coding, forensic evidence handling, biometric data protection, testing, release readiness, handoffs and coding-agent use (Claude Code and others) for this repository.

Ridge extracts fingerprints from ordinary photos of fingers for forensic casework: an examiner uses the output to compare manually against NAFIS/AFIS results. Ridge is an image-enhancement aid; it never identifies anyone and makes no conclusions.

This pack intentionally does **not** contain the PRD. Product requirements, milestones and open questions live in `docs/prd.md`; architecture, threat model and decisions in `docs/architecture.md` (ADR table in section 13; individual ADR files go to `docs/adr/` when created). This pack contains rules and the standards profile.

## Required placement

```text
<repo-root>/AGENTS.md                    Agent entrypoint (reading order, mandatory behaviour)
<repo-root>/CLAUDE.md                    Claude Code bridge; imports AGENTS.md
<repo-root>/Instruction_documentation/   This pack
<repo-root>/docs/                        PRD, architecture, ADRs (project-specific)
```

## Standards-first operating model

Ridge's applicable standards, editions, evidence locations and exceptions are declared in `Project_Standards_Profile.md`. Applicability verdicts per standard are in `standards_applicability_and_compliance_matrix.md`. Work must meet the strictest applicable rule. This pack supports evidence for laboratory accreditation, method validation and data-protection assessments; it does not replace the accreditation body, the Forensic Quality Manager, the DPO or legal review, and nothing here is a claim of compliance or certification.

Status tags used across the pack: **Now** applies today; **M0-M4** release blocker from that milestone; **Ops gate** = milestone M5 in `docs/prd.md` (validation and approval), required before operational casework; **Not applicable to Ridge today** comes with the trigger that would make it applicable. Milestone definitions: `docs/prd.md` section 7 (summary in `Project_Standards_Profile.md` section 2).

## Reading order for every substantial task

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
12. Task-relevant documents: architecture and modularity, case store, write-path audit, entrypoint/sidecar, environment and secrets, desktop GUI, release checklist; ADRs (section 13 of `docs/architecture.md`, later individual files in docs/adr/)

## Folder contents

| File | Purpose |
| --- | --- |
| `standards_applicability_and_compliance_matrix.md` | Generic standards matrix with Ridge verdicts; ASVS 5.0.0, Top 10:2025 and CWE Top 25 (2025) mappings; biometric, forensic and privacy/legal sections. |
| `Project_Standards_Profile.md` | Ridge's filled standards profile: owners, context, milestones, editions, assurance level, evidence, exceptions. |
| `Project_Standards_Profile_Template.md` | Blank template kept for reuse. |
| `forensic_evidence_and_biometric_data_standards.md` | Canonical forensic rules: what Ridge must never claim, data classes, immutability, hashing, custody log, reproducibility, signed reports, examiner in the loop, minimisation, retention, synthetic data, method validation. |
| `product_development_rules.md` | Lifecycle, Definition of Ready/Done, prioritisation, traceability. |
| `coding_standards.md` | Python profile (3.12+, ruff, mypy --strict, typed errors, safe file handling, deterministic numerics), supply chain, GUI language summary. |
| `execution_rules.md` | Mandatory workflow, high-risk changes, coding-agent behaviour, completion criteria. |
| `architecture_and_modularity_standards.md` | Target `src/ridge/` layout, dependency rules, ADR triggers, refactoring rules. |
| `edge_function_standards.md` | Thin entrypoints: CLI, Python sidecar JSON-RPC handlers, Tauri commands. Serverless parts not applicable. |
| `backend_database_rls_rpc_standards.md` | Encrypted case store, custody-log storage, data access, exports, retention. RLS/tenancy not applicable (trigger stated). |
| `direct_mutation_authorization_audit.md` | Audit of every write path, filled with today's write paths in `fingerprint_extract.py`. |
| `environment_configuration_and_secrets.md` | Configuration precedence, `RIDGE_*` variables, passphrases, key custody, signing keys, CI secrets. |
| `desktop_gui_tauri_standards.md` | Future Tauri v2 + React + TypeScript GUI: trust boundaries, IPC allow-list, CSP, no remote content, offline updates, accessibility, Motion animation standard, testing. |
| `testing_and_codex_quality_gates.md` | Test taxonomy, forensic validation tests, hostile input and fuzzing, `python tools/gate.py` gates, pack command mapping. |
| `release_readiness_checklist.md` | Automated and forensic release gates, release artifacts, delivery checks, blockers. |
| `handoff_workflow.md` | Consecutive handoff workflow and content. |
| `Handoff/Handoff_Template.md` | Copy as `Handoff_1.md`, `Handoff_2.md`, ... |
| `references.md` | Verification log (editions checked 2026-10-16 with sources) and reference index. |

## Non-negotiable project invariants

- Ridge never identifies, matches or concludes; outputs are processed images for an examiner.
- Original evidence is read-only and never modified; every input and output is hashed (SHA-256).
- Real finger photos, case material and outputs never enter the repository, CI, issues, handoffs, logs or coding-agent sessions. Tests use synthetic data only.
- No network access, telemetry or internet updates at runtime.
- Security and integrity are enforced in the Python core and the Tauri Rust core. The GUI WebView is untrusted.
- External input (files, metadata, arguments, configuration, RPC/IPC payloads) is untrusted until validated and bounded.
- Secrets never appear in code, argv, environment variables, logs, reports, fixtures or docs.
- Same input, version, parameters and platform give identical output.
- Runtime code never imports documentation; documentation is not shipped in runtime packages.
- Timestamps ISO 8601 UTC; text UTF-8/Unicode; JSON valid and schema-checked at trust boundaries.
- A task is complete only when unchanged behaviour, security, forensic impact, failure handling and tests are verified.

## Maintaining this pack

1. Keep `Project_Standards_Profile.md` current at every milestone and when owners are named.
2. Re-verify editions in `references.md` before citing them in a release or validation document.
3. Record exceptions only in the profile, with owner, compensating control and expiry.
4. When the GUI, case store or exports are built, update the corresponding file from "planned" to concrete rules and tests.
5. When `docs/prd.md` or `docs/architecture.md` decide something this pack assumes (milestones, environment variables, case-store design), align the pack and note it in the handoff.

## Naming convention

The folder name is exactly `Instruction_documentation/`. File names in this folder are referenced from `AGENTS.md`, other pack files and the `docs` gate; do not rename them.
