//! Device-secret recovery file (ADR-012): export it from this account, or restore it into an
//! account whose OS keystore has lost the secret. Both take two passphrases, each typed in the
//! prompt window; the first is held only in the Rust core, zeroised, until the second prompt uses it.

use serde_json::Value;
use tauri::{AppHandle, WebviewWindow};

use crate::dialogs;
use crate::error::IpcError;
use crate::prompt::{self, Purpose};
use crate::state;
use crate::windows::{require, MAIN_LABEL};

const RECOVERY_FILE: (&str, &[&str]) = ("Ridge recovery file (JSON)", &["json"]);

/// Choose where to save, then the recovery passphrase, then the examiner passphrase.
#[tauri::command]
pub async fn export_recovery(app: AppHandle, window: WebviewWindow) -> Result<Value, IpcError> {
    require(&window, MAIN_LABEL)?;
    let store = state::store(&app)?;
    drop(state::take_recovery(&app)?); // nothing left over from an earlier, abandoned task
    let suggested = Some("ridge-recovery.json".to_owned());
    let dest = dialogs::save_file(&app, "Save the recovery file", suggested, RECOVERY_FILE).await?;
    prompt::ask(&app, Purpose::RecoveryNew).await?;
    let recovery = state::take_recovery(&app)?.ok_or_else(IpcError::cancelled)?;
    prompt::ask(
        &app,
        Purpose::RecoveryExport {
            store,
            dest,
            recovery,
        },
    )
    .await
}

/// Choose the recovery file, then its passphrase (checked at once), then the examiner passphrase.
#[tauri::command]
pub async fn import_recovery(app: AppHandle, window: WebviewWindow) -> Result<Value, IpcError> {
    require(&window, MAIN_LABEL)?;
    let store = state::store(&app)?;
    drop(state::take_recovery(&app)?);
    let path = dialogs::pick_file(&app, "Choose the recovery file", RECOVERY_FILE).await?;
    prompt::ask(&app, Purpose::RecoveryOpen { path: path.clone() }).await?;
    let recovery = state::take_recovery(&app)?.ok_or_else(IpcError::cancelled)?;
    prompt::ask(
        &app,
        Purpose::RecoveryImport {
            path,
            store,
            recovery,
        },
    )
    .await
}
