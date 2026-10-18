//! The one setting the GUI keeps: the last case store the examiner chose, so the next start can
//! show it again. It is a folder path (no case data, no secret), written by the Rust core to the
//! application's config folder, never to WebView storage. A remembered path is used only if it
//! is still an absolute path to an existing folder.

use std::fs;
use std::path::{Path, PathBuf};

use serde::{Deserialize, Serialize};
use tauri::{AppHandle, Manager};

const FILE: &str = "last-store.json";
const MAX_BYTES: u64 = 16 * 1024;

#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct Remembered {
    store: PathBuf,
}

fn file(app: &AppHandle) -> Option<PathBuf> {
    app.path().app_config_dir().ok().map(|dir| dir.join(FILE))
}

/// The remembered store, if it is still usable.
pub fn load(app: &AppHandle) -> Option<PathBuf> {
    #[cfg(debug_assertions)]
    if let Some(dev) = std::env::var_os("RIDGE_DEV_STORE") {
        return usable(PathBuf::from(dev)); // development and E2E runs only
    }
    read(&file(app)?)
}

fn read(path: &Path) -> Option<PathBuf> {
    if fs::metadata(path).ok()?.len() > MAX_BYTES {
        return None;
    }
    let remembered: Remembered = serde_json::from_slice(&fs::read(path).ok()?).ok()?;
    usable(remembered.store)
}

fn usable(store: PathBuf) -> Option<PathBuf> {
    (store.is_absolute() && store.is_dir()).then_some(store)
}

/// Remember `store` for the next start (best effort: failing to remember is not an error).
pub fn remember(app: &AppHandle, store: &Path) {
    if let Some(path) = file(app) {
        write(&path, store);
    }
}

fn write(path: &Path, store: &Path) {
    let Ok(text) = serde_json::to_vec(&Remembered {
        store: store.to_path_buf(),
    }) else {
        return;
    };
    if let Some(dir) = path.parent() {
        let _ = fs::create_dir_all(dir);
    }
    let _ = fs::write(path, text);
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn remembers_only_existing_absolute_folders() {
        let dir = std::env::temp_dir().join(format!("ridge-settings-{}", std::process::id()));
        fs::create_dir_all(&dir).unwrap();
        let file = dir.join(FILE);
        write(&file, &dir);
        assert_eq!(read(&file), Some(dir.clone()));
        write(&file, &dir.join("gone"));
        assert_eq!(read(&file), None);
        fs::write(&file, br#"{"store":"relative/path"}"#).unwrap();
        assert_eq!(read(&file), None);
        fs::write(&file, br#"{"store":"/x","extra":1}"#).unwrap();
        assert_eq!(read(&file), None);
        fs::write(&file, vec![b' '; 20_000]).unwrap();
        assert_eq!(read(&file), None);
        fs::remove_dir_all(&dir).unwrap();
    }
}
