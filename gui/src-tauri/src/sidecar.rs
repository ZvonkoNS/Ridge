//! The Python sidecar as a child process: spawn, bounded line reads, timeouts, bounded restarts.
//!
//! Rules (desktop_gui_tauri_standards.md §2, §8): no sockets, stdio only; the binary comes from
//! the application bundle (debug builds: the repository virtualenv, fixed at compile time), never
//! from PATH, the working directory or user input; responses are size-limited; every request has
//! a timeout; a broken or timed-out sidecar is killed, restarted at most `MAX_STARTS - 1` times,
//! and a failed request is never retried automatically.

use std::io::{self, BufRead, BufReader, Read, Write};
use std::path::{Path, PathBuf};
use std::process::{Child, ChildStdin, ChildStdout, Command, Stdio};
use std::sync::mpsc::{self, Receiver, RecvTimeoutError};
use std::thread;
use std::time::{Duration, Instant};

use serde::Serialize;
use serde_json::Value;

use crate::error::IpcError;
use crate::rpc::{self, FrameError, Reply, MAX_RESPONSE_BYTES};

/// Protocol the GUI speaks (`PROTOCOL` in `ridge.sidecar.store_methods`).
pub const PROTOCOL: &str = "ridge.sidecar/1";
/// First start plus at most three restarts per application run.
pub const MAX_STARTS: u32 = 4;
const STARTUP_TIMEOUT: Duration = Duration::from_secs(60);
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

/// Starts the sidecar on first use and after a failure, within `MAX_STARTS`.
pub struct Sidecar<T: Transport> {
    launch: Box<dyn FnMut() -> io::Result<T> + Send>,
    transport: Option<T>,
    starts: u32,
    next_id: u64,
}

impl<T: Transport> Sidecar<T> {
    pub fn new(launch: Box<dyn FnMut() -> io::Result<T> + Send>) -> Self {
        Self {
            launch,
            transport: None,
            starts: 0,
            next_id: 1,
        }
    }

    /// Call one method. A transport or protocol failure stops the sidecar (the open case is then
    /// locked) and is reported; the request is not repeated.
    pub fn call<P: Serialize>(
        &mut self,
        method: &str,
        params: &P,
        timeout: Duration,
    ) -> Result<Value, IpcError> {
        self.ensure_started()?;
        let outcome = self.exchange(method, params, timeout);
        if matches!(&outcome, Err(e) if e.kind == crate::error::ErrorKind::Unavailable) {
            self.stop();
        }
        outcome
    }

    /// Close the sidecar's input so it locks the case and exits.
    pub fn stop(&mut self) {
        if let Some(mut transport) = self.transport.take() {
            transport.shutdown();
        }
    }

    fn ensure_started(&mut self) -> Result<(), IpcError> {
        if self.transport.is_some() {
            return Ok(());
        }
        if self.starts >= MAX_STARTS {
            return Err(IpcError::unavailable(
                "the processing engine stopped too often; restart Ridge and report the problem",
            ));
        }
        self.starts += 1;
        let transport = (self.launch)()
            .map_err(|_| IpcError::unavailable("the processing engine could not be started"))?;
        self.transport = Some(transport);
        let version = self.exchange("ridge.version", &serde_json::json!({}), STARTUP_TIMEOUT);
        match version {
            Ok(v) if v.get("protocol").and_then(Value::as_str) == Some(PROTOCOL) => Ok(()),
            _ => {
                self.stop();
                Err(IpcError::unavailable(
                    "the processing engine does not match this version of Ridge",
                ))
            }
        }
    }

    fn exchange<P: Serialize>(
        &mut self,
        method: &str,
        params: &P,
        timeout: Duration,
    ) -> Result<Value, IpcError> {
        let transport = self
            .transport
            .as_mut()
            .ok_or_else(|| IpcError::unavailable("no processing engine"))?;
        let id = self.next_id;
        self.next_id += 1;
        let line = rpc::encode_request(id, method, params).map_err(|e| match e {
            FrameError::RequestTooLarge => IpcError::invalid("the request is too large"),
            FrameError::Malformed(_) => IpcError::invalid("the request could not be encoded"),
        })?;
        transport.send(&line).map_err(|_| stopped())?;
        drop(line); // zeroised: it may hold a passphrase
        let reply = transport.receive(timeout).map_err(|e| match e {
            ReceiveError::Timeout => {
                IpcError::unavailable("the processing engine did not answer in time")
            }
            ReceiveError::Closed | ReceiveError::TooLarge => stopped(),
        })?;
        match rpc::decode_response(&reply, id) {
            Ok(Reply::Result(value)) => Ok(value),
            Ok(Reply::Error { message, .. }) => Err(IpcError::refused(&message)),
            Err(_) => Err(IpcError::unavailable(
                "the processing engine sent an invalid answer",
            )),
        }
    }
}

