# Standards Applicability And Compliance Matrix

Last verified: 2026-10-16
Use this file to decide which standards apply to a project, feature, module, language, deployment environment, or release. The "Ridge" column gives the verdict for this repository; the selected editions and evidence are in `Project_Standards_Profile.md`; verified sources are in `references.md`.

## Compliance rule

Every project must apply the latest stable published edition of each applicable standard unless the project-specific standards profile documents a different edition, a toolchain constraint, a contractual requirement, or a formal exception.

Applicability is determined by what the project actually builds or operates:

- Programming language standards apply only to source code, generated code, build scripts, or embedded runtimes written in that language.
- Security standards apply to all software that stores, processes, transmits, authenticates, authorizes, exposes APIs, integrates with third parties, or runs in production.
- Lifecycle, quality, testing, verification, documentation, and maintainability standards apply to all non-trivial production software.
- Functional-safety and domain standards apply only when the project domain, customer contract, regulatory regime, hazard analysis, or safety classification requires them.
- Interface, portability, data, numerical, and encoding standards apply when the project exposes or consumes the relevant formats, OS APIs, protocols, or computations.

These instructions create an engineering compliance posture. They do not by themselves create legal compliance, ISO certification, laboratory accreditation, method validation, safety certification, regulatory clearance, Common Criteria certification, or customer acceptance.

Ridge verdict legend: **Yes** applies now; **Partly** some clauses apply (stated); **Future (Mx)** applies from that milestone or trigger; **No** not applicable (reason stated where not obvious).

## Default baseline for every production project

- Secure SDLC aligned to NIST SSDF, ISO/IEC 27034, OWASP ASVS, OWASP Top 10, and CWE.
- Product-quality targets aligned to ISO/IEC 25010 and structural-quality concerns aligned to ISO/IEC 5055.
- Lifecycle discipline aligned to ISO/IEC/IEEE 12207 and maintenance discipline aligned to ISO/IEC 14764.
- Testing process and evidence aligned to ISO/IEC/IEEE 29119, IEEE 730, and IEEE 1012 where applicable.
- Explicit traceability from requirement to design to implementation to test to release evidence.
- Language-specific standards and style guides for every language used.
- Security scanning, dependency review, secret scanning, and supply-chain checks in CI.
- Documented exceptions with risk owner, compensating control, expiration date, and follow-up task.

Ridge adds, as baseline for every change: forensic evidence rules (`forensic_evidence_and_biometric_data_standards.md`), biometric data protection, and the privacy/legal constraints in the last sections of this file.

## Required project standards profile

Every project needs a profile with owners, repository, product type, environments, data classification, technologies, applicable standards with editions, assurance level, release gates, domain classification, and exceptions. Ridge: `Project_Standards_Profile.md` (template: `Project_Standards_Profile_Template.md`).

## Language standards matrix

