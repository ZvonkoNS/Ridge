//! Build script: the command allow-list for the ACL, and the development sidecar location.

use std::path::PathBuf;

include!("src/commands/list.rs");

fn main() {
    println!("cargo:rerun-if-changed=src/commands/list.rs");
    // Debug builds run the sidecar from the repository virtualenv (`pip install -e .`); release
    // builds use the copy bundled in the application resources only (sidecar::locate).
    let manifest = PathBuf::from(std::env::var("CARGO_MANIFEST_DIR").unwrap_or_default());
    let scripts = if std::env::var("CARGO_CFG_TARGET_OS").as_deref() == Ok("windows") {
        "Scripts"
    } else {
        "bin"
    };
    let venv = manifest.join("..").join("..").join(".venv").join(scripts);
    println!("cargo:rustc-env=RIDGE_DEV_SIDECAR_DIR={}", venv.display());

    let all: Vec<&'static str> = MAIN_COMMANDS
        .iter()
        .chain(PROMPT_COMMANDS)
        .copied()
        .collect();
    let manifest = tauri_build::AppManifest::new().commands(Box::leak(all.into_boxed_slice()));
    if let Err(error) =
        tauri_build::try_build(tauri_build::Attributes::new().app_manifest(manifest))
    {
        println!("cargo:warning={error:#}");
        std::process::exit(1);
    }
}
