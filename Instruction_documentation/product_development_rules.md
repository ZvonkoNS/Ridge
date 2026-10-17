# Product Development Rules

Last verified: 2026-10-16
Product development discipline for Ridge. The PRD is project-specific and lives in `docs/prd.md`, outside this pack.

## Product operating principles

- Build only from a clear examiner need with measurable acceptance criteria in `docs/prd.md`.
- Ridge supports examiners; it never identifies, concludes or ranks. Every feature is checked against the forbidden claims in `forensic_evidence_and_biometric_data_standards.md`.
- Quality, security, forensic integrity, privacy and maintainability are product requirements.
- Lifecycle discipline per ISO/IEC/IEEE 12207 (requirements, architecture, implementation, verification, validation, transition, maintenance, retirement); Ridge sits inside the laboratory's examination process (ISO/IEC/IEEE 15288 view).
- ISO/IEC 25010 quality attributes as the quality model; ISO/IEC 14764 for maintenance after release.
- Engineering milestones (M0-M4) and operational use (Ops gate, `docs/prd.md` M5) are separate decisions; finishing a milestone never authorises casework.

## Required project-specific artifacts

Maintained outside this pack:

- `docs/prd.md`: product requirements with IDs, acceptance criteria, milestones, open questions (AFIS format, owners).
- `docs/architecture.md`: architecture, threat model, data flows, trust boundaries.
- Architecture decision records: table in `docs/architecture.md` section 13, individual files in `docs/adr/` when created.
- Validation plan and report, DPIA, AI Act assessment: laboratory QMS and DPO records (referenced from `Project_Standards_Profile.md`).
- Release notes and handoffs.

Maintained in this pack: `Project_Standards_Profile.md` (standards, exceptions, evidence locations).

## Definition of Ready

A feature is ready when the team or coding agent can answer:

- Which examiner problem does it solve, and which `docs/prd.md` requirement covers it?
- Which standards and forensic rules apply?
- What is in and out of scope, and what must not change (CLI options, outputs, golden results)?
- Which data classes are created, read, changed, exported, logged or deleted?
- Which trust boundaries are crossed?
- Can output pixels or defaults change (method change, revalidation decision)?
- Failure modes, limits, recovery paths?
- Required tests, reviews and evidence?
- Any legal or privacy question for the DPO?

If forensic or standards impact is unclear, write a short impact note first.

## Definition of Done

- Acceptance criteria met and verified with tests.
- Applicable standards and forensic rules addressed or exceptions recorded.
- Boundary data validated and bounded; failures typed and visible.
- Integrity controls (hashing, records, custody where implemented) cover the feature.
- Determinism and golden tests pass; pixel changes have an ADR.
- `python tools/gate.py all` passes (plus GUI gates from M4).
- Documentation, profile and the next consecutive handoff updated.
- No class E data, secrets or forbidden claims introduced.

## Product-quality requirements

| Attribute | Typical Ridge acceptance criteria |
| --- | --- |
| Functional suitability | Expected output on synthetic fixtures; documented behaviour for no finger found, no ridge pattern, too low resolution. |
| Performance efficiency | Time and peak memory per megapixel within targets in `docs/prd.md`. |
| Compatibility | Works on Windows 11, Linux, macOS; supported input formats listed. |
| Usability | Clear messages naming the file and the fix; parameters visible; accessible GUI. |
| Reliability | Deterministic output; no partial or overwritten files; store consistent after crashes. |
| Security | Limits, allow-lists, encrypted store, signed records, no network. |
| Maintainability | Size limits, typing, tests, ADRs. |
| Portability | Platform specifics isolated and tested. |

## Prioritisation

1. Evidence integrity, security, privacy and legal blockers.
2. Correctness of extraction and anything that could mislead an examiner.
3. Reproducibility and traceability gaps.
4. Maintainability work that unlocks safe delivery (the refactor).
5. New features with clear acceptance criteria.

Cosmetic or speculative work never outranks known integrity, security or validation gaps.

## Traceability

Mandatory for Ridge. Maintain links among: `docs/prd.md` requirement ID, standard or rule, ADR or design section, modules, tests, validation evidence, release checklist item and handoff.

## Requirements rules

- Testable, unambiguous, scoped; no bare "secure", "fast" or "accurate".
- Accuracy requirements are stated as validation criteria (for example FNMR at a fixed FMR) and are owned by the Forensic Quality Manager.
- Numerical requirements state units (pixels in which scale), tolerances and dtype where relevant.
- Timestamps ISO 8601 UTC; file names Unicode; JSON formats versioned.
- Platform expectations explicit.

## Domain trigger

Ridge is forensic-science software processing special-category biometric data under the LED. Before work starts, check: ISO/IEC 17025 and method validation impact; ISO 21043 and ENFSI practice; ISO/IEC 27037/27041/27042 evidence handling; biometric format and quality standards; LED, ZVOPOKD, GDPR and AI Act implications (to be confirmed by the DPO/legal).

Functional-safety and other regulated-domain standards (IEC 61508, ISO 26262, DO-178C, IEC 62304, EN 50128/50657, IEC 60880, IEC 61511, ISO 13849, ISO/IEC 21434, ISO/IEC 15408) do not apply. If a future scope triggers one, the project needs hazard analysis, traceability, a V&V plan and release evidence for that domain before release.

## Product documentation

- Examiner documentation covers use, inputs, limits, artefacts, forbidden claims, and how to verify hashes and reports.
- The repository `README.md` stays accurate for CLI usage.
- IEEE 1016-style design descriptions for high-risk decisions; UML/BPMN only where they help.
- Documentation is never imported by runtime code.

## Change management

- High-risk changes need impact analysis, owner review, rollback notes and tests.
- Method changes (pixels or defaults) need an ADR, golden update review and a revalidation decision.
- Breaking changes to CLI, library API or record formats need versioning and migration notes.
- Exceptions have an expiry and are reviewed at each milestone.