| Standard family | Applies when | Required engineering posture | Evidence | Ridge |
| --- | --- | --- | --- | --- |
| Python language reference (CPython) | Python source exists. | Declare minimum version; PEP 8/257/484; strict typing; see `coding_standards.md`. | ruff, mypy, pytest output. | Yes (3.12+, dev 3.13). |
| ISO/IEC 9899 - C | C source, native extensions, C ABI boundary. | Declare edition; strict diagnostics; avoid undefined behaviour; static analysis; MISRA/CERT/BARR-C/JPL for high-integrity code. | Compiler flags, analysis, sanitizer/fuzz results. | No project C. Native C/C++ in OpenCV, libheif and codecs is handled as supply chain plus fuzzing at the decode boundary. |
| ISO/IEC 14882 - C++ | C++ source or native modules. | Declare edition; RAII; safe containers; static analysis; MISRA C++/CERT/HIC++ where high-integrity. | Compiler settings, clang-tidy, sanitizers. | No (as above). |
| ISO/IEC 1539 - Fortran | Fortran source. | Declare edition; explicit interfaces; numerical regression fixtures. | Build flags, numerical tests. | No. |
| ISO/IEC 8652 - Ada | Ada source. | Strong typing, contracts, SPARK where appropriate. | Diagnostics, proofs. | No. |
| ISO/IEC 1989 - COBOL | COBOL source. | Declare dialect; protect data conversions. | Integration tests. | No. |
| ISO/IEC 7185 / 10206 - Pascal | Pascal source. | Declare dialect; range and type discipline. | Compiler settings. | No. |
| ISO/IEC 13211 - Prolog | Prolog source. | Test determinism and termination. | Predicate tests. | No. |
| ISO/IEC 13816 - ISLISP | ISLISP source. | Isolate extensions. | Compatibility tests. | No. |
| ISO/IEC 23270, ECMA-334 - C# | C# source. | Nullable references, analyzers, safe serialization. | Analyzer output. | No. |
| ECMA-335 - CLI | .NET assemblies. | CLI type, metadata and versioning constraints. | API compatibility checks. | No. |
| ECMA-372 - C++/CLI | C++/CLI bridge code. | Small interop boundary. | Interop tests. | No. |
| ISO/IEC 9075 - SQL | SQL, schema, migrations. | Parameterised queries; documented dialect; migration and recovery tests. | Migration, query tests. | Only if SQLite is chosen for the case store (`docs/architecture.md` ADR-008 proposes files plus JSONL). |
| ECMA-262 / ISO/IEC 22275 | JavaScript runtime behaviour. | Latest supported stable edition; strict lint; TypeScript strict; no dynamic code. | Lint, typecheck, tests. | Future (M4): GUI. |
| Rust (reference and edition) | Rust source. | Stable toolchain, declared edition, Clippy, `forbid(unsafe_code)`. | Clippy, cargo audit/deny. | Future (M4): Tauri core. |
| ECMA-404 - JSON | JSON stored, exchanged or configured. | Valid JSON; reject invalid input; schema validation at trust boundaries; RFC 8785 canonical form where hashed or signed. | Contract and malformed-input tests. | Yes: run records; M1 reports and custody log; M4 JSON-RPC. |
| ISO 6160 - PL/I | PL/I source. | Declare dialect. | Tests. | No. |

## Coding guidelines and high-integrity style matrix

| Standard or guide | Applies when | Required engineering posture | Evidence | Ridge |
| --- | --- | --- | --- | --- |
| MISRA C / C++, AUTOSAR C++14 | Safety-related or embedded C/C++. | Newest supported edition; documented deviations. | MISRA report. | No. |
| CERT C / C++ / Java / Perl | Those languages in security-sensitive code. | CERT rules for memory, input, integers, errors. | Rule mapping. | Partly: no CERT Python standard exists; CERT concepts (validate input, handle all errors, bounded resources) are applied through `coding_standards.md`. |
| JSF AV C++, JPL C, HIC++, BARR-C | Mandated high-integrity profiles. | Treat as stricter overlay. | Checklist. | No. |
| PEP 8 / PEP 257 | Python is used. | Style, docstrings, type hints, linters, tests. | ruff, mypy. | Yes. |
| Google Style Guides | Selected as project guide. | Apply consistently. | Lint output. | No (PEP 8 + ruff selected). |
| Linux Kernel / GNU Coding Standards | Kernel or GNU packages. | Follow those conventions. | Checkpatch, build. | No. |

## Software quality, process, and lifecycle matrix

| Standard or model | Applies when | Required engineering posture | Evidence | Ridge |
| --- | --- | --- | --- | --- |
| ISO/IEC/IEEE 12207 | All substantial software. | Lifecycle processes, configuration management, V&V, maintenance, disposal. | PRD, ADRs, handoffs, release records. | Yes. |
| ISO/IEC/IEEE 15288 | Software within a larger system. | Align with system requirements and interfaces. | Interface verification. | Partly: Ridge is one tool in the lab's ACE-V and AFIS workflow. |
| ISO/IEC 25000 / 25010 | All production software. | Quality attributes with acceptance criteria. | Tests per attribute. | Yes. |
| ISO/IEC 9126 | Legacy contracts. | Map to 25010. | Mapping table. | No. |
| ISO/IEC 14764 | Maintained software. | Impact analysis, regression protection. | Maintenance records. | Yes. |
| ISO/IEC 90003 | Organisation applies ISO 9001. | Align QMS practice. | QMS records. | Confirm with the Forensic Quality Manager whether the lab QMS requires it. |
| ISO/IEC 33000 / CMMI | Process assessment required. | Measured processes. | Assessment artifacts. | No. |

