//! Folder triage (FR-57): the capture check on every photo of a folder chosen in a native dialog,
//! listed with a measurable ridge pattern first. Read-only; the index, when asked for, goes to a
//! new CSV file chosen in a save dialog. A reading order for the examiner, never a quality
//! judgement; the WebView only shows the rows.

use std::time::Duration;

use serde::Deserialize;
use serde_json::{json, Value};
use tauri::{AppHandle, WebviewWindow};

use crate::dialogs;
use crate::error::IpcError;
use crate::state::{call, path_text};
use crate::windows::{require, MAIN_LABEL};

/// The capture check costs a few seconds per photo whatever its size: `MAX_PHOTOS` keeps one run
/// inside `TRIAGE_IO`. The sidecar refuses a larger folder before any photo is read; the command
/// line takes more.
const TRIAGE_IO: Duration = Duration::from_secs(45 * 60);
const MAX_PHOTOS: u32 = 300;
const CSV_FILE: (&str, &[&str]) = ("Index (CSV)", &["csv"]);

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
pub struct TriageRequest {
    recursive: bool,
    save_index: bool,
}

/// Check every photo of a folder chosen in a native dialog; with `save_index`, a second dialog
/// names the new CSV file (the sidecar refuses one inside the folder, or one that exists).
#[tauri::command]
pub async fn triage_folder(
    app: AppHandle,
    window: WebviewWindow,
    request: TriageRequest,
) -> Result<Value, IpcError> {
    require(&window, MAIN_LABEL)?;
    let folder = dialogs::pick_folder(&app, "Choose a folder of photos").await?;
    let dest = if request.save_index {
        let suggested = folder
            .file_name()
            .map(|name| format!("{}-triage.csv", name.to_string_lossy()));
        let chosen = dialogs::save_file(&app, "Save the triage index", suggested, CSV_FILE).await?;
        Some(path_text(&chosen)?)
    } else {
        None
    };
    let params = json!({
        "path": path_text(&folder)?,
        "recursive": request.recursive,
        "max_files": MAX_PHOTOS,
        "dest": dest,
    });
    call(&app, "folder.triage", params, TRIAGE_IO).await
}
