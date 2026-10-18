# ADR-012: Recovering the OS-keystore device secret

| Field | Value |
| --- | --- |
| Status | **Accepted** (2026-10-18) by the product owner, who also holds the Security Owner role on an interim basis (OQ-10). Option B is implemented: see Decision and implementation |
| Context | ADR-004 (two-factor key wrapping), store backups (architecture §8, `ridge-case backup`), OQ-9 |

## Problem

Every key-encryption key combines the examiner passphrase (Argon2id) with a 32-byte **device secret** that Ridge keeps in the operating-system keystore of the examiner's account. On Windows that is the Credential Manager entry `ridge / device-secret-v1`; on macOS it is the Keychain, and on Linux the Secret Service. The secret is created on first use and never leaves the keystore.

That is the second factor: a copied store is useless without the account. It also means:

- a store backup (`ridge-case backup`) cannot be opened on another account or machine, even with the passphrase;
- losing the account or its keystore (reinstall, profile corruption, a departed examiner) makes every case of that examiner unreadable. **Crypto-erasure by accident.** Signed reports and processing records that were exported stay verifiable; the encrypted evidence does not;
- court-ordered retention (FR-26, legal hold) cannot be guaranteed by backups alone.

## Options

| Option | How | For | Against |
| --- | --- | --- | --- |
| A. No recovery (today) | Document that a lost keystore loses the cases | Strongest against theft of backups; simplest | Accidental loss of evidence under legal hold; retention duty not met by backups |
| B. Recovery file sealed under a recovery passphrase | `ridge-case recovery export --to FILE` writes the device secret sealed with Argon2id + AES-256-GCM under a separate long recovery passphrase. The FQM or Security Owner keeps the file and passphrase apart, for example a sealed envelope plus a safe. `recovery import` restores it into a new account's keystore (logged) | Portable; no new infrastructure; split knowledge possible | A new high-value secret; the procedure must be followed; the import needs a custody record |
| C. IT-managed keystore backup | Rely on OS or enterprise mechanisms (roaming profiles, DPAPI domain backup keys, MDM keychain escrow) | No Ridge code | Opaque to Ridge; differs per platform; IT gains the second factor silently |
| D. Split the secret (Shamir k-of-n) | `recovery export` writes n shares, of which k recover the secret | No single holder can restore alone | More procedure and code; shares can still be lost |

## Recommendation (for the decision makers)

**Option B**, with these rules:

- the recovery passphrase meets the new-passphrase policy and is never the examiner's;
- export and import are explicit commands, each logged in a store-level audit file (cases cannot log it: none is open);
- the file says on its face what it is and that it holds no evidence;
- import refuses to overwrite an existing device secret;
- tests cover tampering, a wrong passphrase and refusal to overwrite.

Option D can be layered on later if split control is required.

Until a decision is made, Option A applies. The CLI, the GUI and the architecture already state that backups do not carry the device secret.

## Consequences if accepted

- New file format `ridge.device-secret-recovery/1` and two CLI commands (no GUI at first).
- Threat model: a stolen recovery file plus its passphrase plus a store backup reveals the cases. The examiner passphrase is still needed, so the recovery file replaces only the device factor.
- Release checklist: the laboratory documents where the recovery file and passphrase are kept, and who may use them.

## Decision and implementation (2026-10-18)

Option B, with the rules above. Implemented in `src/ridge/case/recovery.py` and `src/ridge/case/store_audit.py`:

- **`ridge-case recovery export --store S --to FILE`** needs the examiner passphrase, which must unlock the store's identity. It asks for a new recovery passphrase that meets the policy, is confirmed, and is not the examiner's. It writes `ridge.device-secret-recovery/1`:
  - a notice that the file holds one account's device secret and no evidence;
  - the key id and a fingerprint of the secret;
  - the Argon2id parameters and salt;
  - the secret sealed with AES-256-GCM. The key id, fingerprint and creation time are bound into the seal, so changing them breaks it.
- **`ridge-case recovery import FILE --store S`** opens the file with the recovery passphrase. It refuses if this account's keystore already holds a secret. Before anything is written, it checks that the secret unlocks the store's identity with the examiner passphrase, so a wrong file cannot lock an examiner out. If the import cannot be logged, it is undone.
- **`ridge-case recovery check FILE`** shows the key id, fingerprint and creation time without opening the file.
- Both export and import are logged in **`store-audit.jsonl`**. This hash-chained file holds store-level actions and is verified on every read.
- **Deviation from "no GUI at first":** the store screen also offers "Export recovery file..." and "Restore from a recovery file...". The installed application ships the GUI and its engine but not the `ridge-case` command line, so without the GUI a laboratory could not use recovery at all. Both passphrases are typed in the Rust prompt window (ADR-010); the first is held only in the Rust core, zeroised, until the second prompt uses it.
- Tests: `tests/test_recovery.py` covers:
  - restoring into a new account;
  - every refusal above;
  - tampering with each field;
  - a secret that does not match its fingerprint;
  - the audit chain;
  - the CLI and the sidecar methods.

  The GUI has Vitest tests (`recovery.test.tsx`), and the prompt rules have Rust tests.

The laboratory procedure (release checklist) must say where the recovery file and its passphrase are kept, apart from each other, and who may use them.

