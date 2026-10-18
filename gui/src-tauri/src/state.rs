//! Application state owned by the trusted Rust core. The WebView never sees paths it could send
//! back: the store folder and every file path come from native dialogs and stay here.

use std::path::PathBuf;
use std::sync::Mutex;
use std::time::Duration;

use serde::Serialize;
use serde_json::Value;
use tauri::{AppHandle, Manager};

use crate::error::{ErrorKind, IpcError};
use crate::prompt::{Pending, Secret};
use crate::sidecar::{ChildTransport, Sidecar};

/// Everything the commands share.
pub struct AppState {
    pub sidecar: Mutex<Sidecar<ChildTransport>>,
    pub store: Mutex<Option<PathBuf>>,
    pub prompt: Mutex<Option<Pending>>,
    /// The first passphrase of a two-step recovery task, until the second prompt uses it (zeroised).
    pub recovery: Mutex<Option<Secret>>,
}

impl AppState {
    pub fn new(sidecar: Sidecar<ChildTransport>) -> Self {
        Self {
            sidecar: Mutex::new(sidecar),
            store: Mutex::new(None),
            prompt: Mutex::new(None),
            recovery: Mutex::new(None),
        }
    }
}

fn poisoned() -> IpcError {
    IpcError::unavailable("internal state error; restart Ridge")
}

/// Call the sidecar on a blocking thread (the mutex serialises requests: the sidecar is single-threaded).
pub async fn call<P: Serialize + Send + 'static>(
    app: &AppHandle,
    method: &'static str,
    params: P,
    timeout: Duration,
) -> Result<Value, IpcError> {
    let app = app.clone();
    blocking(move || call_now(&app, method, &params, timeout)).await
}

/// Call the sidecar from a thread that may block.
pub fn call_now<P: Serialize>(
    app: &AppHandle,
    method: &str,
    params: &P,
    timeout: Duration,
) -> Result<Value, IpcError> {
    let state = app.state::<AppState>();
    let mut sidecar = state.sidecar.lock().map_err(|_| poisoned())?;
    sidecar.call(method, params, timeout)
}

/// Run blocking work (sidecar calls, native dialogs) off the async runtime's worker threads.
pub async fn blocking<T: Send + 'static>(
    work: impl FnOnce() -> Result<T, IpcError> + Send + 'static,
) -> Result<T, IpcError> {
    tauri::async_runtime::spawn_blocking(work)
        .await
        .map_err(|_| IpcError::unavailable("internal task error"))?
}

/// The store chosen in the folder dialog.
pub fn store(app: &AppHandle) -> Result<PathBuf, IpcError> {
    let state = app.state::<AppState>();
    let store = state.store.lock().map_err(|_| poisoned())?;
    store
        .clone()
        .ok_or_else(|| IpcError::new(ErrorKind::NoStore, "choose a case store first"))
}

pub fn set_store(app: &AppHandle, path: PathBuf) -> Result<(), IpcError> {
    let state = app.state::<AppState>();
    let mut store = state.store.lock().map_err(|_| poisoned())?;
    *store = Some(path);
    Ok(())
}

/// The prompt slot (one passphrase prompt at a time).
pub fn with_prompt<T>(
    app: &AppHandle,
    f: impl FnOnce(&mut Option<Pending>) -> T,
) -> Result<T, IpcError> {
    let state = app.state::<AppState>();
    let mut slot = state.prompt.lock().map_err(|_| poisoned())?;
    Ok(f(&mut slot))
}

/// Hold the first passphrase of a recovery task for the next prompt.
pub fn stash_recovery(app: &AppHandle, secret: Secret) -> Result<(), IpcError> {
    let state = app.state::<AppState>();
    *state.recovery.lock().map_err(|_| poisoned())? = Some(secret);
    Ok(())
}

/// Take (and so clear) the held recovery passphrase.
pub fn take_recovery(app: &AppHandle) -> Result<Option<Secret>, IpcError> {
    let state = app.state::<AppState>();
    let taken = state.recovery.lock().map_err(|_| poisoned())?.take();
    Ok(taken)
}

/// Lock an idle case from the trusted core, whatever the WebView does (checked every 15 s).
pub fn start_idle_watchdog(app: AppHandle) {
    std::thread::spawn(move || loop {
        std::thread::sleep(Duration::from_secs(15));
        let state = app.state::<AppState>();
        let guard = state.sidecar.lock();
        if let Ok(mut sidecar) = guard {
            sidecar.lock_if_idle(crate::sidecar::IDLE_LOCK);
        }
    });
}

/// Stop the sidecar (it locks the case and exits); used when the application closes.
pub fn shutdown(app: &AppHandle) {
    let state = app.state::<AppState>();
    let guard = state.sidecar.lock();
    if let Ok(mut sidecar) = guard {
        sidecar.stop();
    }
}

/// A path as the sidecar's JSON string (paths that are not valid Unicode cannot be sent).
pub fn path_text(path: &std::path::Path) -> Result<String, IpcError> {
    if !path.is_absolute() {
        return Err(IpcError::invalid(
            "the chosen location is not an absolute path",
        ));
    }
    path.to_str()
        .map(str::to_owned)
        .ok_or_else(|| IpcError::invalid("the chosen path is not valid Unicode"))
}
