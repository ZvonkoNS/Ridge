//! Examiner notes on the case, one of its jobs or one stored item (custody action
//! `examiner.note`). Notes are append-only: a correction is a new note naming the one it corrects.

use std::time::Duration;

use serde::Deserialize;
use serde_json::{json, Value};
use tauri::{AppHandle, WebviewWindow};

use crate::error::IpcError;
use crate::state::call;
use crate::validate;
use crate::windows::{require, MAIN_LABEL};

const QUICK: Duration = Duration::from_secs(30);
/// The sidecar enforces the same limit.
const MAX_NOTE_CHARS: usize = 2000;

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
pub struct NewNote {
    text: String,
    job_id: Option<String>,
    sha256: Option<String>,
    corrects: Option<u64>,
}

fn job(value: Option<&str>) -> Result<Option<String>, IpcError> {
    value.map(|j| validate::uuid(j, "job")).transpose()
}

/// Append an examiner note (logged in the custody log).
#[tauri::command]
pub async fn add_note(
    app: AppHandle,
    window: WebviewWindow,
    request: NewNote,
) -> Result<Value, IpcError> {
    require(&window, MAIN_LABEL)?;
    let text = validate::note(&request.text, MAX_NOTE_CHARS)?;
    let job_id = job(request.job_id.as_deref())?;
    let sha256 = request
        .sha256
        .as_deref()
        .map(validate::sha256)
        .transpose()?;
    let params =
        json!({"text": text, "job_id": job_id, "sha256": sha256, "corrects": request.corrects});
    call(&app, "note.add", params, QUICK).await
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
pub struct NoteFilter {
    job_id: Option<String>,
}

/// The notes of the case, or of one job.
#[tauri::command]
pub async fn list_notes(
    app: AppHandle,
    window: WebviewWindow,
    request: NoteFilter,
) -> Result<Value, IpcError> {
    require(&window, MAIN_LABEL)?;
    let job_id = job(request.job_id.as_deref())?;
    call(&app, "notes.list", json!({"job_id": job_id}), QUICK).await
}
