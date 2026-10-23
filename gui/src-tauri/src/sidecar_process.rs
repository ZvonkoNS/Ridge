//! The sidecar process itself: spawning it from the bundle with a scrubbed environment, bounded
//! line reads on a reader thread, and shutdown. `sidecar` builds the request/response protocol,
//! timeouts and bounded restarts on top of the `Transport` trait defined here.
//!
//! Rules (desktop_gui_tauri_standards.md §2, §8): stdio only; the binary comes from the application
//! bundle (debug builds: the repository virtualenv, fixed at compile time), never from PATH, the
//! working directory or user input; every response line is size-limited.

use std::io::{self, BufRead, BufReader, Read, Write};
use std::path::{Path, PathBuf};
use std::process::{Child, ChildStdin, ChildStdout, Command, Stdio};
use std::sync::mpsc::{self, Receiver, RecvTimeoutError};
use std::thread;
use std::time::{Duration, Instant};

use crate::rpc::MAX_RESPONSE_BYTES;

/// Variables that would let the environment change which Python code, or which keystore, the sidecar uses.
const SCRUBBED_ENV: [&str; 10] = [
    "PYTHONPATH",
    "PYTHONHOME",
    "PYTHONSTARTUP",
    "PYTHONINSPECT",
    "PYTHONEXECUTABLE",
    "PYTHONBREAKPOINT",
    "PYTHONWARNINGS",
    "PYTHONDEBUG",
    "PYTHONVERBOSE",
    "PYTHON_KEYRING_BACKEND", // would let the environment replace the OS keystore
];

/// Why receiving a line failed.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ReceiveError {
    Timeout,
    Closed,
    TooLarge,
}

/// A line-based duplex channel to a sidecar.
pub trait Transport: Send {
    fn send(&mut self, line: &[u8]) -> io::Result<()>;
    fn receive(&mut self, timeout: Duration) -> Result<Vec<u8>, ReceiveError>;
    /// Stop the sidecar: close its input (it locks the case and exits), then kill it if needed.
    fn shutdown(&mut self);
}

/// The real sidecar process.
pub struct ChildTransport {
    child: Child,
    stdin: Option<ChildStdin>,
    lines: Receiver<Result<Vec<u8>, ReceiveError>>,
}

/// Start the sidecar binary with a scrubbed Python environment and piped stdio.
pub fn spawn(program: &Path) -> io::Result<ChildTransport> {
    let mut command = Command::new(program);
    command
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(if cfg!(debug_assertions) {
            Stdio::inherit()
        } else {
            Stdio::null()
        });
    for name in SCRUBBED_ENV {
        command.env_remove(name);
    }
    command
        .env("PYTHONNOUSERSITE", "1")
        .env("PYTHONDONTWRITEBYTECODE", "1")
        .env("PYTHONSAFEPATH", "1");
    if let Some(dir) = program.parent() {
        command.current_dir(dir);
    }
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        const CREATE_NO_WINDOW: u32 = 0x0800_0000;
        command.creation_flags(CREATE_NO_WINDOW);
    }
    let mut child = command.spawn()?;
    let stdin = child.stdin.take();
    let stdout = child
        .stdout
        .take()
        .ok_or_else(|| io::Error::other("sidecar has no stdout"))?;
    Ok(ChildTransport {
        child,
        stdin,
        lines: read_lines(stdout),
    })
}

fn read_lines(stdout: ChildStdout) -> Receiver<Result<Vec<u8>, ReceiveError>> {
    let (tx, rx) = mpsc::sync_channel(2);
    thread::spawn(move || {
        let mut reader = BufReader::new(stdout);
        loop {
            let mut line = Vec::new();
            let limit = u64::try_from(MAX_RESPONSE_BYTES)
                .unwrap_or(u64::MAX)
                .saturating_add(1);
            let outcome = match (&mut reader).take(limit).read_until(b'\n', &mut line) {
                Ok(0) | Err(_) => Err(ReceiveError::Closed),
                Ok(_) if line.last() == Some(&b'\n') => Ok(line),
                Ok(_) if line.len() > MAX_RESPONSE_BYTES => Err(ReceiveError::TooLarge),
                Ok(_) => Err(ReceiveError::Closed),
            };
            let stop = outcome.is_err();
            if tx.send(outcome).is_err() || stop {
                return;
            }
        }
    });
    rx
}

impl Transport for ChildTransport {
    fn send(&mut self, line: &[u8]) -> io::Result<()> {
        let stdin = self
            .stdin
            .as_mut()
            .ok_or_else(|| io::Error::other("sidecar input closed"))?;
        stdin.write_all(line)?;
        stdin.flush()
    }

    fn receive(&mut self, timeout: Duration) -> Result<Vec<u8>, ReceiveError> {
        match self.lines.recv_timeout(timeout) {
            Ok(line) => line,
            Err(RecvTimeoutError::Timeout) => Err(ReceiveError::Timeout),
            Err(RecvTimeoutError::Disconnected) => Err(ReceiveError::Closed),
        }
    }

    fn shutdown(&mut self) {
        drop(self.stdin.take()); // end of input: the sidecar locks the case and exits
        let deadline = Instant::now() + Duration::from_secs(3);
        while Instant::now() < deadline {
            if matches!(self.child.try_wait(), Ok(Some(_))) {
                return;
            }
            thread::sleep(Duration::from_millis(50));
        }
        let _ = self.child.kill();
        let _ = self.child.wait();
    }
}

impl Drop for ChildTransport {
    fn drop(&mut self) {
        self.shutdown();
    }
}

/// Start the sidecar found by `locate`; no location, or nothing there, is `NotFound`.
pub fn launch(program: Option<&Path>) -> io::Result<ChildTransport> {
    match program {
        Some(path) if path.is_file() => spawn(path),
        _ => Err(io::Error::new(
            io::ErrorKind::NotFound,
            "the processing engine is not bundled",
        )),
    }
}

/// Where the sidecar binary is: inside the bundle's resources (release), or the repository
/// virtualenv recorded at compile time (debug builds only).
pub fn locate(resource_dir: Option<PathBuf>) -> Option<PathBuf> {
    let name = format!("ridge-sidecar{}", std::env::consts::EXE_SUFFIX);
    #[cfg(debug_assertions)]
    {
        let _ = &resource_dir;
        Some(PathBuf::from(env!("RIDGE_DEV_SIDECAR_DIR")).join(name))
    }
    #[cfg(not(debug_assertions))]
    {
        resource_dir.map(|dir| dir.join("sidecar").join(name))
    }
}