## Security standards matrix

| Standard or framework | Applies when | Required engineering posture | Evidence | Ridge |
| --- | --- | --- | --- | --- |
| ISO/IEC 27001 / 27002 | Sensitive data, ISMS. | Align access, cryptography, logging, supplier, change management with the ISMS. | Risk register, control evidence. | Yes (align with organisation ISMS; no certification claim). |
| ISO/IEC 27034 | Applications built or operated. | AppSec controls across the lifecycle. | Control mapping. | Yes. |
| ISO/IEC 15408 | Formal evaluation required. | Security target and evaluation evidence. | Evaluator artifacts. | No (not required). |
| ISO/IEC 21434 | Automotive. | TARA. | Cybersecurity case. | No. |
| ISO/IEC 5055 | Structural quality measurement. | Measure weaknesses. | Metrics. | Optional. |
| OWASP ASVS | Apps with input validation, file handling, cryptography, auth, endpoints. | Verification baseline; stronger level for sensitive systems; test allow and deny paths. | Checklist, tests. | Yes, 5.0.0 Level 3 where applicable (chapter map below). |
| OWASP Top 10 | Web- or API-facing software; useful taxonomy for others. | Protect against current risk classes. | Threat model, tests. | Yes as taxonomy (2025 map below). |
| CWE | Any software. | Map findings to CWE; prevent Top 25 classes. | Findings with CWE IDs. | Yes (2025 Top 25 map below). |
| NIST SP 800-53 | Federal or contractual control baseline. | Map controls. | Control matrix. | No. |
| NIST SP 800-218 SSDF | All production software. | Prepare, protect, produce, respond. | SSDF evidence. | Yes: v1.1 (final). Rev. 1 (v1.2) is a draft; not adopted. |

### OWASP ASVS 5.0.0 chapters for Ridge (offline desktop)

| Chapter | Ridge | Scope in Ridge |
| --- | --- | --- |
| V1 Encoding and Sanitization | Partly | JSON output encoding; neutralise control characters in file names printed to the terminal (CWE-150); GUI rendering of untrusted strings (M4). |
| V2 Validation and Business Logic | Yes | Parameter ranges, input limits, case state transitions. |
| V3 Web Frontend Security | Future (M4), partly | CSP and script restrictions in the WebView; cookie and HTTP-header items not applicable. |
| V4 API and Web Service | No | No HTTP API. JSON-RPC over stdio follows `edge_function_standards.md`. Trigger: any network API. |
| V5 File Handling | Yes (core) | Size and pixel limits, format allow-list, decompression bombs, path handling, no silent overwrite. |
| V6 Authentication | Future (M1), partly | Case-store passphrase handling; the OS login is outside Ridge. |
| V7 Session Management | Future (M4), partly | Case auto-lock after inactivity, key material cleared from memory. |
| V8 Authorization | Partly | Deny-by-default IPC allow-list (M4); case access bound to key unwrap (M1). |
| V9 Self-contained Tokens, V10 OAuth and OIDC | No | No tokens or federated login. |
| V11 Cryptography | Future (M1) | AES-256-GCM, SHA-256, Ed25519, Argon2id, CSPRNG, nonce rules, key lifecycle. |
| V12 Secure Communication | No | No network. Trigger: any network component. |
| V13 Configuration | Yes | No secrets in configuration, release builds without debug features, dependency and build hygiene. |
| V14 Data Protection | Yes | Class E handling, minimisation, no caching, retention and deletion. |
| V15 Secure Coding and Architecture | Yes | Dependency management, safe deserialization, resource limits, concurrency rules. |
| V16 Security Logging and Error Handling | Yes | Custody log (M1), local logs without sensitive data, fail closed, no swallowed errors. |
| V17 WebRTC | No | Not used. |

### OWASP Top 10:2025 relevance

