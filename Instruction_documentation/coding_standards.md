# Coding Standards

Last verified: 2026-10-16
Default coding standard for Ridge. Project tooling configuration (`pyproject.toml`, lock files, `tools/gate.py`) may be stricter but must not be weaker without a documented exception in `Project_Standards_Profile.md`.

## Universal coding rules

- Prefer simple, explicit, readable code over clever abstractions.
- Keep source files around 300 lines (soft limit; over 400 needs a reason in review). Keep functions around 50 lines and cyclomatic complexity at most 10. Split by responsibility before adding behaviour.
- Keep entrypoints thin (about 20-30 lines): `src/ridge/cli.py` handlers, `fingerprint_extract.py` (shim only), JSON-RPC handlers and Tauri commands delegate validation, logic and I/O to modules.
- Use strong typing, schemas and linter/type-checker enforcement everywhere.
- Validate and normalise external input before use: files, CLI arguments, environment, configuration, RPC requests, IPC payloads.
- Authorise every protected operation in a trusted layer (Python core or Tauri Rust core), never in the WebView.
- Encode output for its context (terminal, JSON, HTML in the GUI).
- Use parameterised queries if any SQL store is introduced.
- No global mutable state except explicit, documented process-wide settings applied once at startup (for example OpenCV thread count).
- Make failure behaviour explicit. Never return success from a failed operation. Never weaken validation, logging or integrity checks to pass tests.
- Add dependencies only with a written reason (see supply chain below).

## Python profile

| Item | Rule |
| --- | --- |
| Version | `requires-python >= 3.12`; development on 3.13; full CI matrix per `docs/prd.md` NFR-5 (3.12, 3.13, 3.14) for every release, pull requests on 3.12 (`.github/workflows/ci.yml`). Since October 2026 3.13 receives security fixes only. |
| Style | PEP 8 enforced by `ruff format` (check mode in CI). |
| Docstrings | PEP 257 for every public module, class and function. State units (original-image pixels vs working-scale pixels), dtype, shape and value range of array arguments and results. |
| Typing | PEP 484; `mypy --strict` with `warn_unreachable` and error codes `ignore-without-code`, `redundant-expr`, `truthy-bool`. Every `# type: ignore[code]` carries a reason. No `Any` in public signatures. |
| Arrays | `numpy.typing.NDArray[np.float32]` / `NDArray[np.uint8]` / `NDArray[np.bool_]`; dtype explicit on creation. Where OpenCV stubs are incomplete, wrap calls in typed helpers in `src/ridge/pipeline/imgutil.py` instead of disabling checks for the module. |
| Data types | Frozen dataclasses (`@dataclass(frozen=True, slots=True)`) for parameter sets and results; `enum.Enum` or `Literal` for modes; `Final` for constants. Functions with more than 6 parameters take a parameter object. |
| Lint | ruff with at least: `E`, `W`, `F`, `I`, `N`, `UP`, `B` (bugbear), `S` (bandit rules), `A`, `C4`, `C90`, `SIM`, `RET`, `PTH`, `PL`, `PERF`, `RUF`, `BLE` (blind except), `TRY`, `EM`, `NPY`, `D`, `ERA`, `T20`, `DTZ`, `G`, `LOG`, `PIE`, `PT`, `ARG`, `ISC`. `S101` (assert) is allowed only in tests. Every `# noqa: <code>` carries a reason. |
| SAST | bandit through `python tools/gate.py sast`, in addition to ruff `S`. |
| Printing | Library code does not print. Only `src/ridge/cli.py` writes to stdout/stderr. |

Other artifacts:

| Language or artifact | Rule |
| --- | --- |
| JSON | ECMA-404; no comments or trailing commas; schema-validated at trust boundaries. |
| TOML | `pyproject.toml` and configuration; parsed with `tomllib`. |
| SQL (only if SQLite is chosen for the case store) | ISO/IEC 9075 principles, SQLite dialect documented; parameterised only; see `backend_database_rls_rpc_standards.md`. |
| Shell | Avoid; write tooling in Python (`tools/`). Where unavoidable in CI: `set -euo pipefail`, quoted variables, shellcheck clean. |
| C, C++, C#, other | Not used in project code. Adding one requires a profile update and the rules in `standards_applicability_and_compliance_matrix.md`. |

## Errors (no bare except, no swallowing)

