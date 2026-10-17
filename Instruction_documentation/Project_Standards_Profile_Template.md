# Project Standards Profile Template

Last verified: 2026-10-16
Blank template kept for reuse. Ridge's filled profile is `Project_Standards_Profile.md`; update that file, not this one, for Ridge decisions.

## 1. Project identification

Project name:
Repository:
Product Owner:
Security Owner:
Quality/Release Owner:
Data Protection Officer:
Domain quality owner (for example Forensic Quality Manager for an ISO/IEC 17025 laboratory):
Last reviewed:

Unnamed owners are release blockers.

## 2. Product and deployment context

Product type:
Users and roles:
Deployment environments:
Network exposure at runtime: none / internal / public internet
Data classification (including special-category or biometric data):
Legal regime (for example GDPR, Directive (EU) 2016/680 and national transposition):
Customer, contractual or accreditation requirements:
Regulated domain: none / forensic science / automotive / aviation / medical / railway / nuclear / process industry / machinery / other
Safety classification, if any:
Milestones and operational gates:

## 3. Technology profile

| Area | Technologies used | Applicable standards |
| --- | --- | --- |
| Core library / CLI |  |  |
| Frontend / desktop GUI |  |  |
| Backend/API or sidecar |  |  |
| Serverless/Edge Functions |  |  |
| Database/storage |  |  |
| Native/embedded components (including third-party native libraries) |  |  |
| Scripts/tooling |  |  |
| Data formats/protocols |  |  |
| Operating systems/runtime |  |  |
| AI/ML components |  |  |

## 4. Applicable standards

| Standard or framework | Applies? | Edition/version (verified date and source) | Scope | Required evidence | Owner |
| --- | --- | --- | --- | --- | --- |
| ISO/IEC/IEEE 12207 |  |  |  |  |  |
| ISO/IEC/IEEE 15288 |  |  |  |  |  |
| ISO/IEC 25010 / 25000 series |  |  |  |  |  |
| ISO/IEC 27001 / 27002 |  |  |  |  |  |
| ISO/IEC 27034 |  |  |  |  |  |
| ISO/IEC 5055 |  |  |  |  |  |
| OWASP ASVS |  |  |  |  |  |
| OWASP Top 10 |  |  |  |  |  |
| CWE / CWE Top 25 |  |  |  |  |  |
| NIST SP 800-218 SSDF |  |  |  |  |  |
| NIST SP 800-53 |  |  |  |  |  |
| ISO/IEC/IEEE 29119 |  |  |  |  |  |
| IEEE 730 |  |  |  |  |  |
| IEEE 1012 |  |  |  |  |  |
| ISO/IEC 17025, ISO 21043, digital-evidence standards (ISO/IEC 27037/27041/27042/27043), if forensic |  |  |  |  |  |
| Biometric format, quality and protection standards (ISO/IEC 39794, 19794, 29794, 24745, 19795, 30107; ANSI/NIST-ITL), if biometric |  |  |  |  |  |
| Privacy and AI law (GDPR, LED and national law, EU AI Act) |  |  |  |  |  |
| Accessibility (WCAG / ISO/IEC 40500), if a UI exists |  |  |  |  |  |
| Domain-specific safety standard(s) |  |  |  |  |  |
| Language-specific standards |  |  |  |  |  |

## 5. Language and coding-standard selections

| Language | Language standard | Style/safety guide | Tooling | Required commands |
| --- | --- | --- | --- | --- |
| Python | Project Python version | PEP 8 / PEP 257 / PEP 484 / project guide |  |  |
| JavaScript/TypeScript | ECMA-262 / project TS version | Project ESLint/formatter |  |  |
| Rust | Toolchain and edition | Clippy, project lints |  |  |
| JSON | ECMA-404 (RFC 8785 where hashed or signed) | Schema validation |  |  |
| SQL | ISO/IEC 9075 + vendor dialect | Migration and data-access standards |  |  |
| C | ISO/IEC 9899 edition | MISRA/CERT/BARR-C/JPL if applicable |  |  |
| C++ | ISO/IEC 14882 edition | MISRA C++/CERT/HIC++/JSF AV C++ if applicable |  |  |
| C# | ISO/IEC 23270 / ECMA-334 / ECMA-335 | Project .NET analyzers |  |  |
| Other |  |  |  |  |

## 6. Security assurance level

- Verification baseline (OWASP ASVS level and applicable chapters):
- Threat model required: yes/no (location):
- SAST required: yes/no
- DAST or equivalent (fuzzing of parsers/IPC) required: yes/no
- Dependency audit required: yes/no
- Secret scanning required: yes/no
- SBOM required: yes/no
- Penetration test or independent security review required: yes/no
- Independent method/V&V review required: yes/no

## 7. Testing and verification evidence

| Test or verification type | Required? | Tool/command | Release blocker? | Evidence location |
| --- | --- | --- | --- | --- |
| Lint/format |  |  |  |  |
| Typecheck/compile |  |  |  |  |
| Unit tests |  |  |  |  |
| Integration tests |  |  |  |  |
| Contract/schema tests |  |  |  |  |
| Authorization/IPC/security tests |  |  |  |  |
| Hostile input and fuzz tests |  |  |  |  |
| Migration/format tests |  |  |  |  |
| Golden/characterization and determinism tests |  |  |  |  |
| E2E/smoke tests |  |  |  |  |
| Performance/reliability tests |  |  |  |  |
| Accessibility tests |  |  |  |  |
| Supply-chain scans |  |  |  |  |
| Standards conformance checks |  |  |  |  |
| Method validation / V&V or independent review |  |  |  |  |

## 8. Exceptions and deviations

| Standard/control/rule | Reason | Risk | Compensating control | Owner | Approval | Expiration/follow-up |
| --- | --- | --- | --- | --- | --- | --- |
|  |  |  |  |  |  |  |

## 9. Release evidence locations

Standards profile:
Requirements and traceability:
Threat model:
Architecture/design records:
Test reports:
Security scan reports:
Validation report / DPIA / legal assessments:
Migration or format evidence:
Release checklist:
Handoff:

## 10. Review cadence

Review this profile when:

- A new language, runtime, data store, external dependency, deployment target, platform or data class is added.
- A feature changes authentication, authorization, cryptography, evidence handling, privacy, safety or regulated behaviour.
- A trained model or other AI component is added.
- A contract, accreditation or legal assessment adds requirements.
- A release changes risk classification.
- A standards edition changes and the project can adopt it safely.