fn stopped() -> IpcError {
    IpcError::unavailable("the processing engine stopped; any open case was locked")
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

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::VecDeque;
    use std::sync::{Arc, Mutex};

    /// Scripted transport: answers each request with the next canned line (`None` = time out).
    struct Fake {
        replies: VecDeque<Option<String>>,
        sent: Arc<Mutex<Vec<Value>>>,
    }

    impl Transport for Fake {
        fn send(&mut self, line: &[u8]) -> io::Result<()> {
            self.sent
                .lock()
                .unwrap()
                .push(serde_json::from_slice(line).unwrap());
            Ok(())
        }

        fn receive(&mut self, _timeout: Duration) -> Result<Vec<u8>, ReceiveError> {
            let id = self
                .sent
                .lock()
                .unwrap()
                .last()
                .and_then(|m| m["id"].as_u64())
                .unwrap_or(0);
            match self.replies.pop_front() {
                Some(Some(template)) => Ok(template.replace("ID", &id.to_string()).into_bytes()),
                Some(None) => Err(ReceiveError::Timeout),
                None => Err(ReceiveError::Closed),
            }
        }

        fn shutdown(&mut self) {}
    }

    const VERSION: &str =
        r#"{"jsonrpc":"2.0","id":ID,"result":{"ridge":"0.2.0","protocol":"ridge.sidecar/1"}}"#;

    type Sent = Arc<Mutex<Vec<Value>>>;
    type Launches = Arc<Mutex<u32>>;

    fn sidecar(scripts: Vec<Vec<Option<&'static str>>>) -> (Sidecar<Fake>, Sent, Launches) {
        let sent = Arc::new(Mutex::new(Vec::new()));
        let launches = Arc::new(Mutex::new(0));
        let (sent2, launches2) = (sent.clone(), launches.clone());
        let mut scripts: VecDeque<_> = scripts.into();
        let launch = move || {
            *launches2.lock().unwrap() += 1;
            let replies = scripts
                .pop_front()
                .unwrap_or_default()
                .into_iter()
                .map(|r| r.map(str::to_owned))
                .collect();
            Ok(Fake {
                replies,
                sent: sent2.clone(),
            })
        };
        (Sidecar::new(Box::new(launch)), sent, launches)
    }

    fn ok(result: &'static str) -> Option<&'static str> {
        Some(result)
    }

    #[test]
    fn checks_the_protocol_then_forwards_calls() {
        let (mut sidecar, sent, _) = sidecar(vec![vec![
            ok(VERSION),
            ok(r#"{"jsonrpc":"2.0","id":ID,"result":{"locked":true}}"#),
        ]]);
        let value = sidecar
            .call(
                "session.lock",
                &serde_json::json!({}),
                Duration::from_secs(1),
            )
            .unwrap();
        assert_eq!(value, serde_json::json!({"locked": true}));
        let methods: Vec<_> = sent
            .lock()
            .unwrap()
            .iter()
            .map(|m| m["method"].as_str().unwrap().to_owned())
            .collect();
        assert_eq!(methods, ["ridge.version", "session.lock"]);
    }

    #[test]
    fn refusals_keep_the_sidecar_running() {
        let refusal =
            r#"{"jsonrpc":"2.0","id":ID,"error":{"code":-32000,"message":"no case is unlocked"}}"#;
        let (mut sidecar, _, launches) = sidecar(vec![vec![ok(VERSION), ok(refusal), ok(refusal)]]);
        for _ in 0..2 {
            let err = sidecar
                .call("case.items", &serde_json::json!({}), Duration::from_secs(1))
                .unwrap_err();
            assert_eq!(
                (err.kind, err.message.as_str()),
                (crate::error::ErrorKind::Refused, "no case is unlocked")
            );
        }
        assert_eq!(*launches.lock().unwrap(), 1);
    }

    #[test]
    fn a_version_mismatch_is_refused() {
        let old =
            r#"{"jsonrpc":"2.0","id":ID,"result":{"ridge":"0.1.0","protocol":"ridge.sidecar/0"}}"#;
        let (mut sidecar, _, _) = sidecar(vec![vec![ok(old)]]);
        let err = sidecar
            .call("case.items", &serde_json::json!({}), Duration::from_secs(1))
            .unwrap_err();
        assert_eq!(err.kind, crate::error::ErrorKind::Unavailable);
    }

    #[test]
    fn timeouts_and_bad_answers_restart_without_retrying() {
        let (mut sidecar, sent, launches) = sidecar(vec![
            vec![ok(VERSION), None], // times out
            vec![ok(VERSION), ok(r#"{"jsonrpc":"2.0","id":999,"result":1}"#)], // answers another id
            vec![ok(VERSION), ok(r#"{"jsonrpc":"2.0","id":ID,"result":2}"#)],
        ]);
        for _ in 0..2 {
            let err = sidecar
                .call("job.run", &serde_json::json!({}), Duration::from_millis(10))
                .unwrap_err();
            assert_eq!(err.kind, crate::error::ErrorKind::Unavailable);
        }
        assert_eq!(
            sidecar
                .call("case.items", &serde_json::json!({}), Duration::from_secs(1))
                .unwrap(),
            2
        );
        assert_eq!(*launches.lock().unwrap(), 3);
        let jobs = sent
            .lock()
            .unwrap()
            .iter()
            .filter(|m| m["method"] == "job.run")
            .count();
        assert_eq!(jobs, 2, "a failed request is never resent");
    }

    #[test]
    fn restarts_are_bounded() {
        let (mut sidecar, _, launches) = sidecar(vec![vec![], vec![], vec![], vec![], vec![]]);
        for _ in 0..6 {
            assert!(sidecar
                .call(
                    "case.items",
                    &serde_json::json!({}),
                    Duration::from_millis(1)
                )
                .is_err());
        }
        assert_eq!(*launches.lock().unwrap(), MAX_STARTS);
    }

    /// The real sidecar from the repository virtualenv, over real stdio. Skipped when it is not
    /// installed, unless RIDGE_REQUIRE_SIDECAR is set (the GUI gate sets it).
    #[test]
    fn the_real_sidecar_answers_over_stdio() {
        let program = locate(None).filter(|p| p.is_file());
        let Some(program) = program else {
            assert!(
                std::env::var_os("RIDGE_REQUIRE_SIDECAR").is_none(),
                "the dev sidecar is missing"
            );
            eprintln!("skipped: no ridge-sidecar in the virtualenv (pip install -e .)");
            return;
        };
        let mut sidecar = Sidecar::new(Box::new(move || spawn(&program)));
        let wait = Duration::from_secs(120);
        let store = std::env::temp_dir().join(format!("ridge-live-{}", std::process::id()));
        std::fs::create_dir_all(&store).unwrap();
        let store_text = store.to_str().unwrap().to_owned();
        let identity = sidecar
            .call(
                "store.identity",
                &serde_json::json!({"store": store_text}),
                wait,
            )
            .unwrap();
        assert_eq!(identity, serde_json::json!({"exists": false}));
        let cases = sidecar
            .call(
                "store.cases",
                &serde_json::json!({"store": store_text}),
                wait,
            )
            .unwrap();
        assert_eq!(cases, serde_json::json!([]));
        let refused = sidecar
            .call("case.items", &serde_json::json!({}), wait)
            .unwrap_err();
        assert_eq!(
            (refused.kind, refused.message.as_str()),
            (crate::error::ErrorKind::Refused, "no case is unlocked")
        );
        let unknown = sidecar
            .call("os.system", &serde_json::json!({}), wait)
            .unwrap_err();
        assert_eq!(unknown.kind, crate::error::ErrorKind::Refused);
        let status = sidecar
            .call("session.status", &serde_json::json!({}), wait)
            .unwrap();
        assert_eq!(status["unlocked"], false);
        sidecar.stop();
        std::fs::remove_dir_all(&store).unwrap();
    }
}