| Category | Ridge relevance |
| --- | --- |
| A01 Broken Access Control | Path traversal on output and case-store paths; IPC allow-list (M4). |
| A02 Security Misconfiguration | Decoder allow-list, debug outputs, Tauri CSP and capabilities. |
| A03 Software Supply Chain Failures | Hashed lock files, native decoder libraries, pinned Actions, SBOM. |
| A04 Cryptographic Failures | Case store, key custody, signatures (M1). |
| A05 Injection | No shell, no SQL string building (M1), terminal escape sequences. |
| A06 Insecure Design | Threat model in `docs/architecture.md`; forensic design caveats. |
| A07 Authentication Failures | Passphrase handling (M1). |
| A08 Software or Data Integrity Failures | Core concern: evidence integrity, signed reports and releases, no unsafe deserialization. |
| A09 Security Logging and Alerting Failures | Custody log; integrity failures surfaced to the examiner. |
| A10 Mishandling of Exceptional Conditions | Legacy decoder error swallowing; fail-closed rules. |

### CWE Top 25 (2025) and related weaknesses relevant to Ridge

| CWE (2025 rank) | Ridge control |
| --- | --- |
| CWE-22 Path Traversal (6) | Resolve and contain output and case-store paths; refuse symlinked targets (also CWE-59). |
| CWE-787 (5), CWE-125 (8), CWE-120 (11), CWE-121 (14), CWE-122 (16) memory errors | Present in native decoders: format allow-list, size and pixel limits before decode, fuzzing, prompt patching. |
| CWE-78 (9), CWE-77 (23) command injection | No shell; `subprocess` only with argument lists and fixed executables (validation tooling, sidecar). |
| CWE-94 Code Injection (10) | No `eval`, `exec`, dynamic import of user-provided names. |
| CWE-434 Dangerous File Type (12) | Content-based format allow-list. |
| CWE-502 Deserialization (15) | No pickle; `numpy.load(..., allow_pickle=False)`; JSON only for records. |
| CWE-20 Improper Input Validation (18) | Typed validation of parameters, files, RPC requests. |
| CWE-200 Exposure of Sensitive Information (20) | Class E never in logs, errors or exports beyond intent. |
| CWE-770 Allocation Without Limits (25) | Byte, pixel, batch and memory limits. |
| Not in Top 25 but relevant | CWE-400, CWE-409 (decompression bomb), CWE-367 (TOCTOU on writes), CWE-377 (temp files), CWE-312 (cleartext storage), CWE-532 (log exposure), CWE-214/CWE-526 (secrets in argv or environment), CWE-323 (nonce reuse), CWE-330 (weak randomness), CWE-390/CWE-703 (swallowed errors), CWE-150 (terminal escapes). |

## Domain-specific and functional-safety matrix

| Standard | Applies when | Required engineering posture | Ridge |
| --- | --- | --- | --- |
| IEC 61508, ISO 26262, DO-178C/ED-12C, IEC 62304, EN 50128/50657, IEC 60880, IEC 61511, ISO 13849 | The software performs or supports a safety function in that domain. | Hazard/risk analysis, integrity level, traceability from hazard to test, V&V with required independence, tool confidence, safety case. | No: Ridge has no safety function. Its domain is forensic science (section below). |

## Modeling, notation, and documentation matrix

| Standard | Applies when | Required engineering posture | Ridge |
| --- | --- | --- | --- |
| ISO/IEC 19505 - UML | UML diagrams used. | Standard notation; diagrams consistent with code. | Optional. |
| ISO/IEC 19510 - BPMN | Workflows modelled. | Standard notation including error flows. | Optional (custody and case workflow). |
| ISO/IEC 14977 - EBNF | Grammars or DSLs specified. | Precise grammar plus parser tests. | No. |
| ISO/IEC/IEEE 26512-26515 | User or acquirer documentation required. | Accurate, versioned, task-oriented docs linked to releases. | Partly: examiner user documentation before the Ops gate. |
| IEEE 1016 | Design descriptions required. | Context, stakeholders, views, rationale, interfaces, data, traceability. | Yes: style for `docs/architecture.md` and ADRs. |

## Numerical, text, and data matrix

