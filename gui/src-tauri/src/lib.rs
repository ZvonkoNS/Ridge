//! Ridge desktop GUI, trusted Rust core (architecture §5, §7.3; ADR-002, ADR-010).
//!
//! The WebViews are untrusted. They call only the commands in `commands::list.rs`, each granted
//! to one window by a capability file. The core owns the native dialogs, the passphrase prompt,
//! the case-store location and the Python sidecar, which it talks to over stdio (no sockets).
//! Ridge is an image-enhancement aid: nothing here identifies, matches or scores anyone.

#![cfg_attr(test, allow(clippy::unwrap_used, clippy::expect_used, clippy::panic))]

mod commands;
mod dialogs;
mod error;
mod prompt;
mod prompt_calls;
mod rpc;
mod settings;
mod sidecar;
mod state;
mod validate;
mod windows;

use tauri::{Manager, RunEvent, WindowEvent};

use crate::sidecar::Sidecar;
use crate::state::AppState;

/// Environment variables that would attach a debugger to the WebViews or swap their engine or
/// profile. A process running as the same user could otherwise start Ridge with a DevTools port,
/// wait until a case is unlocked and drive the IPC (previews of decrypted images). Release builds
/// drop them before any window or thread exists; debug builds keep them for development.
pub const WEBVIEW_ENV: [&str; 8] = [
    "WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS",
    "WEBVIEW2_BROWSER_EXECUTABLE_FOLDER",
    "WEBVIEW2_USER_DATA_FOLDER",
    "WEBVIEW2_RELEASE_CHANNEL_PREFERENCE",
    "WEBVIEW2_PIPE_FOR_SCRIPT_DEBUGGER",
    "WEBKIT_INSPECTOR_SERVER",
    "WEBKIT_INSPECTOR_HTTP_SERVER",
    "WEBKIT_INSPECTOR_PIPE",
];

fn scrub_webview_environment() {
    if cfg!(debug_assertions) {
        return;
    }
    for name in WEBVIEW_ENV {
        // Edition 2021: safe here because no other thread exists yet (first statement of `run`).
        std::env::remove_var(name);
    }
}

/// Start the application.
pub fn run() {
    scrub_webview_environment();
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .setup(|app| {
            let program = sidecar::locate(app.path().resource_dir().ok());
            let launch = move || match &program {
                Some(path) => sidecar::spawn(path),
                None => Err(std::io::Error::other(
                    "the processing engine is not bundled",
                )),
            };
            app.manage(AppState::new(Sidecar::new(Box::new(launch))));
            state::start_idle_watchdog(app.handle().clone());
            if let Some(store) = settings::load(app.handle()) {
                state::set_store(app.handle(), store)?;
            }
            windows::build_main(app.handle())?;
            Ok(())
        })
        .on_window_event(|window, event| {
            if let WindowEvent::Destroyed = event {
                match window.label() {
                    windows::PROMPT_LABEL => prompt::abandon(window.app_handle()),
                    windows::MAIN_LABEL => {
                        windows::close_prompt(window.app_handle());
                        state::shutdown(window.app_handle());
                    }
                    _ => {}
                }
            }
        })
        .invoke_handler(tauri::generate_handler![
            commands::store::app_info,
            commands::store::choose_store,
            commands::store::refresh_store,
            commands::store::create_identity,
            commands::store::create_case,
            commands::store::unlock_case,
            commands::store::lock_case,
            commands::store::session_status,
            commands::case::case_info,
            commands::case::case_status,
            commands::case::set_legal_hold,
            commands::case::list_items,
            commands::case::import_evidence,
            commands::case::import_reference,
            commands::case::verify_case,
            commands::case::export_item,
            commands::case::preview,
            commands::case::preview_region,
            commands::jobs::run_job,
            commands::jobs::list_jobs,
            commands::jobs::get_report,
            commands::jobs::export_report,
            commands::jobs::reproduce_job,
            commands::jobs::export_log,
            commands::jobs::export_comparison,
            commands::jobs::get_minutiae,
            commands::store::limits_of_use,
            commands::jobs::export_head,
            commands::store::verify_store,
            commands::store::store_overview,
            commands::notes::add_note,
            commands::notes::list_notes,
            commands::package::export_package,
            commands::records::custody_log,
            commands::records::export_report_html,
            commands::store::export_key_card,
            commands::records::check_exported,
            commands::store::backup_store,
            commands::case::export_all,
            commands::store::workstation_check,
            commands::prompt::passphrase_context,
            commands::prompt::passphrase_submit,
            commands::prompt::passphrase_cancel,
        ])
        .build(tauri::generate_context!());
    match app {
        Ok(app) => app.run(|handle, event| {
            if let RunEvent::Exit = event {
                state::shutdown(handle); // end of input: the sidecar locks the case and exits
            }
        }),
        Err(error) => eprintln!("Ridge could not start: {error}"),
    }
}

#[cfg(test)]
mod tests {
    use crate::commands::{MAIN_COMMANDS, PROMPT_COMMANDS};
    use serde_json::Value;

    fn granted(capability: &str) -> Vec<String> {
        let parsed: Value = serde_json::from_str(capability).unwrap();
        assert!(
            parsed.get("remote").is_none(),
            "capabilities never grant remote origins"
        );
        parsed["permissions"]
            .as_array()
            .unwrap()
            .iter()
            .map(|p| p.as_str().unwrap().to_owned())
            .collect()
    }

    fn allow(commands: &[&str]) -> Vec<String> {
        commands
            .iter()
            .map(|c| format!("allow-{}", c.replace('_', "-")))
            .collect()
    }

    #[test]
    fn each_window_is_granted_exactly_its_own_commands() {
        let main: Value = serde_json::from_str(include_str!("../capabilities/main.json")).unwrap();
        assert_eq!(main["windows"], serde_json::json!(["main"]));
        assert_eq!(
            granted(include_str!("../capabilities/main.json")),
            allow(MAIN_COMMANDS)
        );
        let prompt: Value =
            serde_json::from_str(include_str!("../capabilities/passphrase.json")).unwrap();
        assert_eq!(prompt["windows"], serde_json::json!(["passphrase"]));
        assert_eq!(
            granted(include_str!("../capabilities/passphrase.json")),
            allow(PROMPT_COMMANDS)
        );
    }

    #[test]
    fn the_csp_forbids_remote_and_inline_code() {
        let config: Value = serde_json::from_str(include_str!("../tauri.conf.json")).unwrap();
        let csp = &config["app"]["security"]["csp"];
        assert_eq!(csp["default-src"], "'self'");
        assert_eq!(csp["script-src"], "'self'");
        assert_eq!(csp["object-src"], "'none'");
        assert_eq!(csp["worker-src"], "'none'");
        // Only the app itself, preview blobs and Tauri's IPC endpoints; no remote origin, no inline code.
        let allowed = ["'self'", "'none'", "blob:", "ipc:", "http://ipc.localhost"];
        for (directive, sources) in csp.as_object().unwrap() {
            for source in sources.as_str().unwrap().split_whitespace() {
                assert!(allowed.contains(&source), "{directive}: {source}");
            }
        }
        assert_eq!(csp["connect-src"], "ipc: http://ipc.localhost");
        assert_eq!(config["app"]["withGlobalTauri"], false);
        assert!(config["plugins"]
            .as_object()
            .is_none_or(|p| p.keys().all(|k| k == "dialog")));
    }
}