- Typed errors live in `src/ridge/errors.py`, with one base class and distinct classes for at least: unreadable or unsupported input, input over limits, processing failure (no finger, no ridge pattern, ridge period too small), unsafe or existing output, integrity failure, configuration error. `errors.py` is authoritative for names.
- Forbidden: bare `except:`; `except Exception` or `except BaseException` anywhere except the outermost CLI or RPC boundary; `except ...: pass`; returning `None` to signal failure where an error is meant.
- At the outer boundary the error is mapped to an exit code or typed RPC error, reported to the examiner, and counted; processing of other files may continue, but the final exit code reflects every failure.
- Chain causes with `raise NewError(...) from exc`. Messages state what failed and what the examiner can do; they never contain pixel data, keys or passphrases.
- No decoder fallback chains: choose the decoder from the content-detected, allow-listed format before decoding. If that decoder fails, the input fails (the legacy Pillow-then-OpenCV fallback is a known defect).
- Warnings that indicate risk (for example Pillow `DecompressionBombWarning`) are turned into errors.
- Distinguish validation, limit, not-found, conflict (output exists), integrity, dependency and unexpected failures. Retries, where any exist (sidecar restart), are explicit and bounded; mutating operations are not retried automatically.

## Safe file handling

Inputs:

- Open originals read-only (`"rb"`), check size with `os.fstat` against the byte limit before reading, read once into memory, hash those bytes, and decode from the same bytes (`io.BytesIO`). Hashing and decoding the same buffer removes time-of-check/time-of-use gaps (CWE-367).
- Detect the format from content with `PIL.Image.open(fp, formats=[...])` and an explicit allow-list (today: JPEG, PNG, TIFF, BMP, WEBP, and HEIF/HEIC through pillow-heif when installed). EPS, PDF, PSD, ICNS and any other format are rejected. A mismatch between extension and detected format is reported.
- Enforce limits before full decode: file bytes, width, height, total pixels (`Image.MAX_IMAGE_PIXELS` set to the project limit), frame count (multi-frame files rejected unless a frame is chosen explicitly), and memory budget for working arrays. Limits come from configuration with hard maximums in code.
- Never follow input paths from untrusted metadata; directory scans list only regular files with allow-listed extensions, sorted deterministically.

Outputs:

- Build output paths with `pathlib` from validated components; resolve and verify containment in the output directory; refuse symlinked targets (CWE-59) and output directories inside input directories.
- No silent overwrite, atomic publish: write to a temporary file in the destination directory, flush and `os.fsync`, then publish with an operation that fails if the target exists (for example `os.link` and then removing the temporary file). This avoids the race of checking for an existing file and then calling `os.replace` (CWE-367). `os.replace` / `Path.replace` are allowed only (a) when the examiner passed `--overwrite` (`docs/prd.md` FR-11, outside the case store), with the replaced file's hash recorded, and (b) for content-addressed case-store objects whose name is the hash of their content. Implementation: `src/ridge/image_io.py`.
- Output names derived from input stems must be unique; a collision (`a.jpg` and `a.png`) is an error or is resolved deterministically as defined in `docs/architecture.md`, never by overwriting.
- New files and directories get restrictive permissions (POSIX `0o600` / `0o700`; inherited ACLs on Windows documented).
- No temporary files outside the destination directory or case store.
- Windows: support non-ASCII and long paths; reject reserved device names and control characters in generated names.

Serialisation and processes:

- No `pickle`, `marshal` or `shelve` for anything that crosses a trust boundary; `numpy.load(..., allow_pickle=False)` always.
- JSON with stdlib `json`; reject `NaN`/`Infinity` on trust-boundary input; canonical RFC 8785 form where hashed or signed. TOML with `tomllib`.
- `subprocess` only with argument lists, absolute executable paths, `shell=False`, timeouts and captured output. No `eval`, `exec`, or dynamic imports of computed names.

## Numerics and determinism (IEEE 754)

- Image arrays in the pipeline are `float32` unless a module documents why `float64` is needed (spectral power and long sums may use `float64`). Casts are explicit; do not rely on implicit NumPy type promotion.
- Every division has a documented epsilon or guard; stage outputs are checked finite in tests; NaN or Inf never reaches an output file.
- Every OpenCV call states interpolation and border mode explicitly (some legacy `cv2.resize` calls rely on defaults).
- Method constants (working ridge period 12 px, 16 Gabor orientations, quality defaults, morphology sizes) are named, documented and defined in one place. Changing one is a method change (`forensic_evidence_and_biometric_data_standards.md` section 6).
- No unseeded randomness; random generators only in tests and synthetic-data generators with fixed seeds (`numpy.random.default_rng(seed)`).
- OpenCV thread count is set once at startup (`cv2.setNumThreads`) and recorded. The default is 1 unless the determinism test proves bit-identical results for the higher count. No threads or processes inside one image's pipeline; batch parallelism across files only if results are independent and outputs and records are ordered deterministically.
- Comparisons: integer and binary outputs exactly; floats with `numpy.testing.assert_allclose` and explicit tolerances. Default same-platform tolerance for float32 intermediates: `rtol=1e-5`, `atol=1e-6` on values normalised to order 1. Same-architecture tolerances (different CPUs) are set and justified in `docs/architecture.md` §11 and approved by the Quality/Release Owner; gates never compare results across CPU architectures.

## Secure coding requirements

Aligned with NIST SSDF, ISO/IEC 27034, OWASP ASVS 5.0.0, OWASP Top 10:2025 and the 2025 CWE Top 25 (mapping in `standards_applicability_and_compliance_matrix.md`).

