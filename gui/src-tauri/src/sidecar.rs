//! Requests to the Python sidecar: protocol check, timeouts, bounded restarts and the idle lock.
//! The child process itself (spawn, bounded line reads, shutdown, where the binary is) lives in
//! `sidecar_process`.
//!
//! Rules (desktop_gui_tauri_standards.md §2, §8): no sockets, stdio only; responses are
//! size-limited; every request has a timeout; a broken or timed-out sidecar is killed and
//! restarted at most `MAX_STARTS - 1` times, and a failed request is never retried automatically.

use std::io;
use std::time::{Duration, Instant};

use serde::Serialize;
use serde_json::Value;

use crate::error::IpcError;
use crate::rpc::{self, FrameError, Reply};
pub use crate::sidecar_process::{launch, locate, ChildTransport, ReceiveError, Transport};

/// Protocol the GUI speaks (`PROTOCOL` in `ridge.sidecar.store_methods`).
pub const PROTOCOL: &str = "ridge.sidecar/1";
/// JSON-RPC error code the sidecar uses when it refuses one input file (`INPUT_REFUSED`).
const INPUT_REFUSED: i64 = -32001;
/// The sidecar's idle lock (`DEFAULT_IDLE_TIMEOUT_S` in `ridge.sidecar.session`), enforced by the core.
pub const IDLE_LOCK: Duration = Duration::from_secs(15 * 60);
/// First start plus at most three restarts per application run.
pub const MAX_STARTS: u32 = 4;
const STARTUP_TIMEOUT: Duration = Duration::from_secs(60);
/// A missing engine file (launch `NotFound`) is a broken installation, which restarting Ridge does
/// not fix. No path: IPC errors carry none (desktop_gui_tauri_standards.md §8).
const MISSING: &str = "the processing engine is missing from this installation; reinstall Ridge";
/// Starts the sidecar on first use and after a failure, within `MAX_STARTS`.
pub struct Sidecar<T: Transport> {
    launch: Box<dyn FnMut() -> io::Result<T> + Send>,
    transport: Option<T>,
    starts: u32,
    /// The last launch found no engine file; still the reason once the starts are used up.
    missing: bool,
    next_id: u64,
    last_request: Instant,
    idle_locked: bool,
}

