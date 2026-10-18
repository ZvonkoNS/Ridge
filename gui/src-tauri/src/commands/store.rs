//! Store and session commands: choose a store, first run, create, unlock and lock cases.

use std::time::Duration;

use serde::Deserialize;
use serde_json::{json, Value};
use tauri::{AppHandle, WebviewWindow};

use crate::error::IpcError;
use crate::prompt::{self, Purpose};
use crate::state::{self, call, path_text};
use crate::windows::{require, MAIN_LABEL};
use crate::{dialogs, settings, validate};

const QUICK: Duration = Duration::from_secs(30);
/// A large store is copied file by file: allow time for it.
const BACKUP: Duration = Duration::from_secs(60 * 60);

/// Versions of the GUI and the processing engine.
#[tauri::command]
pub async fn app_info(app: AppHandle, window: WebviewWindow) -> Result<Value, IpcError> {
    require(&window, MAIN_LABEL)?;
    let engine = call(&app, "ridge.version", json!({}), QUICK).await?;
    Ok(json!({"gui": env!("CARGO_PKG_VERSION"), "engine": engine}))
}

/// What the store view shows: the folder (display only), the identity and the cases.
async fn store_view(app: &AppHandle) -> Result<Value, IpcError> {
    let store = path_text(&state::store(app)?)?;
    let identity = call(app, "store.identity", json!({"store": store}), QUICK).await?;
    let cases = call(app, "store.cases", json!({"store": store}), QUICK).await?;
    Ok(json!({"path": store, "identity": identity, "cases": cases}))
}

/// Choose the case-store folder in a native dialog.
#[tauri::command]
pub async fn choose_store(app: AppHandle, window: WebviewWindow) -> Result<Value, IpcError> {
    require(&window, MAIN_LABEL)?;
    let folder = dialogs::pick_folder(&app, "Choose the case store folder").await?;
    path_text(&folder)?;
    let _ = call(&app, "session.lock", json!({}), QUICK).await; // a new store never keeps another case open
    settings::remember(&app, &folder);
    state::set_store(&app, folder)?;
    store_view(&app).await
}

/// Re-read the chosen store.
#[tauri::command]
pub async fn refresh_store(app: AppHandle, window: WebviewWindow) -> Result<Value, IpcError> {
    require(&window, MAIN_LABEL)?;
    store_view(&app).await
}

