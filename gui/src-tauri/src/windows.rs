//! Window creation with the navigation policy: the WebViews show bundled pages only.
//!
//! Navigation to anything outside the app origin is blocked and new windows are denied
//! (desktop_gui_tauri_standards.md §4). DevTools are off in release builds (Tauri default).

use tauri::webview::NewWindowResponse;
use tauri::{AppHandle, Manager, Url, WebviewUrl, WebviewWindow, WebviewWindowBuilder};

use crate::error::IpcError;

pub const MAIN_LABEL: &str = "main";
pub const PROMPT_LABEL: &str = "passphrase";
/// Vite dev server port (`gui/vite.config.ts`); allowed in debug builds only.
pub const DEV_PORT: u16 = 1420;

/// Whether a WebView may navigate to `url`: the bundled app origin only.
pub fn navigation_allowed(url: &Url) -> bool {
    match (url.scheme(), url.host_str()) {
        ("tauri", Some("localhost")) => true,
        ("http" | "https", Some("tauri.localhost")) => true, // Windows serves the app from this origin
        ("http", Some("localhost")) => cfg!(debug_assertions) && url.port() == Some(DEV_PORT),
        _ => false,
    }
}

fn hardened<'a>(
    builder: WebviewWindowBuilder<'a, tauri::Wry, AppHandle>,
) -> WebviewWindowBuilder<'a, tauri::Wry, AppHandle> {
    builder
        .on_navigation(navigation_allowed)
        .on_new_window(|_, _| NewWindowResponse::Deny)
}

/// The main application window.
pub fn build_main(app: &AppHandle) -> tauri::Result<WebviewWindow> {
    hardened(WebviewWindowBuilder::new(
        app,
        MAIN_LABEL,
        WebviewUrl::App("index.html".into()),
    ))
    .title("Ridge")
    .inner_size(1360.0, 880.0)
    .min_inner_size(1024.0, 700.0)
    .center()
    .build()
}

/// The passphrase prompt: a separate, owned window with its own page and capability. The main
/// WebView never receives the passphrase (ADR-010).
pub fn build_prompt(app: &AppHandle) -> tauri::Result<WebviewWindow> {
    let mut builder = hardened(WebviewWindowBuilder::new(
        app,
        PROMPT_LABEL,
        WebviewUrl::App("passphrase.html".into()),
    ))
    .title("Ridge - passphrase")
    .inner_size(460.0, 360.0)
    .resizable(false)
    .minimizable(false)
    .maximizable(false)
    .center()
    .focused(true);
    if let Some(main) = app.get_webview_window(MAIN_LABEL) {
        builder = builder.parent(&main)?;
    }
    builder.build()
}

pub fn close_prompt(app: &AppHandle) {
    if let Some(window) = app.get_webview_window(PROMPT_LABEL) {
        let _ = window.destroy();
    }
}

/// Defense in depth beyond the capability files: a command answers only its own window.
pub fn require(window: &WebviewWindow, label: &str) -> Result<(), IpcError> {
    if window.label() == label {
        Ok(())
    } else {
        Err(IpcError::invalid("this window may not use that command"))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn only_the_app_origin_is_navigable() {
        for allowed in [
            "tauri://localhost/index.html",
            "http://tauri.localhost/passphrase.html",
        ] {
            assert!(
                navigation_allowed(&Url::parse(allowed).unwrap()),
                "{allowed}"
            );
        }
        for refused in [
            "https://example.com/",
            "file:///C:/Windows/win.ini",
            "http://localhost:8080/",
            "http://tauri.localhost.example.com/",
            "data:text/html,hi",
            "javascript:alert(1)",
            "ftp://tauri.localhost/",
        ] {
            assert!(
                !navigation_allowed(&Url::parse(refused).unwrap()),
                "{refused}"
            );
        }
        let dev = Url::parse("http://localhost:1420/").unwrap();
        assert_eq!(navigation_allowed(&dev), cfg!(debug_assertions));
    }
}