impl<T: Transport> Sidecar<T> {
    pub fn new(launch: Box<dyn FnMut() -> io::Result<T> + Send>) -> Self {
        Self {
            launch,
            transport: None,
            starts: 0,
            missing: false,
            next_id: 1,
            last_request: Instant::now(),
            idle_locked: false,
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
        self.last_request = Instant::now();
        self.idle_locked = false;
        let outcome = self.exchange(method, params, timeout);
        self.last_request = Instant::now(); // a long job is activity until it ends
        if matches!(&outcome, Err(e) if e.kind == crate::error::ErrorKind::Unavailable) {
            self.stop();
        }
        outcome
    }

    /// Lock the case once no request has been made for `idle` (the watchdog in `lib.rs` calls this).
    ///
    /// The sidecar checks its own idle deadline only when a request arrives; this enforces it from
    /// the trusted core even if the WebView is minimised, suspended or compromised. Returns true when
    /// it sent the lock. The lock itself does not count as activity.
    pub fn lock_if_idle(&mut self, idle: Duration) -> bool {
        if self.transport.is_none() || self.idle_locked || self.last_request.elapsed() < idle {
            return false;
        }
        self.idle_locked = true;
        if self
            .exchange("session.lock", &serde_json::json!({}), STARTUP_TIMEOUT)
            .is_err()
        {
            self.stop(); // closing the sidecar's input locks the case as well
        }
        true
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
            return Err(IpcError::unavailable(if self.missing {
                MISSING
            } else {
                "the processing engine stopped too often; restart Ridge and report the problem"
            }));
        }
        self.starts += 1;
        let launched = (self.launch)();
        self.missing = matches!(&launched, Err(e) if e.kind() == io::ErrorKind::NotFound);
        let transport = launched.map_err(|_| {
            IpcError::unavailable(if self.missing {
                MISSING
            } else {
                "the processing engine could not be started"
            })
        })?;
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
            Ok(Reply::Error { code, message }) if code == INPUT_REFUSED => {
                Err(IpcError::input_refused(&message))
            }
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

#[cfg(test)]
mod tests {
    use super::*;
    use crate::sidecar_process::spawn;
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
    fn an_input_refusal_is_marked_for_batches() {
        let input = r#"{"jsonrpc":"2.0","id":ID,"error":{"code":-32001,"message":"not a supported image format"}}"#;
        let other = r#"{"jsonrpc":"2.0","id":ID,"error":{"code":-32000,"message":"custody log: write failed"}}"#;
        let (mut sidecar, _, _) = sidecar(vec![vec![ok(VERSION), ok(input), ok(other)]]);
        let params = serde_json::json!({});
        let first = sidecar
            .call("case.import", &params, Duration::from_secs(1))
            .unwrap_err();
        let second = sidecar
            .call("case.import", &params, Duration::from_secs(1))
            .unwrap_err();
        assert_eq!(
            (first.kind, first.input_refused),
            (crate::error::ErrorKind::Refused, true)
        );
        assert!(!second.input_refused);
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

    /// The errors of `MAX_STARTS + 1` calls when every launch fails with `kind`: the last call
    /// finds the starts used up and launches nothing.
    fn launch_failures(kind: io::ErrorKind) -> Vec<(crate::error::ErrorKind, String)> {
        let launches = Arc::new(Mutex::new(0));
        let counted = launches.clone();
        let mut sidecar = Sidecar::<Fake>::new(Box::new(move || {
            *counted.lock().unwrap() += 1;
            Err(io::Error::from(kind))
        }));
        let errors = (0..=MAX_STARTS)
            .map(|_| {
                let err = sidecar
                    .call(
                        "ridge.version",
                        &serde_json::json!({}),
                        Duration::from_secs(1),
                    )
                    .unwrap_err();
                (err.kind, err.message)
            })
            .collect();
        assert_eq!(*launches.lock().unwrap(), MAX_STARTS, "starts stay bounded");
        errors
    }

    #[test]
    fn a_missing_engine_asks_for_a_reinstall_every_time() {
        let unavailable = crate::error::ErrorKind::Unavailable;
        let missing = launch_failures(io::ErrorKind::NotFound);
        let reinstall = (
            unavailable,
            "the processing engine is missing from this installation; reinstall Ridge".to_owned(),
        );
        assert_eq!(missing, vec![reinstall; missing.len()]);
        let denied = launch_failures(io::ErrorKind::PermissionDenied);
        let (last, starts) = denied.split_last().unwrap();
        for failed in starts {
            assert_eq!(
                failed,
                &(
                    unavailable,
                    "the processing engine could not be started".to_owned()
                )
            );
        }
        assert_eq!(
            last.1,
            "the processing engine stopped too often; restart Ridge and report the problem"
        );
    }

    #[test]
    fn no_engine_file_is_not_found() {
        let absent = std::env::temp_dir().join(format!("ridge-absent-{}", std::process::id()));
        let not_a_file = std::env::temp_dir();
        for program in [None, Some(absent.as_path()), Some(not_a_file.as_path())] {
            assert_eq!(
                launch(program).err().map(|e| e.kind()),
                Some(io::ErrorKind::NotFound)
            );
        }
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

    #[test]
    fn the_core_locks_an_idle_case_once() {
        let locked = r#"{"jsonrpc":"2.0","id":ID,"result":{"locked":true}}"#;
        let items = r#"{"jsonrpc":"2.0","id":ID,"result":[]}"#;
        let (mut sidecar, sent, _) = sidecar(vec![vec![
            ok(VERSION),
            ok(items),
            ok(locked),
            ok(items),
            ok(locked),
        ]]);
        assert!(
            !sidecar.lock_if_idle(Duration::ZERO),
            "nothing to lock before the sidecar runs"
        );
        sidecar
            .call("case.items", &serde_json::json!({}), Duration::from_secs(1))
            .unwrap();
        assert!(
            !sidecar.lock_if_idle(Duration::from_secs(3600)),
            "not idle yet"
        );
        assert!(sidecar.lock_if_idle(Duration::ZERO));
        assert!(
            !sidecar.lock_if_idle(Duration::ZERO),
            "locked once until the next request"
        );
        sidecar
            .call("case.items", &serde_json::json!({}), Duration::from_secs(1))
            .unwrap();
        assert!(sidecar.lock_if_idle(Duration::ZERO));
        let methods: Vec<_> = sent
            .lock()
            .unwrap()
            .iter()
            .map(|m| m["method"].as_str().unwrap().to_owned())
            .collect();
        assert_eq!(
            methods,
            [
                "ridge.version",
                "case.items",
                "session.lock",
                "case.items",
                "session.lock"
            ]
        );
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
