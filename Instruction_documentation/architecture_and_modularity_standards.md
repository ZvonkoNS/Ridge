# Architecture And Modularity Standards

Last verified: 2026-10-16
Architectural rules for Ridge. The concrete architecture, threat model and decisions are in `docs/architecture.md` (ADR table in section 13; individual files in `docs/adr/` when created), maintained outside this pack; where they are more specific, they win, but they may not weaken these rules without a recorded exception.

## Architectural principles

- Security and integrity by design: validation, limits, hashing, custody and key handling live in trusted layers (Python core, Tauri Rust core).
- Forensic by design: originals immutable, every output traceable to input hashes, parameters and version; no conclusions in software.
- Pure core: the image pipeline is a set of pure, deterministic array transformations with no file, network, clock or global-state dependencies.
- Separation of concerns: entrypoints, application services, pipeline, I/O, case store, custody, reports, exports and GUI are separable and testable alone.
- Single source of truth: one module owns each concept (limits, method constants, data-class rules, error types).
- Explicit state transitions for cases (created, locked, unlocked, under legal hold, deleted).
- Offline by design: no component opens network connections.
- Maintainability over cleverness.

## Quality attributes (ISO/IEC 25010)

| Attribute | Ridge meaning |
| --- | --- |
| Functional suitability | Correct ridge extraction within validated limits; no invented detail beyond documented behaviour. |
| Performance efficiency | Bounded memory per megapixel; predictable time per image on examiner hardware. |
| Compatibility | Windows 11, Linux, macOS; stable CLI and library API; versioned record formats. |
| Usability | Clear errors, visible parameters, original beside output, WCAG 2.2 AA in the GUI. |
| Reliability | Deterministic results, no partial outputs, consistent store after crashes. |
| Security | Least privilege, bounded decoding, encrypted store, signed records, no network. |
| Maintainability | Small modules, typed code, tests, ADRs. |
| Portability | Platform specifics isolated in `image_io` and keystore adapters. |

## Target layout

```text
src/ridge/
  __init__.py        Public library API
  __main__.py        `python -m ridge`
  cli.py             Thin argparse entrypoint
  errors.py          Typed errors
  image_io.py        Bounded, allow-listed decoding/encoding; atomic no-overwrite writes
  debug.py           Writing of intermediate images (class E)
  pipeline/
    imgutil.py       Typed helpers around OpenCV/NumPy primitives
    mask.py          Skin-colour finger mask (Lab a* + Otsu)
    period.py        Ridge period from local FFT
    gabor.py         Gabor bank and orientation-adaptive filtering
    quality.py       Ridge-quality map and region selection
    extract.py       Pipeline orchestration (pure)
fingerprint_extract.py   Backward-compatible shim calling ridge.cli.main
tests/                   pytest; synthetic data; tests/golden/*.npz
tools/gate.py            Named quality gates
```

Planned (roadmap; design in `docs/architecture.md`): `src/ridge/case/` (encrypted case store), `custody/` (hash-chained custody log), `report/` (signed JSON job reports), `export/` (matcher-ready 500 ppi exports), `quality/` (NFIQ 2 adapter), `minutiae/`, `sidecar/` (JSON-RPC over stdio); `gui/` (Tauri v2 + React + TypeScript).

Serverless or Edge Function structures from the generic pack are not applicable (no server components).

## Dependency rules

- Direction: `cli`, `sidecar` -> application services (`case`, `report`, `export`) -> `pipeline`, `image_io`, `custody`, `quality`.
- `pipeline` imports only NumPy, OpenCV and `ridge.errors`; it performs no I/O and reads no configuration directly (parameters arrive as typed objects).
- `image_io` is the only module that decodes or encodes image files.
- Only `case` reads or writes case-store files; only `custody` appends custody entries.
- `gui/` depends on the sidecar protocol, never on Python modules or the case-store format.
- Runtime code never imports `docs/`, `Instruction_documentation/` or `tests/`.
- No circular imports; checked in CI where tooling allows.

## File size and responsibility rules

- Files around 300 lines, functions around 50 lines, complexity at most 10 (`coding_standards.md`).
- Entrypoints (CLI handlers, JSON-RPC handlers, Tauri commands) about 20-30 lines.
- A module has one primary reason to change; split before adding behaviour. The 413-line legacy script is the motivating example.

## Architecture decisions

Record an ADR (row in `docs/architecture.md` section 13, or a file in `docs/adr/` once ADRs need more than a row) when a decision affects:

- Pipeline numerics, constants, defaults or output format (method change).
- Decoders, allow-listed formats, limits.
- Cryptography, key custody, case-store format, custody log format, report format.
- Export formats and AFIS interoperability.
- Sidecar protocol, Tauri capabilities, CSP, isolation pattern, packaging, update channel.
- Supported platforms, Python versions, native dependencies.
- Anything that changes standards applicability or forensic evidence.

Use IEEE 1016-style content for high-risk designs: context, stakeholders, views, rationale, interfaces, data, traceability.

## Domain rules

- Case, evidence item, processing run, output, report, export and custody entry are explicit domain types with IDs and hashes.
- Case state transitions are explicit and validated; deletion is a recorded transition, never a silent removal.
- History is append-only for custody, reports and key events.
- Method constants live in one module and are versioned with the method.
- No speculative abstractions without a current requirement in `docs/prd.md`.

## Boundary rules

- The WebView is untrusted; the Rust core and the Python sidecar validate everything they receive.
- Every cross-boundary payload (CLI arguments, configuration, files, JSON-RPC, IPC) has an explicit, versioned schema.
- JSON is ECMA-404 valid; hashed or signed JSON uses RFC 8785.
- Timestamps are ISO 8601 UTC; file names are Unicode paths passed through unchanged.
- External tools used in validation (matchers, NFIQ 2) are wrapped in adapters that isolate their formats and errors.

## Modelling and notation

- UML (ISO/IEC 19505) or BPMN (ISO/IEC 19510) where diagrams clarify the case workflow or custody flow; diagrams live in `docs/` and must match code and tests.
- Diagrams are not authoritative when they drift from code.

## Portability

- Supported: Windows 11, Linux, macOS. Platform-specific code (paths, permissions, keystore, hard links for atomic publication) is isolated in small adapters with tests on each platform's CI runner.
- Determinism is defined per platform (`forensic_evidence_and_biometric_data_standards.md` section 6).

## Safety and regulated architecture

No functional-safety standard applies. The forensic requirements take the equivalent role: deterministic, analysable pipeline; minimal dynamic behaviour; traceability from requirement (`docs/prd.md`) to design, code, tests and validation; independent review of method changes by the Forensic Quality Manager.

## Refactoring rules

- Characterize first: capture golden outputs and intermediates of the legacy script on synthetic inputs before moving code.
- Keep `fingerprint_extract.py` working as a shim with the same options and exit codes.
- Refactor structure and behaviour in separate commits; structural commits must leave golden results identical.
- Behaviour changes found necessary during the refactor (for example overwrite protection, decoder limits) are separate, tested, documented commits.

## Observability

- Local structured logs only; no telemetry, no remote error tracking.
- Custody log (M1) is the audit trail; logs are diagnostics.
- Logs never contain class E data or secrets; timestamps ISO 8601 UTC.
- Errors are categorised (input, limit, processing, output, integrity, configuration, unexpected).
