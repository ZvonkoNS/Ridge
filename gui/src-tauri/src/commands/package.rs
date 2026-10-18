//! Disclosure package: the case's signed processing record and reports in a new folder, with a
//! signed manifest (no images). The examiner names the folder in a native dialog.

use std::time::Duration;

use serde_json::{json, Value};
use tauri::{AppHandle, WebviewWindow};

use crate::dialogs;
use crate::error::IpcError;
use crate::state::{call, path_text};
use crate::windows::{require, MAIN_LABEL};

/// Every signed report is read and checked: allow for a case with many jobs.
const PACKAGE_IO: Duration = Duration::from_secs(10 * 60);

/// Write a disclosure package to a new folder (logged as `package.export`).
#[tauri::command]
pub async fn export_package(app: AppHandle, window: WebviewWindow) -> Result<Value, IpcError> {
    require(&window, MAIN_LABEL)?;
    let suggested = "Ridge disclosure package".to_owned();
    let dest = dialogs::new_folder(&app, "Name the new package folder", suggested).await?;
    let dest = path_text(&dest)?;
    call(&app, "package.export", json!({"dest": dest}), PACKAGE_IO).await
}
