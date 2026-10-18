//! Commands of the passphrase prompt window only (capability `passphrase`, ADR-010).

use serde::Deserialize;
use tauri::{AppHandle, WebviewWindow};
use zeroize::Zeroizing;

use crate::error::IpcError;
use crate::prompt::{self, Context};
use crate::state::blocking;
use crate::windows::{require, PROMPT_LABEL};

/// What the prompt is for (no secrets).
#[tauri::command]
pub fn passphrase_context(app: AppHandle, window: WebviewWindow) -> Result<Context, IpcError> {
    require(&window, PROMPT_LABEL)?;
    prompt::context(&app)
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Submission {
    passphrase: String,
    confirmation: Option<String>,
}

/// Use the passphrase. Success closes the prompt; a wrong passphrase leaves it open.
#[tauri::command]
pub async fn passphrase_submit(
    app: AppHandle,
    window: WebviewWindow,
    request: Submission,
) -> Result<(), IpcError> {
    require(&window, PROMPT_LABEL)?;
    let passphrase = Zeroizing::new(request.passphrase);
    let confirmation = Zeroizing::new(request.confirmation.unwrap_or_default());
    blocking(move || prompt::submit(&app, &passphrase, &confirmation)).await
}

/// The examiner cancelled.
#[tauri::command]
pub fn passphrase_cancel(app: AppHandle, window: WebviewWindow) -> Result<(), IpcError> {
    require(&window, PROMPT_LABEL)?;
    prompt::abandon(&app);
    Ok(())
}
