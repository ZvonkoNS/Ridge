//! The passphrase prompt broker (ADR-010).
//!
//! A main-window command that needs the examiner passphrase registers what it is for, opens the
//! prompt window and waits. The prompt window submits the passphrase to the Rust core, which
//! sends it to the sidecar itself and passes only the non-secret result back to the waiting
//! command. The passphrase never reaches the main WebView, and Rust buffers holding it are
//! zeroised when dropped.

use std::path::PathBuf;
use std::sync::mpsc;
use std::time::Duration;

use serde::Serialize;
use serde_json::Value;
use tauri::AppHandle;
use zeroize::Zeroizing;

use crate::error::{ErrorKind, IpcError};
use crate::state;
use crate::{prompt_calls, windows};

const MAX_ATTEMPTS: u32 = 5;
const PROMPT_TIMEOUT: Duration = Duration::from_secs(10 * 60);
/// NIST SP 800-63B-style minimum for new passphrases (architecture §9.3; the sidecar enforces it too).
pub const MIN_NEW_CHARS: usize = 15;
const MAX_CHARS: usize = 1024;

/// A passphrase held between two prompts of one task (device-secret recovery, ADR-012).
/// Zeroised when dropped and never printed.
#[derive(Clone)]
pub struct Secret(Zeroizing<String>);

impl Secret {
    pub fn new(text: &str) -> Self {
        Self(Zeroizing::new(text.to_owned()))
    }

    pub fn expose(&self) -> &str {
        &self.0
    }
}

impl std::fmt::Debug for Secret {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str("Secret(<redacted>)")
    }
}

/// What the passphrase is needed for.
#[derive(Clone, Debug)]
pub enum Purpose {
    CreateIdentity {
        store: PathBuf,
    },
    CreateCase {
        store: PathBuf,
        reference: String,
        legal_basis: String,
        retention_until: String,
    },
    Unlock {
        store: PathBuf,
        case_id: String,
    },
    /// Verify every case of the store (one passphrase for all of the examiner's cases).
    VerifyStore {
        store: PathBuf,
    },
    /// Read every case's reference, retention date and legal hold (nothing is written).
    StoreOverview {
        store: PathBuf,
    },
    /// Sign a key card for the laboratory's key register, saved to `dest` (chosen in a native dialog).
    KeyCard {
        store: PathBuf,
        holder: String,
        dest: PathBuf,
    },
    /// Choose the recovery passphrase that will seal the device secret (held until the next prompt).
    RecoveryNew,
    /// Seal this account's device secret into `dest` with the recovery passphrase chosen before.
    RecoveryExport {
        store: PathBuf,
        dest: PathBuf,
        recovery: Secret,
    },
    /// Open the recovery file at `path` with its passphrase (nothing is written).
    RecoveryOpen {
        path: PathBuf,
    },
    /// Restore the device secret from `path` into this account's keystore, after it proves it opens `store`.
    RecoveryImport {
        path: PathBuf,
        store: PathBuf,
        recovery: Secret,
    },
}

impl Purpose {
    fn creates_secret(&self) -> bool {
        matches!(self, Self::CreateIdentity { .. } | Self::RecoveryNew)
    }
}

/// A prompt waiting for the examiner.
pub struct Pending {
    purpose: Purpose,
    attempts: u32,
    reply: mpsc::Sender<Result<Value, IpcError>>,
}

/// What the prompt window shows (no secrets).
#[derive(Debug, Serialize, PartialEq, Eq)]
pub struct Context {
    pub purpose: &'static str,
    pub title: String,
    pub detail: String,
    pub confirm: bool,
    pub min_chars: usize,
    pub attempts_left: u32,
}

/// Open the prompt for `purpose` and wait for the outcome of the sidecar call it makes.
pub async fn ask(app: &AppHandle, purpose: Purpose) -> Result<Value, IpcError> {
    let (reply, outcome) = mpsc::channel();
    let registered = state::with_prompt(app, |slot| {
        if slot.is_some() {
            return false;
        }
        *slot = Some(Pending {
            purpose,
            attempts: 0,
            reply,
        });
        true
    })?;
    if !registered {
        return Err(IpcError::new(
            ErrorKind::Busy,
            "a passphrase prompt is already open",
        ));
    }
    if windows::build_prompt(app).is_err() {
        let _ = state::with_prompt(app, Option::take);
        return Err(IpcError::unavailable(
            "the passphrase prompt could not be opened",
        ));
    }
    let waited = state::blocking(move || Ok(outcome.recv_timeout(PROMPT_TIMEOUT))).await?;
    match waited {
        Ok(result) => result,
        Err(_) => {
            let _ = state::with_prompt(app, Option::take);
            windows::close_prompt(app);
            Err(IpcError::cancelled())
        }
    }
}

/// Describe the open prompt to the prompt window.
pub fn context(app: &AppHandle) -> Result<Context, IpcError> {
    let described = state::with_prompt(app, |slot| {
        slot.as_ref()
            .map(|p| describe(&p.purpose, MAX_ATTEMPTS.saturating_sub(p.attempts)))
    })?;
    described.ok_or_else(|| IpcError::invalid("no passphrase is being asked for"))
}

