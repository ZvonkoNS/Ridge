//! Native file dialogs, opened by the Rust core only. The WebView has no dialog permission and
//! never sends a path: it asks for an action, and the examiner chooses the file here.

use std::path::PathBuf;

use tauri::{AppHandle, Manager};
use tauri_plugin_dialog::{DialogExt, FileDialogBuilder};

use crate::error::IpcError;
use crate::state::blocking;
use crate::windows::MAIN_LABEL;

/// Image formats the sidecar decodes (FR-8); the dialog filter is a convenience, the sidecar
/// identifies formats by content.
const IMAGE_EXTENSIONS: [&str; 9] = [
    "jpg", "jpeg", "png", "tif", "tiff", "bmp", "webp", "heic", "heif",
];

fn builder(app: &AppHandle, title: &str) -> FileDialogBuilder<tauri::Wry> {
    let mut dialog = app.dialog().file().set_title(title);
    if let Some(main) = app.get_webview_window(MAIN_LABEL) {
        dialog = dialog.set_parent(&main);
    }
    dialog
}

fn chosen(path: Option<tauri_plugin_dialog::FilePath>) -> Result<PathBuf, IpcError> {
    path.ok_or_else(IpcError::cancelled)?
        .into_path()
        .map_err(|_| IpcError::invalid("choose a file on this computer"))
}

/// Choose the case-store folder.
pub async fn pick_folder(app: &AppHandle, title: &'static str) -> Result<PathBuf, IpcError> {
    let app = app.clone();
    blocking(move || {
        chosen(
            builder(&app, title)
                .set_can_create_directories(true)
                .blocking_pick_folder(),
        )
    })
    .await
}

/// Choose an image to import.
pub async fn pick_image(app: &AppHandle, title: &'static str) -> Result<PathBuf, IpcError> {
    let app = app.clone();
    blocking(move || {
        chosen(
            builder(&app, title)
                .add_filter("Images", &IMAGE_EXTENSIONS)
                .blocking_pick_file(),
        )
    })
    .await
}

/// Choose one or more images to import, at most `max`.
pub async fn pick_images(
    app: &AppHandle,
    title: &'static str,
    max: usize,
) -> Result<Vec<PathBuf>, IpcError> {
    let app = app.clone();
    blocking(move || {
        let picked = builder(&app, title)
            .add_filter("Images", &IMAGE_EXTENSIONS)
            .blocking_pick_files()
            .ok_or_else(IpcError::cancelled)?;
        if picked.len() > max {
            return Err(IpcError::invalid(&format!(
                "choose at most {max} photos at a time"
            )));
        }
        picked.into_iter().map(|p| chosen(Some(p))).collect()
    })
    .await
}

/// Choose where to save an export. `suggested` is reduced to a bare file name.
pub async fn save_file(
    app: &AppHandle,
    title: &'static str,
    suggested: Option<String>,
    filter: (&'static str, &'static [&'static str]),
) -> Result<PathBuf, IpcError> {
    let app = app.clone();
    let name = suggested.map(|s| file_name(&s)).filter(|s| !s.is_empty());
    blocking(move || {
        let mut dialog = builder(&app, title).add_filter(filter.0, filter.1);
        if let Some(name) = name {
            dialog = dialog.set_file_name(name);
        }
        chosen(dialog.blocking_save_file())
    })
    .await
}

/// Choose the name and place of a new folder (the sidecar creates it and refuses an existing one).
pub async fn new_folder(
    app: &AppHandle,
    title: &'static str,
    suggested: String,
) -> Result<PathBuf, IpcError> {
    let app = app.clone();
    let name = file_name(&suggested);
    blocking(move || {
        chosen(
            builder(&app, title)
                .set_file_name(name)
                .set_can_create_directories(true)
                .blocking_save_file(),
        )
    })
    .await
}

/// A suggestion from the WebView becomes a plain file name: no separators, no reserved characters.
pub fn file_name(suggested: &str) -> String {
    let base = suggested.rsplit(['/', '\\']).next().unwrap_or_default();
    let cleaned: String = base
        .chars()
        .map(|c| {
            if c.is_control() || "<>:\"|?*".contains(c) {
                '_'
            } else {
                c
            }
        })
        .take(120)
        .collect();
    cleaned
        .trim_matches(|c: char| c == '.' || c.is_whitespace())
        .to_owned()
}

#[cfg(test)]
mod tests {
    use super::file_name;

    #[test]
    fn suggestions_cannot_carry_paths() {
        assert_eq!(file_name("finger_print.png"), "finger_print.png");
        assert_eq!(file_name("../../etc/passwd"), "passwd");
        assert_eq!(file_name("C:\\Windows\\x.png"), "x.png");
        assert_eq!(file_name("a:b|c?.png"), "a_b_c_.png");
        assert_eq!(file_name(".."), "");
        assert_eq!(file_name(&"x".repeat(500)).len(), 120);
    }
}
