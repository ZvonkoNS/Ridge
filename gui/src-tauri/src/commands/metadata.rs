//! Photo metadata (FR-36): what an imported evidence or reference image records about itself,
//! read by the sidecar from the verified stored copy (a logged read). The WebView only shows it;
//! the map link is text to copy, never opened by Ridge (no opener, shell or network capability).

use std::time::Duration;

use serde::Deserialize;
use serde_json::{json, Value};
use tauri::{AppHandle, WebviewWindow};

use crate::error::IpcError;
use crate::state::call;
use crate::validate;
use crate::windows::{require, MAIN_LABEL};

/// The photo is decrypted and its metadata parsed (PNG text after the pixels needs a decode).
const METADATA_IO: Duration = Duration::from_secs(120);

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
pub struct PhotoRef {
    sha256: String,
}

/// The metadata of one imported photo, bounded and display-safe (the sidecar refuses outputs).
#[tauri::command]
pub async fn photo_metadata(
    app: AppHandle,
    window: WebviewWindow,
    request: PhotoRef,
) -> Result<Value, IpcError> {
    require(&window, MAIN_LABEL)?;
    let sha256 = validate::sha256(&request.sha256)?;
    call(&app, "metadata.get", json!({"sha256": sha256}), METADATA_IO).await
}