fn describe(purpose: &Purpose, attempts_left: u32) -> Context {
    let (purpose, title, detail) = match purpose {
        Purpose::CreateIdentity { .. } => (
            "create_identity",
            "Choose your examiner passphrase".to_owned(),
            "It protects your signing key and every case you create in this store. It cannot be recovered."
                .to_owned(),
        ),
        Purpose::CreateCase { reference, .. } => (
            "create_case",
            format!("Create case {reference}"),
            "Enter your examiner passphrase to create and open the case.".to_owned(),
        ),
        Purpose::Unlock { case_id, .. } => (
            "unlock",
            "Unlock case".to_owned(),
            format!("Case {}. Enter your examiner passphrase.", &case_id[..8.min(case_id.len())]),
        ),
        Purpose::VerifyStore { .. } => (
            "verify_store",
            "Verify all cases".to_owned(),
            "Enter your examiner passphrase to check every case of this store. Each check is recorded in that case's custody log."
                .to_owned(),
        ),
        Purpose::KeyCard { .. } => (
            "key_card",
            "Export your key card".to_owned(),
            "Enter your examiner passphrase to sign a card of your public key for the laboratory's key register."
                .to_owned(),
        ),
        Purpose::StoreOverview { .. } => (
            "store_overview",
            "Show case details".to_owned(),
            "Enter your examiner passphrase to show the reference, retention date and legal hold of every case. Nothing is changed."
                .to_owned(),
        ),
        Purpose::RecoveryNew => (
            "recovery_new",
            "Choose a recovery passphrase".to_owned(),
            "It seals this account's device secret in the recovery file. Use a different passphrase from your examiner passphrase; the laboratory keeps it apart from the file."
                .to_owned(),
        ),
        Purpose::RecoveryExport { .. } => (
            "recovery_export",
            "Export the recovery file".to_owned(),
            "Enter your examiner passphrase to confirm it is you. The export is recorded in the store audit file."
                .to_owned(),
        ),
        Purpose::RecoveryOpen { .. } => (
            "recovery_open",
            "Open the recovery file".to_owned(),
            "Enter the recovery passphrase that seals this file. Nothing is changed yet.".to_owned(),
        ),
        Purpose::RecoveryImport { .. } => (
            "recovery_import",
            "Restore the device secret".to_owned(),
            "Enter your examiner passphrase. Ridge checks that the recovered secret opens this store before it saves it in this account's OS keystore."
                .to_owned(),
        ),
    };
    let confirm = matches!(purpose, "create_identity" | "recovery_new");
    Context {
        purpose,
        title,
        detail,
        confirm,
        min_chars: if confirm { MIN_NEW_CHARS } else { 1 },
        attempts_left,
    }
}

/// Use a submitted passphrase. `Ok` closes the prompt; a refusal keeps it open for another try
/// until `MAX_ATTEMPTS`.
pub fn submit(
    app: &AppHandle,
    passphrase: &Zeroizing<String>,
    confirmation: &Zeroizing<String>,
) -> Result<(), IpcError> {
    let purpose = state::with_prompt(app, |slot| slot.as_ref().map(|p| p.purpose.clone()))?
        .ok_or_else(|| IpcError::invalid("no passphrase is being asked for"))?;
    check(&purpose, passphrase, confirmation)?;
    match prompt_calls::perform(app, &purpose, passphrase) {
        Ok(value) => {
            finish(app, Ok(value));
            Ok(())
        }
        Err(error) if error.kind == ErrorKind::Refused => {
            let exhausted = state::with_prompt(app, |slot| {
                slot.as_mut().is_some_and(|p| {
                    p.attempts += 1;
                    p.attempts >= MAX_ATTEMPTS
                })
            })?;
            if exhausted {
                finish(
                    app,
                    Err(IpcError::refused(
                        "too many failed attempts; the prompt was closed",
                    )),
                );
            }
            Err(error)
        }
        Err(error) => {
            finish(app, Err(error.clone()));
            Err(error)
        }
    }
}

/// The examiner cancelled or closed the prompt.
pub fn abandon(app: &AppHandle) {
    finish(app, Err(IpcError::cancelled()));
}

fn finish(app: &AppHandle, outcome: Result<Value, IpcError>) {
    if let Ok(Some(pending)) = state::with_prompt(app, Option::take) {
        let _ = pending.reply.send(outcome);
    }
    windows::close_prompt(app);
}

