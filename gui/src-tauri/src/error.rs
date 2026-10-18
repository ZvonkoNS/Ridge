//! Typed IPC errors: what the WebView may learn about a failure (no paths, no internals).

use serde::Serialize;

/// Category of a failed command, for the UI to choose a message and a next step.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ErrorKind {
    /// The WebView sent a value the Rust core refuses.
    Invalid,
    /// Ridge refused or failed; the message comes from the sidecar and is safe to show.
    Refused,
    /// The examiner closed a dialog or the passphrase prompt.
    Cancelled,
    /// Another passphrase prompt is already open.
    Busy,
    /// No store has been chosen yet.
    NoStore,
    /// The processing engine (sidecar) is not available: it stopped, timed out or is missing.
    Unavailable,
}

/// Error returned by every command.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct IpcError {
    pub kind: ErrorKind,
    pub message: String,
    /// The sidecar refused one input file (wrong format, too large); a batch may go on. Never sent
    /// to the WebView, which sees an ordinary refusal.
    #[serde(skip)]
    pub input_refused: bool,
}

impl IpcError {
    pub fn new(kind: ErrorKind, message: &str) -> Self {
        Self {
            kind,
            message: message.to_owned(),
            input_refused: false,
        }
    }

    pub fn invalid(message: &str) -> Self {
        Self::new(ErrorKind::Invalid, message)
    }

    pub fn refused(message: &str) -> Self {
        Self::new(ErrorKind::Refused, message)
    }

    /// The sidecar refused one input file (JSON-RPC code `INPUT_REFUSED`).
    pub fn input_refused(message: &str) -> Self {
        Self {
            input_refused: true,
            ..Self::refused(message)
        }
    }

    pub fn cancelled() -> Self {
        Self::new(ErrorKind::Cancelled, "cancelled")
    }

    pub fn unavailable(message: &str) -> Self {
        Self::new(ErrorKind::Unavailable, message)
    }
}

impl std::fmt::Display for IpcError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(&self.message)
    }
}

impl std::error::Error for IpcError {}
