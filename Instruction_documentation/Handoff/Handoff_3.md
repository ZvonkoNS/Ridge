# Handoff_3.md

Date/time (ISO 8601 with offset): 2026-10-17T09:05+02:00
Author/agent: Claude Code (claude-opus-5-5), working autonomously under the owner's standing go-ahead (2026-10-17, 4-hour development window)
Project: Ridge
Branch: `m1-case-store` → PR into `main`
Base commit: `6384f7d` (merge of PR #1)
Latest commit: see the PR

## 1. Scope

Requested change: continue development and deliver as many PRD features as possible. This handoff covers **M1 Evidence integrity** (PRD FR-20 to FR-27, SEC-3, SEC-4, SEC-9, PRIV-1 to PRIV-3).

Completed work, in a new package `src/ridge/case/` and a new CLI `ridge-case`:

| Module | What it does |
| --- | --- |
| `crypto.py` | AES-256-GCM envelope `RDG1`, HKDF sub-keys, HMAC-keyed file names |
| `keys.py` | Argon2id + OS-keystore device secret → KEK; `KdfParams` with enforced minimum; passphrase policy (≥ 15 characters); `KeyringKeyStore` |
| `identity.py` | Examiner Ed25519 identity, private key sealed under the identity KEK |
| `custody.py` | Encrypted, hash-chained, RFC 8785 canonical custody log; signed chain heads |
| `store.py` | Case create/open, single-writer lock, encrypted metadata, evidence import (validated, hashed, encrypted, source untouched), artefacts, controlled export, legal hold, sealed reports |
| `jobs.py` | Extraction jobs on stored evidence; signed JSON job report with environment, parameters, measurements, input/output hashes and a disclaimer |
| `verify.py` | Blobs, report signatures and hashes, signed heads, stray files |
| `dispose.py` | Crypto-erase with confirmation, legal-hold and retention checks; retained disposal record without personal data |
| `cli.py` | `ridge-case identity / init / import / extract / list / log / export / verify / hold / dispose` |

Also:

- The plain `ridge` command now prints an R&D-mode notice (FR-27).
- The licence gate reads runtime packages from `requirements.lock`.
- `.claude/` (agent worktrees) is ignored by git, ruff and gitleaks.

Out of scope or deferred:

- Recovery key (OQ-12).
- Out-of-band countersigning or timestamping (OQ-8).
- Per-examiner identities if OQ-9 requires them.
- M2 exports (being built in a parallel branch).

## 2. Current repository state

Git status summary: all M1 work is committed on `m1-case-store`. A parallel M2 branch (`m2-export`) is in progress in an agent worktree under `.claude/worktrees/`.

## 3. Standards applicability and evidence

Project standards profile updated: yes. The exceptions "Encrypted case store" and "Custody log and signed reports" are closed for casework.

| Standard/control/rule | Applies? | Evidence produced | Exception/deviation |
| --- | --- | --- | --- |
| OWASP ASVS 5.0 V11 (cryptography), V14 (data protection), V16 (logging) | Yes | `tests/test_case_crypto.py`, `tests/test_case_store.py`, `tests/test_case_cli.py` | Recovery (OQ-12) |
| CWE-311/312 (missing or cleartext storage) | Yes | Tests assert that no plaintext pixels, case reference or content hashes appear on disk | — |
| CWE-345/353 (integrity) | Yes | Tamper tests: flipped byte, deleted, swapped or planted file, altered custody line, report and signature | Tail truncation is only detectable up to the last signed head (R-5, OQ-8) |
| CWE-522 / NIST SP 800-63B | Yes | Passphrase ≥ 15 characters, Argon2id minimum enforced, never read from argv or the environment | Breached-password check not implemented (offline list needed) |
| ISO/IEC 27037/27042, ISO/IEC 17025 7.5/7.11 | Yes | Custody log, signed reports, reproducibility record per job | Validation (M5) |
| LED Art. 25 logging (to be confirmed) | Yes | `ridge-case log` exports the decrypted processing log (PRIV-3) | DPO confirmation (OQ-13) |

Standards checks or tools run (Windows x86-64, Python 3.13.5):

```bash
python tools/gate.py all
# docs, lint, format, typecheck: passed; test: 180 passed, 2 skipped, coverage 96.09%
python tools/gate.py lint format sast deps secrets licenses sbom   # after the bandit annotation: all 7 passed
```

Exceptions, deviations or evidence gaps:

- Disposal deletes files, but SSD remnants or backups of `case.json` could still hold the wrapped key (documented in `dispose.py` and architecture §8.2).
- The real OS keystore is exercised only through a fake `keyring` backend in tests; CI never touches a real keystore.

## 4. Forensic impact

- Output pixels changed: **no**. Jobs run the unchanged pipeline, and a test checks that the stored print equals a direct extraction.
- Defaults or recorded parameters changed: no.
- New records: job reports and custody entries (formats in architecture §8.3–8.4 and in `jobs.py` / `custody.py`).
- Examiner-facing wording: every report carries the disclaimer "Image enhancement only. Ridge does not identify anyone and draws no conclusions."

**Review follow-up (PR #2, automated Codex review of `c025ead`):**

| Finding | Change |
| --- | --- |
| P1 stripped final `chain.sign` passed verification | `verify` requires a signed head after every completed job (`unsigned_jobs`). Test: `test_stripped_signed_head_is_detected` |
| P1 disposal record written before the key was destroyed | The key is erased first (`erasing` stub), then the record is published, then files are deleted. Interrupted disposals are resumable. Test: `test_interrupted_disposal_never_leaves_a_readable_case` |
| P2 personal data in the disposal record | The record keeps the examiner key id and a reason code from a fixed list; no OS user name or free text |
| P2 unbounded stored Argon2 parameters | Upper bounds enforced and integer type checked before Argon2 runs (CWE-400). Test: `test_stored_kdf_parameters_are_bounded` |
| P2 `init` accepted a passphrase that cannot unlock the identity | `init` confirms the passphrase and unlocks the identity with it; one examiner passphrase for identity and cases |

## 5. Files changed

`src/ridge/case/*` (new), `src/ridge/errors.py` (case error types), `src/ridge/cli.py` (R&D notice), `tests/case_helpers.py`, `tests/test_case_{crypto,store,cli}.py` (new), `tests/test_cli.py`, `pyproject.toml` (dependencies, `ridge-case` script), `requirements*.lock`, `tools/gate.py`, `.gitignore`, `.gitleaks.toml`, `README.md`, `docs/prd.md` (v0.4), `docs/architecture.md` (§5, §6, §7.2, §8, §9.3, ADR-004/005/008 accepted), the standards profile, the write-path audit, and this handoff.

## 6. Data store, records and formats

Case-store format `ridge.case/1`, identity `ridge.identity/1`, job report `ridge.job-report/1`, disposal record `ridge.disposal/1`, envelope `RDG1` v1. There are no migrations (new feature). Write paths P1–P8 are implemented; the audit document has been updated.

## 7. Configuration, keys and CI

- New runtime dependencies (hash-pinned): `cryptography`, `argon2-cffi`, `keyring`, `rfc8785`, plus their transitive packages. Licences checked: MIT, MIT-0, BSD-3-Clause, Apache-2.0.
- Keys: one device secret per OS account (`keyring` service `ridge`), an identity KEK and a per-case KEK.
- CI: no workflow changes.

## 8. Security

- New trust boundaries: evidence import (bounded, allow-listed decoding before storage), passphrase input (`getpass` only), OS keystore.
- Threat-model notes: STRIDE rows in architecture §9.2 are now implemented for tampering, repudiation and information disclosure.
- Open security risks: no breached-passphrase check; no recovery key (availability risk); key rotation for identities is not implemented.

## 9. Tests

- Added: 16 crypto, key and identity tests; 21 store, custody, job, verify and disposal tests; 8 CLI tests.
- Tests not run: the real OS keystore (see §3); POSIX permission tests on Windows.
- Still missing: fuzzing of the custody-line parser.

## 10. Release readiness

Internal engineering build. Not ready for casework: owners, DPIA, validation (M5) and OQ-9, OQ-12 and OQ-13 are open.

## 11. Open risks and known issues

- The test suite now takes about 4 minutes locally, because of the Argon2id cost even at the minimum allowed parameters.
- `store.py` is about 300 lines; split it (for example, reports into their own module) before it grows.

## 12. Recommended next work

1. Merge M2 (`m2-export`) and wire comparison exports, 500 ppi output and NFIQ 2 into `ridge-case extract`.
2. Security Owner review of ADR-004/005/008 and OQ-9, OQ-12 and OQ-13.

## 13. First thing the next agent/developer should read or do

Run `python tools/gate.py all`, then read `src/ridge/case/store.py` and architecture §8.
