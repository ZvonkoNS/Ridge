// The command allow-list, shared by the crate and build.rs (one source of truth).

/// Commands of the main window (capability `main`).
#[allow(dead_code)] // read by build.rs and the capability tests
pub const MAIN_COMMANDS: &[&str] = &[
    "app_info",
    "choose_store",
    "refresh_store",
    "create_identity",
    "create_case",
    "unlock_case",
    "lock_case",
    "session_status",
    "case_info",
    "case_status",
    "set_legal_hold",
    "list_items",
    "import_evidence",
    "import_reference",
    "verify_case",
    "export_item",
    "preview",
    "preview_region",
    "run_job",
    "list_jobs",
    "get_report",
    "export_report",
    "reproduce_job",
    "export_log",
    "export_comparison",
    "get_minutiae",
    "limits_of_use",
    "export_head",
    "verify_store",
    "store_overview",
    "add_note",
    "list_notes",
    "export_package",
    "custody_log",
    "export_report_html",
    "export_key_card",
    "check_exported",
    "backup_store",
    "export_all",
    "workstation_check",
];

/// Commands of the passphrase window (capability `passphrase`).
#[allow(dead_code)] // read by build.rs and the capability tests
pub const PROMPT_COMMANDS: &[&str] = &["passphrase_context", "passphrase_submit", "passphrase_cancel"];