| Standard | Applies when | Required engineering posture | Ridge |
| --- | --- | --- | --- |
| IEEE 754 / ISO/IEC 60559 | Floating-point computation. | Define precision, rounding, NaN/Infinity handling, tolerances, reproducibility and comparison rules. | Yes: float32/float64 pipeline; rules in `coding_standards.md`. |
| ISO/IEC 10646 / Unicode | Text stored or exchanged. | Unicode-compatible encoding; normalise where identity depends on text; guard against confusables, truncation and encoding attacks. | Yes: non-ASCII paths on Windows, examiner names, reports (UTF-8). |
| ISO/IEC 646, ISO 8859 | Legacy encodings. | Isolate and test conversions. | No. |
| ISO 8601 | Timestamps. | Timezone-aware formats; documented UTC rules. | Yes: UTC with `Z` in records, logs, reports. |
| RFC 8785 (JCS) | JSON is hashed or signed. | Canonicalise before hashing or signing. | Future (M1): reports and custody log. |

## Interfaces and portability matrix

| Standard | Applies when | Required engineering posture | Ridge |
| --- | --- | --- | --- |
| IEEE 1003 / ISO/IEC 9945 - POSIX | Portable Unix behaviour. | Isolate non-portable extensions; test on target OS. | Partly: Linux and macOS file semantics; Windows handled separately (path length, reserved names, sharing modes). |
| ISO/IEC 23360 - LSB | Linux binary compatibility contracts. | Respect packaging constraints. | No. |

## Testing and verification matrix

| Standard | Applies when | Required engineering posture | Ridge |
| --- | --- | --- | --- |
| ISO/IEC/IEEE 29119 | Substantial testing. | Test process, levels, techniques, documentation and completion criteria proportionate to risk. | Yes. |
| IEEE 829 | Legacy contracts. | Map to 29119 artifacts. | No. |
| IEEE 730 | SQA process required. | QA responsibilities, reviews, audits, nonconformance handling, release quality records. | Yes for the Ops gate. |
| IEEE 1012 | Independent V&V required. | V&V scope, independence, methods, criticality, anomaly resolution. | Yes for method validation. |

## Biometric data standards

| Standard | Edition (see `references.md`) | Ridge | Notes |
| --- | --- | --- | --- |
| ISO/IEC 39794-4 Finger image data | 2019 + Amd 1:2023, under review | Future (M3), candidate export | Extensible binary (ASN.1) and XML encodings; Amd 1 improves interoperability with ANSI/NIST-ITL. |
| ISO/IEC 39794-2 Finger minutiae data | 2023 (Amd 1 in development) | Future (M3, minutiae) | Only if minutiae are exported. |
| ISO/IEC 19794-4 Finger image data | 2011 + Amd 1:2013 + Amd 2:2015, confirmed 2024 | Future (M3), candidate | Legacy format if the AFIS requires it. |
| ISO/IEC 19794-2 Finger minutiae data | Not verified | Future | Legacy minutiae format. |
| ANSI/NIST-ITL 1 | 1-2025 (SP 500-290e4) current; 1-2011 Update 2015 (SP 500-290e3) previous | Future (M3), candidate | Edition, record type and compression must be agreed with the national AFIS vendor (open question). |
| ISO/IEC 29794-4 + NFIQ 2 | 29794-4:2024; NFIQ 2.3.0 | Future (M2) | Nominal scope is contact captures at 500 ppi; on photo-derived images scores are indicative only. NFIQ 2 uses a trained model (AI Act trigger). |
| ISO/IEC 24745 Biometric information protection | 2022 | Yes | Confidentiality and integrity apply; renewability/revocability of references does not (no enrolment templates). |
| ISO/IEC 19795-1 Performance testing | 2021, to be revised | Yes (validation) | Benchmark design and reporting. |
| ISO/IEC 30107 Presentation attack detection | 30107-1:2023 | Mostly No | PAD addresses attacks at a capture device during enrolment or verification. Ridge has no capture subsystem and makes no verification decision. Manipulated or synthetic case photos are an evidence-authenticity question for the laboratory (ISO/IEC 27037/27042). Trigger: Ridge used to capture live fingers. |

## Forensic science and digital evidence standards

