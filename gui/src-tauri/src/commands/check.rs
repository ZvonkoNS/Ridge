//! Capture check (FR-54): whether a photograph gives Ridge something to work with, on a file chosen
//! in a native dialog before import (read once, read-only) or on a stored photo (a logged read).
//! Indicative only, never a quality score; the WebView only shows the findings.

use std::time::Duration;

use serde::Deserialize;
use serde_json::{json, Value};
use tauri::{AppHandle, WebviewWindow};

use crate::dialogs;
use crate::error::IpcError;
use crate::state::{call, path_text};
use crate::validate;
use crate::windows::{require, MAIN_LABEL};

/// The photo is decoded and the finger measured at working scale.
const CHECK_IO: Duration = Duration::from_secs(120);

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
pub struct PhotoRef {
    sha256: String,
}

/// Check a photo before it is imported: the file is chosen in a native dialog and never changed.
#[tauri::command]
pub async fn check_photo(app: AppHandle, window: WebviewWindow) -> Result<Value, IpcError> {
    require(&window, MAIN_LABEL)?;
    let path = dialogs::pick_image(&app, "Check a photo before import").await?;
    call(
        &app,
        "photo.check",
        json!({"path": path_text(&path)?}),
        CHECK_IO,
    )
    .await
}

/// Check a stored evidence or reference image (the sidecar logs the read and refuses outputs).
#[tauri::command]
pub async fn check_evidence(
    app: AppHandle,
    window: WebviewWindow,
    request: PhotoRef,
) -> Result<Value, IpcError> {
    require(&window, MAIN_LABEL)?;
    let sha256 = validate::sha256(&request.sha256)?;
    call(&app, "evidence.check", json!({"sha256": sha256}), CHECK_IO).await
}
