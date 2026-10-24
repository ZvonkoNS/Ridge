//! Examiner annotations (FR-55): marks the examiner places on a job's output image, recorded by the
//! sidecar as a signed custody entry, listed, and drawn into a plaintext PNG chosen in a native save
//! dialog. The WebView proposes; Rust bounds and types the request; the sidecar validates it again.

use std::time::Duration;

use serde::Deserialize;
use serde_json::{json, Value};
use tauri::{AppHandle, WebviewWindow};

use crate::dialogs;
use crate::error::IpcError;
use crate::state::{call, path_text};
use crate::validate;
use crate::windows::{require, MAIN_LABEL};

const QUICK: Duration = Duration::from_secs(30);
/// The image is decrypted, drawn on and written.
const EXPORT_IO: Duration = Duration::from_secs(120);
const MAX_MARKS: usize = 500;
const MAX_LABEL_CHARS: usize = 40;
const MAX_NOTE_CHARS: usize = 2000;
const KINDS: [&str; 3] = ["ending", "bifurcation", "other"];

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
pub struct MarkRequest {
    x: u32,
    y: u32,
    kind: String,
    label: Option<String>,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
pub struct NewAnnotation {
    job_id: String,
    sha256: String,
    marks: Vec<MarkRequest>,
    note: Option<String>,
    replaces: Option<u64>,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
pub struct AnnotationFilter {
    job_id: Option<String>,
    sha256: Option<String>,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
pub struct AnnotationRef {
    seq: u64,
    suggested_name: String,
}

/// A mark's label is one short printable line.
fn label(value: Option<&str>) -> Result<Option<String>, IpcError> {
    let Some(text) = value else {
        return Ok(None);
    };
    let clean = validate::note(text, MAX_LABEL_CHARS)?;
    if clean.contains('\n') {
        return Err(IpcError::invalid("a mark's label is one line"));
    }
    Ok(Some(clean))
}

/// The marks as the sidecar takes them: a bounded list, each of an allow-listed kind with a clean label.
fn marks(items: &[MarkRequest]) -> Result<Vec<Value>, IpcError> {
    if items.is_empty() || items.len() > MAX_MARKS {
        return Err(IpcError::invalid(&format!(
            "an annotation set holds 1 to {MAX_MARKS} marks"
        )));
    }
    items
        .iter()
        .map(|m| {
            if !KINDS.contains(&m.kind.as_str()) {
                return Err(IpcError::invalid(
                    "a mark is an ending, a bifurcation or other",
                ));
            }
            Ok(json!({"x": m.x, "y": m.y, "kind": m.kind, "label": label(m.label.as_deref())?}))
        })
        .collect()
}

/// Record an annotation set on one output image of a job (the sidecar logs and signs it).
#[tauri::command]
pub async fn add_annotation(
    app: AppHandle,
    window: WebviewWindow,
    request: NewAnnotation,
) -> Result<Value, IpcError> {
    require(&window, MAIN_LABEL)?;
    let job_id = validate::uuid(&request.job_id, "job")?;
    let sha256 = validate::sha256(&request.sha256)?;
    let marks = marks(&request.marks)?;
    let note = request
        .note
        .as_deref()
        .map(|n| validate::note(n, MAX_NOTE_CHARS))
        .transpose()?;
    let params = json!({
        "job_id": job_id, "sha256": sha256, "marks": marks, "note": note, "replaces": request.replaces
    });
    call(&app, "annotation.add", params, QUICK).await
}

/// The annotation sets of the case, one job or one image.
#[tauri::command]
pub async fn list_annotations(
    app: AppHandle,
    window: WebviewWindow,
    request: AnnotationFilter,
) -> Result<Value, IpcError> {
    require(&window, MAIN_LABEL)?;
    let job_id = request
        .job_id
        .as_deref()
        .map(|j| validate::uuid(j, "job"))
        .transpose()?;
    let sha256 = request
        .sha256
        .as_deref()
        .map(validate::sha256)
        .transpose()?;
    let params = json!({"job_id": job_id, "sha256": sha256});
    call(&app, "annotations.list", params, QUICK).await
}

/// Write one set's annotated image (PNG) to a place chosen in a native save dialog (logged).
#[tauri::command]
pub async fn export_annotated(
    app: AppHandle,
    window: WebviewWindow,
    request: AnnotationRef,
) -> Result<Value, IpcError> {
    require(&window, MAIN_LABEL)?;
    let suggested = Some(dialogs::file_name(&request.suggested_name));
    let dest = dialogs::save_file(
        &app,
        "Save annotated image",
        suggested,
        ("PNG image", &["png"]),
    )
    .await?;
    let params = json!({"seq": request.seq, "dest": path_text(&dest)?});
    call(&app, "annotation.export", params, EXPORT_IO).await
}