| Standard | Edition | Ridge | Applies to |
| --- | --- | --- | --- |
| ISO/IEC 17025 | 2017, confirmed 2023 | Yes (laboratory accreditation context) | 7.2.2 validation of methods; 7.5 technical records; 7.6 measurement uncertainty; 7.11 control of data and information management (software validation); 8.4 control of records. |
| ISO 21043-1 Vocabulary | 2025 | Yes | Terminology in docs and UI. |
| ISO 21043-2 Recognition, recording, collecting, transport, storage | 2018, to be revised (DIS in progress) | Yes | Evidence immutability, storage, custody. |
| ISO 21043-3 Analysis | 2025 | Yes | Ridge is an analysis aid; records of what was done. |
| ISO 21043-4 Interpretation | 2025 | Partly | Ridge does not interpret; it must not present outputs as opinions. |
| ISO 21043-5 Reporting | 2025 | Partly | Job reports are technical records supporting the examiner's report. |
| ENFSI Best Practice Manual for Fingerprint Examination | Edition not verified | Yes | ACE-V framing; laboratory procedure. |
| ISO/IEC 27037 | 2012 | Partly | Preservation and hashing of digital originals (case photos). |
| ISO/IEC 27041 | 2015 | Yes | Assurance that the method is fit for purpose (validation). |
| ISO/IEC 27042 | 2015 | Yes | Analysis of digital evidence: repeatability, reproducibility, records. |
| ISO/IEC 27043 | 2015 | Partly | Investigation process context. |

Rules implementing these: `forensic_evidence_and_biometric_data_standards.md`.

## Privacy and legal (to be confirmed by the DPO/legal)

| Instrument | Ridge | Engineering consequences |
| --- | --- | --- |
| Directive (EU) 2016/680 (LED) | Yes: case processing is law-enforcement processing | Biometric data for identification purposes is a special category (Art. 10, "strictly necessary" with safeguards); data protection by design and default (Art. 20); logging of processing operations (Art. 25) supported by the custody log; DPIA (Art. 27) and possibly prior consultation (Art. 28); security of processing (Art. 29); breach handling (Art. 30-31). Ridge makes no automated decision (Art. 11). Article references not re-verified online on 2026-10-16. |
| ZVOPOKD (Slovenia) | Yes | Act on the Protection of Personal Data in the Field of Criminal Offences, Uradni list RS 177/2020. Article-level obligations to be mapped by the DPO/legal. |
| GDPR (EU) 2016/679 and ZVOP-2 | Only non-LED processing | Likely relevant to the volunteer validation set (legal basis, explicit consent, DPIA); DPO to decide. |
| EU AI Act, Regulation (EU) 2024/1689 | Assessed as likely not applicable today | Ridge uses hand-designed deterministic signal processing (FFT, Gabor filters, Otsu threshold, morphology) with no learned parameters; the Act's AI-system definition centres on systems that infer outputs, and recital 12 excludes systems based on rules defined solely by natural persons. If a component were an AI system, Annex III use areas for biometrics and law enforcement make a high-risk classification plausible. Reassess before adding NFIQ 2 (trained model), ML minutiae extraction, learned enhancement or any matching. Application dates were reportedly amended in 2026 ("Digital Omnibus"; not verified). Legal to confirm. |

## Conflict and exception process

1. Prefer the stricter rule when multiple applicable standards overlap.
2. Never waive a security, forensic, privacy, or compliance requirement silently.
3. Record each exception in `Project_Standards_Profile.md` section 8 with standard, rule/control, reason, risk, compensating control, owner, approval, expiration date, and follow-up task.
4. Revisit exceptions before release and during maintenance.
5. If a standard requires accredited processes, independent review, or formal assessors, the profile identifies the process and the owner.

## Minimum standards evidence package

For every substantial release, maintain:

- Standards profile and this matrix.
- Requirements, acceptance criteria, and traceability links (`docs/prd.md`).
- Architecture, threat model and ADRs for high-risk components (`docs/architecture.md` including its ADR table).
- Code review evidence.
- Output of `python tools/gate.py all` for the release commit (and the GUI gates from M4).
- Security evidence for the ASVS chapters, Top 10 categories and CWE classes mapped above.
- Determinism and golden characterization results.
- From M1: custody and report integrity test results. For the Ops gate: approved validation report, DPIA and AI Act assessment references.
- Release readiness checklist and handoff with unresolved risks and exceptions.