fn check(purpose: &Purpose, passphrase: &str, confirmation: &str) -> Result<(), IpcError> {
    let chars = passphrase.chars().count();
    if chars == 0 || chars > MAX_CHARS {
        return Err(IpcError::invalid("enter your passphrase"));
    }
    if purpose.creates_secret() {
        if chars < MIN_NEW_CHARS {
            return Err(IpcError::invalid(&format!(
                "use at least {MIN_NEW_CHARS} characters"
            )));
        }
        if passphrase != confirmation {
            return Err(IpcError::invalid("the two passphrases are not the same"));
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn secret(s: &str) -> Zeroizing<String> {
        Zeroizing::new(s.to_owned())
    }

    #[test]
    fn new_passphrases_need_length_and_confirmation() {
        let create = Purpose::CreateIdentity {
            store: PathBuf::from("/store"),
        };
        assert!(check(&create, &secret("short"), &secret("short")).is_err());
        let long = "correct horse battery staple";
        assert!(check(&create, &secret(long), &secret("something else entirely")).is_err());
        assert!(check(&create, &secret(long), &secret(long)).is_ok());
    }

    #[test]
    fn unlocking_needs_only_a_non_empty_passphrase() {
        let unlock = Purpose::Unlock {
            store: PathBuf::from("/store"),
            case_id: "0f8fad5b".into(),
        };
        assert!(check(&unlock, &secret(""), &secret("")).is_err());
        assert!(check(&unlock, &secret("x"), &secret("")).is_ok());
        assert!(check(&unlock, &secret(&"x".repeat(MAX_CHARS + 1)), &secret("")).is_err());
    }

    #[test]
    fn the_prompt_describes_its_purpose_without_secrets() {
        let unlock = Purpose::Unlock {
            store: PathBuf::from("/s"),
            case_id: "0f8fad5b-d9cb-469f-a165-70867728950e".into(),
        };
        let shown = describe(&unlock, 5);
        assert_eq!((shown.purpose, shown.confirm), ("unlock", false));
        assert!(shown.detail.contains("0f8fad5b") && !shown.detail.contains("/s"));
        let create = Purpose::CreateIdentity {
            store: PathBuf::from("/s"),
        };
        assert_eq!(describe(&create, 5).min_chars, MIN_NEW_CHARS);
        let case = Purpose::CreateCase {
            store: PathBuf::from("/s"),
            reference: "KT-2026-7".into(),
            legal_basis: "x".into(),
            retention_until: "2030-01-01".into(),
        };
        assert!(describe(&case, 3).title.contains("KT-2026-7"));
    }

    #[test]
    fn verifying_a_store_asks_for_the_existing_passphrase_only() {
        let verify = Purpose::VerifyStore {
            store: PathBuf::from("/s"),
        };
        let shown = describe(&verify, 5);
        assert_eq!(
            (shown.purpose, shown.confirm, shown.min_chars),
            ("verify_store", false, 1)
        );
        assert!(check(&verify, &secret("x"), &secret("")).is_ok());
        let overview = describe(
            &Purpose::StoreOverview {
                store: PathBuf::from("/s"),
            },
            5,
        );
        assert_eq!(
            (overview.purpose, overview.confirm),
            ("store_overview", false)
        );
        assert!(!overview.detail.contains("/s"));
        let card = Purpose::KeyCard {
            store: PathBuf::from("/s"),
            holder: "Examiner A".into(),
            dest: PathBuf::from("/out/card.json"),
        };
        let shown = describe(&card, 5);
        assert_eq!((shown.purpose, shown.confirm), ("key_card", false));
        assert!(!shown.detail.contains("/out"));
    }

    #[test]
    fn recovery_asks_a_new_passphrase_then_existing_ones_and_never_prints_one() {
        let new = describe(&Purpose::RecoveryNew, 5);
        assert_eq!(
            (new.purpose, new.confirm, new.min_chars),
            ("recovery_new", true, MIN_NEW_CHARS)
        );
        let long = "a separate recovery passphrase";
        assert!(check(&Purpose::RecoveryNew, &secret("short"), &secret("short")).is_err());
        assert!(check(&Purpose::RecoveryNew, &secret(long), &secret("different")).is_err());
        assert!(check(&Purpose::RecoveryNew, &secret(long), &secret(long)).is_ok());
        let held = Secret::new(long);
        assert_eq!(format!("{held:?}"), "Secret(<redacted>)");
        let export = Purpose::RecoveryExport {
            store: PathBuf::from("/s"),
            dest: PathBuf::from("/out/recovery.json"),
            recovery: held.clone(),
        };
        assert!(!format!("{export:?}").contains(long)); // a purpose may be logged; its secret never is
        let shown = describe(&export, 5);
        assert_eq!((shown.purpose, shown.confirm), ("recovery_export", false));
        assert!(check(&export, &secret("x"), &secret("")).is_ok());
        let open = describe(
            &Purpose::RecoveryOpen {
                path: PathBuf::from("/in/recovery.json"),
            },
            5,
        );
        assert_eq!((open.purpose, open.confirm), ("recovery_open", false));
        let import = Purpose::RecoveryImport {
            path: PathBuf::from("/in/recovery.json"),
            store: PathBuf::from("/s"),
            recovery: held,
        };
        let shown = describe(&import, 5);
        assert_eq!((shown.purpose, shown.confirm), ("recovery_import", false));
        assert!(!shown.detail.contains("/in") && !shown.detail.contains(long));
    }
}
