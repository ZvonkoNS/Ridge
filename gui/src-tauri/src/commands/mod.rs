//! Tauri commands: thin handlers that validate, map to one sidecar method, and return a typed
//! result or a typed error (desktop_gui_tauri_standards.md §3). The allow-list is in `list.rs`;
//! `build.rs` generates permissions for exactly these, and the capability files grant them.

pub mod annotations;
pub mod case;
pub mod check;
pub mod jobs;
pub mod metadata;
pub mod notes;
pub mod package;
pub mod prompt;
pub mod records;
pub mod recovery;
pub mod store;
pub mod triage;

include!("list.rs");
