//! Reading the case's records: the custody log page by page, and a readable HTML rendering of a
//! verified report (not signed; the signed JSON stays authoritative).

use std::time::Duration;

use serde::Deserialize;
use serde_json::{json, Value};
use tauri::{AppHandle, WebviewWindow};

use crate::error::IpcError;
use crate::state::{call, path_text};
use crate::windows::{require, MAIN_LABEL};
use crate::{dialogs, validate};

const QUICK: Duration = Duration::from_secs(30);
const RECORD_IO: Duration = Duration::from_secs(120);
/// A folder may be a store backup, which is rehashed file by file: allow time for a large store.
const FOLDER_CHECK: Duration = Duration::from_secs(60 * 60);
const HTML_FILE: (&str, &[&str]) = ("Web page", &["html"]);
/// The sidecar enforces the same page size.
const MAX_PAGE: u32 = 500;
const MAX_OFFSET: u32 = 10_000_000;

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
pub struct LogPage {
    offset: u32,
    limit: u32,
    action: Option<String>,
    text: Option<String>,
}

/// An action kind like `job` or `examiner.note`: lower-case words joined by one dot.
fn action_kind(value: &str) -> Result<String, IpcError> {
    let words: Vec<&str> = value.split('.').collect();
    let word_ok =
        |w: &&str| !w.is_empty() && w.bytes().all(|b| b.is_ascii_lowercase() || b == b'_');
    if value.len() <= 40 && words.len() <= 2 && words.iter().all(word_ok) {
        Ok(value.to_owned())
    } else {
        Err(IpcError::invalid("not a kind of custody entry"))
    }
}

/// A page of the custody log, newest first (read only).
#[tauri::command]
pub async fn custody_log(
    app: AppHandle,
    window: WebviewWindow,
    request: LogPage,
) -> Result<Value, IpcError> {
    require(&window, MAIN_LABEL)?;
    if request.offset > MAX_OFFSET || request.limit == 0 || request.limit > MAX_PAGE {
        return Err(IpcError::invalid(
            "the page of the custody log is out of range",
        ));
    }
    let action = request.action.as_deref().map(action_kind).transpose()?;
    let text = validate::optional_text(request.text.as_deref(), "search text", 100)?;
    let params =
        json!({"offset": request.offset, "limit": request.limit, "action": action, "text": text});
    call(&app, "log.entries", params, QUICK).await
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ReportRef {
    job_id: String,
}

/// Write a readable HTML rendering of a verified report (logged).
#[tauri::command]
pub async fn export_report_html(
    app: AppHandle,
    window: WebviewWindow,
    request: ReportRef,
) -> Result<Value, IpcError> {
    require(&window, MAIN_LABEL)?;
    let job_id = validate::uuid(&request.job_id, "job")?;
    let suggested = Some(format!("ridge_job_{}_report.html", &job_id[..8]));
    let title = "Save a readable copy of the report";
    let dest = path_text(&dialogs::save_file(&app, title, suggested, HTML_FILE).await?)?;
    let params = json!({"job_id": job_id, "dest": dest, "overwrite": false});
    call(&app, "report.export_html", params, RECORD_IO).await
}

/// Write the AFIS submission cover sheet of a verified report (FR-38; logged, not signed).
#[tauri::command]
pub async fn export_cover(
    app: AppHandle,
    window: WebviewWindow,
    request: ReportRef,
) -> Result<Value, IpcError> {
    require(&window, MAIN_LABEL)?;
    let job_id = validate::uuid(&request.job_id, "job")?;
    let suggested = Some(format!("ridge_job_{}_submission_cover.html", &job_id[..8]));
    let title = "Save the submission cover sheet";
    let dest = path_text(&dialogs::save_file(&app, title, suggested, HTML_FILE).await?)?;
    let params = json!({"job_id": job_id, "dest": dest, "overwrite": false});
    call(&app, "cover.export", params, RECORD_IO).await
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
pub struct CheckRequest {
    folder: bool,
    with_register: bool,
}

const JSON_FILE: (&str, &[&str]) = ("Ridge file (JSON)", &["json"]);

/// Verify an exported file, or a disclosure package or store backup folder, chosen in a native
/// dialog; with a key register (a second dialog) the signer is named. Needs no store and writes
/// nothing.
#[tauri::command]
pub async fn check_exported(
    app: AppHandle,
    window: WebviewWindow,
    request: CheckRequest,
) -> Result<Value, IpcError> {
    require(&window, MAIN_LABEL)?;
    let path = if request.folder {
        dialogs::pick_folder(&app, "Choose a disclosure package or store backup folder").await?
    } else {
        dialogs::pick_file(&app, "Choose an exported Ridge file", JSON_FILE).await?
    };
    let register = if request.with_register {
        let chosen =
            dialogs::pick_file(&app, "Choose the laboratory's key register", JSON_FILE).await?;
        Some(path_text(&chosen)?)
    } else {
        None
    };
    let params = json!({"path": path_text(&path)?, "register": register});
    let timeout = if request.folder {
        FOLDER_CHECK
    } else {
        RECORD_IO
    };
    call(&app, "files.check", params, timeout).await
}

#[cfg(test)]
mod tests {
    use super::action_kind;

    #[test]
    fn action_kinds_are_plain_words() {
        for good in ["job", "examiner.note", "report.export_html"] {
            assert!(action_kind(good).is_ok(), "{good}");
        }
        for bad in [
            "",
            "Job",
            "a.b.c",
            "job.",
            ".job",
            "job start",
            "../x",
            &"x".repeat(41),
        ] {
            assert!(action_kind(bad).is_err(), "{bad}");
        }
    }
}
