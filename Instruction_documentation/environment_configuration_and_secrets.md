# Environment Configuration And Secrets

Last verified: 2026-10-16
Covers Ridge's runtime configuration on offline examiner workstations, passphrases and keys, signing keys, and CI secrets for GitHub Actions. Authoritative key and storage design: `docs/architecture.md` and `docs/adr/`.

## Standards posture

- ISO/IEC 27001/27002 (cryptography, access control, logging, change management) as alignment; ISO/IEC 27034; NIST SSDF.
- OWASP ASVS 5.0.0 V11 (cryptography), V13 (configuration), V14 (data protection); CWE-798 (hard-coded credentials), CWE-214 and CWE-526 (secrets in process arguments or environment), CWE-312, CWE-532, CWE-330.
- RFC 9106 (Argon2), AES-GCM and Ed25519 as specified in their NIST/IETF documents (see `references.md`).

## Core rules

- Ridge has no network secrets: no API keys, tokens, provider credentials or service URLs exist at runtime. Adding any requires a profile change.
- Secrets (passphrases, data keys, signing private keys) are never committed, logged, printed, placed in argv, environment variables, configuration files, run records, reports, crash output, screenshots or test fixtures.
- Configuration is read through one typed module, validated at startup, and fails fast with a typed error when invalid.
- Defaults are safe; missing optional configuration falls back to defaults, never to weaker behaviour.
- The effective configuration (no secrets) is recorded in every run record.

## Configuration sources and precedence

Lowest to highest: built-in defaults in code, configuration file, `RIDGE_*` environment variables, CLI flags.

- Security and resource limits have hard maximums in code. A value above the hard maximum is rejected. A value above the default but within the hard maximum is accepted, recorded and reported as a warning.
- Method parameters (for example `--min-quality`, `--period`, `--flip`, `--no-crop`) are always recorded with their source.
- Configuration file: TOML parsed with `tomllib`, unknown keys rejected. Proposed locations: Windows `%APPDATA%\Ridge\config.toml`; macOS `~/Library/Application Support/Ridge/config.toml`; Linux `$XDG_CONFIG_HOME/ridge/config.toml`. A documented example file with safe values replaces the pack's `.env.example`; final name and location are defined with the configuration module.

## Environment variables (proposed)

The final list is defined by the configuration module and `docs/architecture.md`; this table is the starting point and must be updated when that module lands.

| Name | Purpose | Class | Required | Validation | Default |
| --- | --- | --- | --- | --- | --- |
| `RIDGE_CONFIG` | Path to the configuration file | I | No | Existing regular file, not a symlink | Per-OS location above |
| `RIDGE_LOG_LEVEL` | Log verbosity | I | No | `ERROR`, `WARNING`, `INFO`, `DEBUG` | `INFO` |
| `RIDGE_MAX_INPUT_BYTES` | Input file byte limit | I | No | Integer, at most the hard maximum | Code default |
| `RIDGE_MAX_PIXELS` | Decoded pixel limit | I | No | Integer, at most the hard maximum | Code default |
| `RIDGE_CASE_ROOT` (M1) | Root directory for case stores | C (path may reveal case names) | No | Absolute path on a local volume | Per-OS data directory |

Never introduced: any variable carrying a passphrase, key, token or anything that weakens a control (no "disable checks" or "skip hashing" switches). Overwriting outputs is possible only with the explicit per-run CLI flag `--overwrite` (`docs/prd.md` FR-11), never through configuration or environment.

## Passphrase handling (M1)

- CLI: read with `getpass` from the terminal only; refuse when stdin is not a terminal. Non-interactive unlocking is not supported unless an ADR defines a safe mechanism.
- GUI: password field in the WebView, sent once through the dedicated unlock command and sidecar method; never stored in WebView storage or state after submission.
- Policy set by the Security Owner; `docs/architecture.md` section 9.3 proposes the NIST SP 800-63B approach: at least 15 characters, no composition rules, checked against an offline breached-password list where available; no hints, no recovery questions.
- Failed unlock attempts are slowed by the KDF cost plus an increasing delay and are recorded as security events.

## Key custody (M1)

- Each case has a random 256-bit data key from `secrets.token_bytes` or `os.urandom`.
- The data key is protected by two factors, both required: a key derived from the examiner passphrase with Argon2id, and a device secret held in the OS keystore (Windows DPAPI in the user scope, macOS Keychain, Linux Secret Service). Construction: `docs/architecture.md` section 8.2 (ADR-004, HKDF combination; proposed, needs Security Owner approval). An optional sealed recovery key is a Security Owner decision.
- Argon2id parameters, salt (at least 128 bits) and format version are stored in the case key file (`keys.json` in `docs/architecture.md` section 8.1). Parameters are no weaker than RFC 9106's second recommended option (memory 64 MiB, 3 iterations, 4 lanes) unless a benchmark and ADR justify otherwise.
- AES-256-GCM nonces are 96-bit random values, never reused under one key; the key is rotated before the number of encryptions approaches the limit stated for random nonces in NIST SP 800-38D.
- Plaintext keys exist only in process memory for the shortest time (see Python memory caveat in `coding_standards.md`), never on disk.
- Key recovery when the OS keystore is lost is an open decision (`backend_database_rls_rpc_standards.md`).

## Report signing keys (M1)

- Ed25519 signing key per examiner per workstation, generated locally, private key protected like the data key (OS keystore plus passphrase).
- Key ID = SHA-256 of the public key; reports carry the key ID.
- Public keys are registered with the Forensic Quality Manager (registry outside Ridge) so reports can be verified on any workstation.
- Rotation, revocation and suspected compromise are custody events; reports signed after a compromise date are flagged by verification.

## Release signing keys

- Separate from report keys; held by the Quality/Release Owner.
- Releases are signed outside CI on a controlled machine, or in a protected GitHub environment with required reviewers; the choice is recorded in an ADR.

## Provider configuration

Not applicable to Ridge today: there are no external providers, webhooks, callbacks, CORS origins or OAuth scopes. Becomes applicable if any network integration is added (requires a profile change).

## CI/CD (GitHub Actions) rules

- Every workflow declares minimal `permissions` (default `contents: read`; `security-events: write` only for CodeQL upload). No `id-token: write` unless needed for signing or attestations.
- Third-party actions pinned by full commit SHA; updates through reviewed pull requests.
- No `pull_request_target` workflows that check out untrusted code; forked pull requests get no secrets.
- Gates need no long-lived secrets. If the gitleaks GitHub Action is used under an organisation account it may need a license key secret (confirm); running the gitleaks binary through `python tools/gate.py secrets` avoids that.
- CI uses synthetic data only. Artifacts never contain class E data, secrets or environment dumps; short artifact retention.
- Branch protection: required gate checks, review before merge, no force pushes to the default branch.

## Logging rules

- Local only; no telemetry.
- Never log secrets, key material, pixel data or full paths of originals at default level; neutralise control characters.
- UTC ISO 8601 timestamps; structured fields; correlation via run ID or request ID.
- Security events (failed unlock, integrity failure, key events) are logged and, from M1, written to the custody log.

## Review checklist

- No secret in code, config examples, tests, logs, argv or environment (`python tools/gate.py secrets` clean).
- Configuration schema, defaults, hard maximums and the environment-variable table are current.
- Run records contain the effective configuration and no secrets.
- Key custody, passphrase and signing rules tested with test keys only.
- CI permissions minimal; actions pinned; no secrets exposed to forks.
- Standards profile and release checklist include required evidence.