- Treat files, metadata, CLI arguments, environment, configuration, RPC/IPC payloads and dependency outputs as untrusted.
- Least privilege for processes, files, CI tokens and GUI capabilities.
- Block path traversal, injection (command, SQL, template), unsafe deserialization and, in the GUI, XSS through design and tests. SSRF, CSRF and redirects are not applicable while Ridge has no network code.
- Secrets never in source, logs, argv, environment variables, fixtures or docs (`environment_configuration_and_secrets.md`).
- Cryptography only through reviewed libraries selected by ADR (candidates: pyca/cryptography, argon2-cffi). No custom cryptography, token formats or signing schemes.
- Randomness for keys, nonces and identifiers from `secrets` or `os.urandom`. Compare secrets and MACs with `hmac.compare_digest`.
- Python cannot reliably erase memory: keep key material in short-lived `bytearray` objects, overwrite on release as best effort, never log or repr them, and document the residual risk.
- Neutralise control characters in any untrusted string written to a terminal or log (CWE-150).
- Map recurring findings to CWE and add a regression test.

## TypeScript, React and Rust profile (GUI, M4)

Summary; full rules in `desktop_gui_tauri_standards.md`:

- TypeScript `strict` plus `noUncheckedIndexedAccess` and `exactOptionalPropertyTypes`; ECMA-262 target per supported WebView; ESLint type-checked rules; no `any`, `eval`, `dangerouslySetInnerHTML`.
- React UI holds no security logic; IPC types generated or checked against the Rust/JSON-RPC schema.
- Animation with Motion (`motion/react`) from the published npm package, respecting `prefers-reduced-motion`, never delaying LCP.
- Rust: `forbid(unsafe_code)`, Clippy with `-D warnings`, no `unwrap`/`expect` on untrusted paths, `serde(deny_unknown_fields)`, `cargo audit`, `cargo deny check`.

## Maintainability and modularity

- One primary reason to change per module; dependency direction `cli`/`sidecar` -> application services -> `pipeline` and `image_io`; `pipeline` never imports CLI, I/O, case store or GUI code.
- No circular imports; no star imports; explicit `__all__` in package `__init__` files.
- Remove dead code instead of keeping unused paths.
- Generated code is never mixed with hand-written code in one file.

## Data, time, text

- Timestamps are timezone-aware UTC (`datetime.now(timezone.utc)`), serialised as ISO 8601 with `Z`. Naive datetimes are forbidden (ruff `DTZ`).
- Text files are UTF-8. File names are handled as `pathlib.Path`, never re-encoded. Normalise text (NFC) only where identity comparison depends on it and document it.
- JSON is ECMA-404 valid; schemas validated at trust boundaries.

## Dependency and supply-chain rules

- Runtime dependencies pinned with hashes in `requirements.lock`, development tools in `requirements-dev.lock` (pip-tools, `--generate-hashes`); install with `pip install --require-hashes`. The legacy `requirements.txt` with `>=` ranges is replaced by the lock files.
- Every new dependency needs a note in the pull request or an ADR: purpose, license, maintenance status, native code, whether it touches class E data. Dependencies with native decoders get the fuzzing and limit rules above.
- `python tools/gate.py deps` (pip-audit), `licenses` (allow-list for proprietary internal distribution) and `sbom` (CycloneDX) pass before release. Bundled native libraries count: pillow-heif wheels ship libheif and codec libraries whose licenses (LGPL, possibly GPL for an encoder) need explicit review; legal to confirm.
- GitHub Actions pinned by full commit SHA; OpenSSF Scorecard tracked.
- No install-time downloads, git dependencies or URL dependencies.

## Documentation in code

- Comments explain why, risks, invariants and standards rationale. Cite the method source where an algorithm follows literature (for example Hong, Wan and Jain 1998 for the Gabor filter bank).
- No stale comments, misleading TODOs or undocumented deviations; a TODO references an issue.

## Git and review rules

- Focused, reviewable changes; refactors separate from behaviour changes. The `src/` refactor must keep golden outputs identical.
- Never commit secrets, real images or other class E data (`forensic_evidence_and_biometric_data_standards.md` section 11).
- Include tests with behaviour changes and golden-array updates only with an ADR-backed method change.
- Review covers security, forensic impact, determinism, tests and unchanged behaviour.

## Forbidden practices without an approved exception

- Security or authorisation decisions in the WebView.
- Dynamic code execution from untrusted input.
- Building SQL, shell commands, file paths, regexes or HTML from untrusted strings without safe APIs and tests.
- Logging secrets, pixel data or unnecessary personal data.
- Swallowing exceptions; decoder fallback chains.
- Overwriting outputs or touching originals.
- Unbounded decoding or allocation driven by file content.
- Disabling linter, type-checker or SAST rules without a written reason.
- Releasing with failing gates, missing standards evidence or undocumented exceptions.
