//! The sidecar calls a submitted passphrase is used for, one per prompt purpose (ADR-010). Only
//! the Rust core sends these methods; the passphrase is borrowed from the prompt's zeroised buffer.

use std::time::Duration;

use serde::Serialize;
use serde_json::{json, Value};
use tauri::AppHandle;

use crate::error::IpcError;
use crate::prompt::{Purpose, Secret};
use crate::state::{self, path_text};

const KDF_TIMEOUT: Duration = Duration::from_secs(180);
/// Every case is decrypted and checked (or its metadata read): allow for a large store.
const STORE_VERIFY_TIMEOUT: Duration = Duration::from_secs(60 * 60);

#[derive(Serialize)]
struct WithSecret<'a> {
    store: &'a str,
    #[serde(skip_serializing_if = "Option::is_none")]
    case_id: Option<&'a str>,
    passphrase: &'a str,
}

/// Make the sidecar call `purpose` stands for, with the examiner's passphrase.
pub fn perform(app: &AppHandle, purpose: &Purpose, passphrase: &str) -> Result<Value, IpcError> {
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
        Purpose::KeyCard {
            store,
            holder,
            dest,
        } => {
            #[derive(Serialize)]
            struct Card<'a> {
                store: &'a str,
                passphrase: &'a str,
                holder: &'a str,
                dest: &'a str,
            }
            let (store, dest) = (path_text(store)?, path_text(dest)?);
            let params = Card {
                store: &store,
                passphrase,
                holder,
                dest: &dest,
            };
            state::call_now(app, "identity.card", &params, KDF_TIMEOUT)
        }
        Purpose::StoreOverview { store } => {
            let store = path_text(store)?;
            let params = WithSecret {
                store: &store,
                case_id: None,
                passphrase,
            };
            state::call_now(app, "store.overview", &params, STORE_VERIFY_TIMEOUT)
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
        Purpose::RecoveryNew => {
            state::stash_recovery(app, Secret::new(passphrase))?;
            Ok(json!({"chosen": true}))
        }
        Purpose::RecoveryExport {
            store,
            dest,
            recovery,
        } => {
            if recovery.expose() == passphrase {
                return Err(IpcError::invalid(
                    "the recovery passphrase must not be your examiner passphrase",
                ));
            }
            let (store, dest) = (path_text(store)?, path_text(dest)?);
            let params = Recovery {
                store: Some(&store),
                path: None,
                dest: Some(&dest),
                examiner_passphrase: Some(passphrase),
                recovery_passphrase: recovery.expose(),
            };
            state::call_now(app, "recovery.export", &params, KDF_TIMEOUT)
        }
        Purpose::RecoveryOpen { path } => {
            let path = path_text(path)?;
            let params = Recovery {
                store: None,
                path: Some(&path),
                dest: None,
                examiner_passphrase: None,
                recovery_passphrase: passphrase,
            };
            let opened = state::call_now(app, "recovery.check", &params, KDF_TIMEOUT)?;
            state::stash_recovery(app, Secret::new(passphrase))?;
            Ok(opened)
        }
        Purpose::RecoveryImport {
            path,
            store,
            recovery,
        } => {
            let (path, store) = (path_text(path)?, path_text(store)?);
            let params = Recovery {
                store: Some(&store),
                path: Some(&path),
                dest: None,
                examiner_passphrase: Some(passphrase),
                recovery_passphrase: recovery.expose(),
            };
            state::call_now(app, "recovery.import", &params, KDF_TIMEOUT)
        }
    }
}

/// Parameters of the recovery methods (ADR-012); absent fields are left out of the request.
#[derive(Serialize)]
struct Recovery<'a> {
    #[serde(skip_serializing_if = "Option::is_none")]
    store: Option<&'a str>,
    #[serde(skip_serializing_if = "Option::is_none")]
    path: Option<&'a str>,
    #[serde(skip_serializing_if = "Option::is_none")]
    dest: Option<&'a str>,
    #[serde(skip_serializing_if = "Option::is_none")]
    examiner_passphrase: Option<&'a str>,
    recovery_passphrase: &'a str,
}
