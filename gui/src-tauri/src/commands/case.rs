//! Commands on the unlocked case: metadata, legal hold, items, import, verify, export, previews.

use std::time::Duration;

use serde::Deserialize;
use serde_json::{json, Value};
use tauri::{AppHandle, WebviewWindow};

use crate::error::IpcError;
use crate::state::{call, path_text};
use crate::windows::{require, MAIN_LABEL};
use crate::{dialogs, validate};

const QUICK: Duration = Duration::from_secs(30);
const IMAGE_IO: Duration = Duration::from_secs(120);
const VERIFY: Duration = Duration::from_secs(15 * 60);
const PNG: (&str, &[&str]) = ("PNG image", &["png"]);
const JSON_FILE: (&str, &[&str]) = ("JSON", &["json"]);
const ANY_IMAGE: (&str, &[&str]) = (
    "Image",
    &[
        "png", "jpg", "jpeg", "tif", "tiff", "bmp", "webp", "heic", "heif",
    ],
);

/// Metadata of the unlocked case.
#[tauri::command]
pub async fn case_info(app: AppHandle, window: WebviewWindow) -> Result<Value, IpcError> {
    require(&window, MAIN_LABEL)?;
    call(&app, "case.info", json!({}), QUICK).await
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Hold {
    on: bool,
    reason: String,
}

/// Place or lift a legal hold (FR-26).
#[tauri::command]
pub async fn set_legal_hold(
    app: AppHandle,
    window: WebviewWindow,
    request: Hold,
) -> Result<Value, IpcError> {
    require(&window, MAIN_LABEL)?;
    let reason = validate::text(&request.reason, "reason", 500)?;
    call(
        &app,
        "case.hold",
        json!({"on": request.on, "reason": reason}),
        QUICK,
    )
    .await
}

/// Everything stored in the case.
#[tauri::command]
pub async fn list_items(app: AppHandle, window: WebviewWindow) -> Result<Value, IpcError> {
    require(&window, MAIN_LABEL)?;
    call(&app, "case.items", json!({}), QUICK).await
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Import {
    source: Option<String>,
}

/// At most this many photos per import, so one dialog cannot start an unbounded batch.
const MAX_BATCH: usize = 50;

/// Import evidence photos chosen in a native dialog (one or more), with an optional source note
/// for all of them (FR-21). Each import is its own logged step; a photo the sidecar refuses is
/// reported and the others are still imported. A locked case or a stopped engine ends the batch.
#[tauri::command]
pub async fn import_evidence(
    app: AppHandle,
    window: WebviewWindow,
    request: Import,
) -> Result<Value, IpcError> {
    require(&window, MAIN_LABEL)?;
    let source = validate::optional_text(request.source.as_deref(), "source note", 200)?;
    let paths = dialogs::pick_images(&app, "Import evidence photos", MAX_BATCH).await?;
    let (mut imported, mut refused) = (Vec::new(), Vec::new());
    for path in paths {
        let name = path_name(&path);
        let params = json!({"path": path_text(&path)?, "source": source});
        match call(&app, "case.import", params, IMAGE_IO).await {
            Ok(item) => imported.push(item),
            Err(error) if continues(&error) => {
                refused.push(json!({"name": name, "message": error.message}));
            }
            Err(error) => return Err(error),
        }
    }
    Ok(json!({"imported": imported, "refused": refused}))
}

/// Only a refusal of the photo itself (wrong format, too large, undecodable) lets the batch go on;
/// a locked case, a custody or storage failure, or a stopped engine ends it.
fn continues(error: &IpcError) -> bool {
    error.input_refused
}

/// The file name only, for the examiner's summary (no folders reach the WebView).
fn path_name(path: &std::path::Path) -> String {
    path.file_name()
        .map(|n| n.to_string_lossy().into_owned())
        .unwrap_or_default()
}

/// Import a NAFIS/AFIS candidate image for viewing beside an export (FR-52; never processed).
#[tauri::command]
pub async fn import_reference(
    app: AppHandle,
    window: WebviewWindow,
    request: Import,
) -> Result<Value, IpcError> {
    require(&window, MAIN_LABEL)?;
    let source = validate::text(
        request.source.as_deref().unwrap_or_default(),
        "source of the reference",
        200,
    )?;
    let path = path_text(&dialogs::pick_image(&app, "Import a reference image").await?)?;
    call(
        &app,
        "case.import_reference",
        json!({"path": path, "source": source}),
        IMAGE_IO,
    )
    .await
}

/// Check every hash, the custody chain and every signature (FR-24).
#[tauri::command]
pub async fn verify_case(app: AppHandle, window: WebviewWindow) -> Result<Value, IpcError> {
    require(&window, MAIN_LABEL)?;
    call(&app, "case.verify", json!({}), VERIFY).await
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Export {
    sha256: String,
    suggested_name: Option<String>,
}

/// Export one stored item to a file the examiner chooses (FR-25, logged; never overwrites).
#[tauri::command]
pub async fn export_item(
    app: AppHandle,
    window: WebviewWindow,
    request: Export,
) -> Result<Value, IpcError> {
    require(&window, MAIN_LABEL)?;
    let sha256 = validate::sha256(&request.sha256)?;
    let suggested = request
        .suggested_name
        .as_deref()
        .unwrap_or_default()
        .to_ascii_lowercase();
    let filter = if suggested.ends_with(".png") {
        PNG
    } else if suggested.ends_with(".json") {
        JSON_FILE // minutiae artefacts
    } else {
        ANY_IMAGE
    };
    let dest =
        path_text(&dialogs::save_file(&app, "Export to", request.suggested_name, filter).await?)?;
    call(
        &app,
        "case.export",
        json!({"sha256": sha256, "dest": dest, "overwrite": false}),
        IMAGE_IO,
    )
    .await
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Preview {
    sha256: String,
    max_side: u32,
}

/// A bounded PNG preview for display (logged read).
#[tauri::command]
pub async fn preview(
    app: AppHandle,
    window: WebviewWindow,
    request: Preview,
) -> Result<Value, IpcError> {
    require(&window, MAIN_LABEL)?;
    let sha256 = validate::sha256(&request.sha256)?;
    validate::number(f64::from(request.max_side), 16.0, 2048.0, "preview size")?;
    call(
        &app,
        "preview.get",
        json!({"sha256": sha256, "max_side": request.max_side}),
        IMAGE_IO,
    )
    .await
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Region {
    sha256: String,
    x: u32,
    y: u32,
    width: u32,
    height: u32,
}

/// A full-resolution rectangle for pixel inspection (logged read).
#[tauri::command]
pub async fn preview_region(
    app: AppHandle,
    window: WebviewWindow,
    request: Region,
) -> Result<Value, IpcError> {
    require(&window, MAIN_LABEL)?;
    let sha256 = validate::sha256(&request.sha256)?;
    for side in [request.width, request.height] {
        validate::number(f64::from(side), 1.0, 2048.0, "region size")?;
    }
    let params = json!({
        "sha256": sha256, "x": request.x, "y": request.y, "width": request.width, "height": request.height
    });
    call(&app, "preview.region", params, IMAGE_IO).await
}

#[cfg(test)]
mod tests {
    use super::{continues, path_name};
    use crate::error::IpcError;

    #[test]
    fn a_refused_photo_does_not_stop_the_batch_but_a_locked_case_does() {
        assert!(continues(&IpcError::input_refused(
            "not a supported image format"
        )));
        assert!(!continues(&IpcError::refused("no case is unlocked")));
        assert!(!continues(&IpcError::refused(
            "custody log: entry 9 could not be written"
        )));
        assert!(!continues(&IpcError::unavailable("the engine stopped")));
        assert_eq!(
            path_name(std::path::Path::new("/photos/IMG_0042.jpg")),
            "IMG_0042.jpg"
        );
    }
}