/// First run: create the examiner identity (the passphrase is entered in the prompt window).
#[tauri::command]
pub async fn create_identity(app: AppHandle, window: WebviewWindow) -> Result<Value, IpcError> {
    require(&window, MAIN_LABEL)?;
    let store = state::store(&app)?;
    prompt::ask(&app, Purpose::CreateIdentity { store }).await
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
pub struct NewCase {
    reference: String,
    legal_basis: String,
    retention_until: String,
}

/// Create a case (FR-20) and open it; the passphrase is entered in the prompt window.
#[tauri::command]
pub async fn create_case(
    app: AppHandle,
    window: WebviewWindow,
    request: NewCase,
) -> Result<Value, IpcError> {
    require(&window, MAIN_LABEL)?;
    let purpose = Purpose::CreateCase {
        store: state::store(&app)?,
        reference: validate::text(&request.reference, "case reference", 200)?,
        legal_basis: validate::text(&request.legal_basis, "legal basis", 500)?,
        retention_until: validate::date(&request.retention_until, "retention date")?,
    };
    prompt::ask(&app, purpose).await
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
pub struct CaseRef {
    case_id: String,
}

/// Unlock a case of the chosen store; the passphrase is entered in the prompt window.
#[tauri::command]
pub async fn unlock_case(
    app: AppHandle,
    window: WebviewWindow,
    request: CaseRef,
) -> Result<Value, IpcError> {
    require(&window, MAIN_LABEL)?;
    let purpose = Purpose::Unlock {
        store: state::store(&app)?,
        case_id: validate::uuid(&request.case_id, "case")?,
    };
    prompt::ask(&app, purpose).await
}

/// Verify every case of the chosen store; the passphrase is entered in the prompt window.
#[tauri::command]
pub async fn verify_store(app: AppHandle, window: WebviewWindow) -> Result<Value, IpcError> {
    require(&window, MAIN_LABEL)?;
    let store = state::store(&app)?;
    prompt::ask(&app, Purpose::VerifyStore { store }).await
}

/// Show every case's reference, retention date and legal hold; the passphrase is entered in the
/// prompt window.
#[tauri::command]
pub async fn store_overview(app: AppHandle, window: WebviewWindow) -> Result<Value, IpcError> {
    require(&window, MAIN_LABEL)?;
    let store = state::store(&app)?;
    prompt::ask(&app, Purpose::StoreOverview { store }).await
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
pub struct KeyCardRequest {
    holder: String,
}

/// Export a self-signed key card for the laboratory's register: the examiner chooses the file in
/// a native dialog, then enters the passphrase in the prompt window.
#[tauri::command]
pub async fn export_key_card(
    app: AppHandle,
    window: WebviewWindow,
    request: KeyCardRequest,
) -> Result<Value, IpcError> {
    require(&window, MAIN_LABEL)?;
    let holder = validate::holder(&request.holder)?;
    let store = state::store(&app)?;
    let suggested = Some("ridge_key_card.json".to_owned());
    let dest =
        dialogs::save_file(&app, "Save your key card", suggested, ("JSON", &["json"])).await?;
    prompt::ask(
        &app,
        Purpose::KeyCard {
            store,
            holder,
            dest,
        },
    )
    .await
}

/// Copy the encrypted store to a new folder with a hash manifest (no passphrase; nothing decrypted).
#[tauri::command]
pub async fn backup_store(app: AppHandle, window: WebviewWindow) -> Result<Value, IpcError> {
    require(&window, MAIN_LABEL)?;
    let store = path_text(&state::store(&app)?)?;
    let suggested = "Ridge store backup".to_owned();
    let dest = dialogs::new_folder(&app, "Name the new backup folder", suggested).await?;
    let params = json!({"store": store, "dest": path_text(&dest)?});
    call(&app, "store.backup", params, BACKUP).await
}

/// Lock the open case.
#[tauri::command]
pub async fn lock_case(app: AppHandle, window: WebviewWindow) -> Result<Value, IpcError> {
    require(&window, MAIN_LABEL)?;
    call(&app, "session.lock", json!({}), QUICK).await
}

/// Whether a case is unlocked (the sidecar locks it after 15 idle minutes).
#[tauri::command]
pub async fn session_status(app: AppHandle, window: WebviewWindow) -> Result<Value, IpcError> {
    require(&window, MAIN_LABEL)?;
    call(&app, "session.status", json!({}), QUICK).await
}

/// The chosen store's limits of use (PRD §12 item 8), shown before any case is unlocked.
#[tauri::command]
pub async fn limits_of_use(app: AppHandle, window: WebviewWindow) -> Result<Value, IpcError> {
    require(&window, MAIN_LABEL)?;
    let store = path_text(&state::store(&app)?)?;
    call(&app, "store.limits", json!({"store": store}), QUICK).await
}

const REGISTER_FILE: (&str, &[&str]) = ("Key register (JSON)", &["json"]);

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
pub struct WorkstationRequest {
    with_register: bool,
}

/// Check the installation, the OS keystore, the chosen store and its limits of use; with a key
/// register (chosen in a native dialog) also whether the store's key is registered. Read-only:
/// nothing is decrypted or logged, and the device secret is only looked up.
#[tauri::command]
pub async fn workstation_check(
    app: AppHandle,
    window: WebviewWindow,
    request: WorkstationRequest,
) -> Result<Value, IpcError> {
    require(&window, MAIN_LABEL)?;
    let store = path_text(&state::store(&app)?)?;
    let register = if request.with_register {
        let chosen =
            dialogs::pick_file(&app, "Choose the laboratory's key register", REGISTER_FILE).await?;
        Some(path_text(&chosen)?)
    } else {
        None
    };
    let params = json!({"store": store, "register": register});
    call(&app, "store.workstation", params, QUICK).await
}
