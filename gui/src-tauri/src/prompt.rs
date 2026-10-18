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
use serde_json::{json, Value};
use tauri::AppHandle;
use zeroize::Zeroizing;

use crate::error::{ErrorKind, IpcError};
use crate::state::{self, path_text};
use crate::windows;

const MAX_ATTEMPTS: u32 = 5;
const PROMPT_TIMEOUT: Duration = Duration::from_secs(10 * 60);
const KDF_TIMEOUT: Duration = Duration::from_secs(180);
/// Every case is decrypted and checked: allow for a large store.
const STORE_VERIFY_TIMEOUT: Duration = Duration::from_secs(60 * 60);
/// NIST SP 800-63B-style minimum for new passphrases (architecture §9.3; the sidecar enforces it too).
pub const MIN_NEW_CHARS: usize = 15;
const MAX_CHARS: usize = 1024;

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
}

impl Purpose {
    fn creates_secret(&self) -> bool {
        matches!(self, Self::CreateIdentity { .. })
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
    };
    let confirm = matches!(purpose, "create_identity");
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
    match perform(app, &purpose, passphrase) {
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

#[derive(Serialize)]
struct WithSecret<'a> {
    store: &'a str,
    #[serde(skip_serializing_if = "Option::is_none")]
    case_id: Option<&'a str>,
    passphrase: &'a str,
}

fn perform(app: &AppHandle, purpose: &Purpose, passphrase: &str) -> Result<Value, IpcError> {
    match purpose {
        Purpose::VerifyStore { store } => {
            let store = path_text(store)?;
            let params = WithSecret {
                store: &store,
                case_id: None,
                passphrase,
            };
            state::call_now(app, "store.verify", &params, STORE_VERIFY_TIMEOUT)
        }
        Purpose::CreateIdentity { store } => {
            let store = path_text(store)?;
            let params = WithSecret {
                store: &store,
                case_id: None,
                passphrase,
            };
            state::call_now(app, "identity.create", &params, KDF_TIMEOUT)
        }
        Purpose::Unlock { store, case_id } => {
            let store = path_text(store)?;
            let params = WithSecret {
                store: &store,
                case_id: Some(case_id),
                passphrase,
            };
            state::call_now(app, "session.unlock", &params, KDF_TIMEOUT)
        }
        Purpose::CreateCase {
            store,
            reference,
            legal_basis,
            retention_until,
        } => {
            let store = path_text(store)?;
            #[derive(Serialize)]
            struct Create<'a> {
                store: &'a str,
                reference: &'a str,
                legal_basis: &'a str,
                retention_until: &'a str,
                passphrase: &'a str,
            }
            let params = Create {
                store: &store,
                reference,
                legal_basis,
                retention_until,
                passphrase,
            };
            let created = state::call_now(app, "case.create", &params, KDF_TIMEOUT)?;
            let case_id = created
                .get("case_id")
                .and_then(Value::as_str)
                .unwrap_or_default()
                .to_owned();
            let unlock = WithSecret {
                store: &store,
                case_id: Some(&case_id),
                passphrase,
            };
            // The case exists even if opening it fails; the examiner can unlock it from the list.
            let session = state::call_now(app, "session.unlock", &unlock, KDF_TIMEOUT).ok();
            Ok(json!({"case_id": case_id, "session": session}))
        }
    }
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
    }
}
