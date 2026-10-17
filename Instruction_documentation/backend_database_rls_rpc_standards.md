# Case Store, Custody Log And Data-Access Standards

Last verified: 2026-10-16
The file name is kept for cross-references. For Ridge it covers the encrypted per-case store (planned `src/ridge/case/`, M1), the custody log storage (planned `src/ridge/custody/`), and every data-access path. Authoritative design: `docs/architecture.md` section 8 (current proposal, ADR-008: per-case directory of files with AES-256-GCM encrypted, content-addressed blobs and a JSONL custody log; SQLite is the alternative if querying needs grow). Rules below apply to either design; SQL rules apply only if SQLite is chosen.

Status: not implemented. Interim control until M1: OS full-disk encryption and examiner discipline (`Project_Standards_Profile.md` section 8).

## Core rule

All reads and writes of case data go through the Python core's case-store API. The WebView, the Rust core, scripts and examiners' file managers never read or modify case-store files directly. UI restrictions help usability; they are never the control.

## Standards posture

- ISO/IEC 9075 principles for SQL (SQLite dialect documented).
- OWASP ASVS 5.0.0 V2, V5, V11, V14, V15, V16; CWE-89, CWE-22, CWE-312, CWE-323, CWE-367, CWE-532.
- ISO/IEC 24745 (confidentiality and integrity of biometric data); ISO/IEC 27001/27002 cryptography and logging controls (alignment only).
- LED Art. 20 (data protection by design), Art. 25 (logging), Art. 29 (security), to be confirmed by the DPO/legal.
- Forensic rules in `forensic_evidence_and_biometric_data_standards.md` (immutability, hashing, custody, retention).

## Access rules

- Single examiner per workstation. Access to a case requires the OS account (OS keystore layer) and the examiner passphrase (Argon2id layer); key custody details in `environment_configuration_and_secrets.md`.
- Cases are locked by default and after inactivity (GUI, M4). No administrator bypass, no master passphrase in code.
- Deny by default: every API call checks case state (exists, unlocked, not under deletion) before acting.

### RLS, RBAC and tenancy

Not applicable to Ridge today: there is one examiner per workstation and no shared store. Becomes applicable if a laboratory server, shared case repository or multi-user mode is added. In that case restore the full pack rules before design: deny by default, server-side role/owner/tenant checks, policies for every operation, denial tests for anonymous, wrong-role, wrong-owner and cross-tenant access, no client-controlled authorization fields, audit of every security-relevant change.

## Storage layout rules

- Per-case directory with: encrypted case metadata (case reference, legal basis, retention date, legal-hold flag), key file (wrapped data keys, KDF parameters, no plaintext keys), encrypted evidence and artefact blobs, signed reports, custody log, single-writer lock.
- Blob contents (originals, outputs, debug images, exports staged inside the store) are encrypted with AES-256-GCM under the per-case data key: 96-bit nonces generated randomly per encryption and never reused under the same key; associated data binds case ID, blob ID, blob type and format version; the authentication tag is verified before any plaintext is used.
- Blob names are random IDs or content hashes. Content-addressed names reveal whether a known image is present in a store and whether two cases share an image; the ADR records whether that is acceptable or whether names are keyed (for example HMAC with a case key).
- Class C metadata (original file names, case reference, examiner identity) is encrypted at rest. Plaintext is allowed only where independent verification needs it (signed reports, custody log), and then it is minimised: no original file names, actor as account and workstation IDs; any case reference in plaintext reports is confirmed by the DPO.
- The plaintext SHA-256 of every blob is recorded and re-verified on read; a mismatch is an integrity failure (custody entry, processing stops).
- Atomic writes for every store file (`coding_standards.md`, safe file handling); no plaintext temporary files.
- If SQLite is chosen: journal and WAL files can retain old page content; the ADR addresses journal mode and `secure_delete`.

## SQL and migration rules (if SQLite is chosen; format-version rules always apply)

- Parameterised statements only; no string-built SQL; `PRAGMA foreign_keys = ON`.
- Multi-step changes in one transaction together with their custody entry.
- Schema version recorded in the database (for example `PRAGMA user_version`); migrations are versioned code, deterministic, tested on fixture stores built from synthetic data, and logged as custody events.
- Before a migration, a verified backup of the encrypted case exists; failed migrations leave the case readable in its previous version.
- Old case formats open or fail with a typed, explained error; they are never silently rewritten.

## Case-store API rules

- Small cohesive functions per operation (create, unlock, lock, ingest, process, export, set or release legal hold, retention action, delete, verify).
- Inputs validated; outputs minimal (handles, hashes, metadata the caller needs).
- Every mutating operation writes its custody entry or fails as a whole.
- The API never returns keys, wrapped keys or passphrase-derived material.

## Mutation paths

- WebView: never mutates; it requests through Tauri commands and the sidecar (`edge_function_standards.md`).
- CLI and library: may write outputs outside the store only through the export rules below; once the case store exists, casework processing goes through the store.
- Scripts and manual edits of store files are forbidden; integrity verification detects them.
- Inventory and risk review of every write path: `direct_mutation_authorization_audit.md`.

## Exports

- An export creates plaintext class E data outside the store. It requires an explicit examiner action, a destination outside any input directory, the forensic labels, a custody entry with output hashes, and a warning that the exported file is no longer protected by the store.
- Export formats follow the AFIS decision (open question; `standards_applicability_and_compliance_matrix.md`, biometric section).

## Custody log storage

- Stored with the case, append-only. If kept in SQLite, triggers abort `UPDATE` and `DELETE` on custody rows as defence in depth; the hash chain and signatures are the actual control.
- Verification reads the full chain and fails closed (`forensic_evidence_and_biometric_data_standards.md` section 5).

## Retention, legal hold, deletion, backup

- Retention date and legal hold live in the encrypted case metadata; legal hold blocks every deletion path.
- Deletion is crypto-erasure (destroy wrapped data keys, then ciphertext) plus a retained deletion record.
- Backups contain only ciphertext, the key file (wrapped keys only) and signed records. Key recovery when the OS keystore is lost is an open decision for the Security Owner and the Forensic Quality Manager (with both layers required, losing the OS profile means losing the case unless a recovery mechanism is designed); record it in an ADR before M1.

## Audit fields

Each custody entry or audit record captures: actor (OS account, examiner ID), case ID, action, target object IDs and hashes, previous and new state where relevant, UTC ISO 8601 timestamp, request ID (sidecar), result or failure category, Ridge version. No secrets, pixel data or unnecessary personal data.

## Case-store release checklist (M1 onwards)

- Encryption, nonce and AAD rules tested, including tampered ciphertext, swapped blobs and wrong case key.
- Lock/unlock with wrong passphrase, missing keystore entry and corrupted case metadata or key file handled with typed errors.
- Migrations tested on synthetic fixture stores; recovery path documented.
- Custody entries written for every mutation; verification passes on valid stores and fails on tampered ones.
- Retention, legal hold and crypto-erasure tested.
- No plaintext class E or class C data found on disk after a full synthetic workflow (scan of the case directory and temp directories).
- Evidence recorded in the release handoff.
