//! JSON-RPC 2.0 framing for the Python sidecar (architecture §7.3): one UTF-8 JSON object per line.
//!
//! Pure functions only: building a request and checking a response. Every response is untrusted
//! input for the Rust core: it must be one JSON object, answer the request id that was sent, and
//! carry either a result or an error with an integer code and a string message.

use serde::Serialize;
use serde_json::Value;
use zeroize::Zeroizing;

/// The sidecar refuses requests larger than this (`MAX_MESSAGE_BYTES` in `ridge.sidecar.protocol`).
pub const MAX_REQUEST_BYTES: usize = 1024 * 1024;
/// Largest response line accepted from the sidecar: a 2048 px PNG preview in base64 plus framing.
pub const MAX_RESPONSE_BYTES: usize = 32 * 1024 * 1024;

#[derive(Serialize)]
struct Request<'a, P: Serialize> {
    jsonrpc: &'static str,
    id: u64,
    method: &'a str,
    params: &'a P,
}

/// Why a response could not be used.
#[derive(Debug, PartialEq, Eq)]
pub enum FrameError {
    /// The request would exceed the sidecar's limit.
    RequestTooLarge,
    /// The response is not one JSON-RPC 2.0 response object for this request.
    Malformed(&'static str),
}

/// A sidecar answer: the result, or the sidecar's error code and safe message.
#[derive(Debug, PartialEq)]
pub enum Reply {
    Result(Value),
    Error { code: i64, message: String },
}

/// Serialise one request line. The buffer is zeroised on drop because it may hold a passphrase.
pub fn encode_request<P: Serialize>(
    id: u64,
    method: &str,
    params: &P,
) -> Result<Zeroizing<Vec<u8>>, FrameError> {
    let request = Request {
        jsonrpc: "2.0",
        id,
        method,
        params,
    };
    let mut line = Zeroizing::new(
        serde_json::to_vec(&request)
            .map_err(|_| FrameError::Malformed("request is not serialisable"))?,
    );
    line.push(b'\n');
    if line.len() > MAX_REQUEST_BYTES {
        return Err(FrameError::RequestTooLarge);
    }
    Ok(line)
}

/// Check one response line against the request id that was sent.
pub fn decode_response(line: &[u8], expected_id: u64) -> Result<Reply, FrameError> {
    if line.len() > MAX_RESPONSE_BYTES {
        return Err(FrameError::Malformed("response too large"));
    }
    let message: Value =
        serde_json::from_slice(line).map_err(|_| FrameError::Malformed("response is not JSON"))?;
    let object = message
        .as_object()
        .ok_or(FrameError::Malformed("response is not an object"))?;
    if object.get("jsonrpc").and_then(Value::as_str) != Some("2.0") {
        return Err(FrameError::Malformed("response is not JSON-RPC 2.0"));
    }
    if object.get("id").and_then(Value::as_u64) != Some(expected_id) {
        return Err(FrameError::Malformed("response answers another request"));
    }
    match (object.get("result"), object.get("error")) {
        (Some(result), None) => Ok(Reply::Result(result.clone())),
        (None, Some(error)) => {
            let code = error.get("code").and_then(Value::as_i64);
            let text = error.get("message").and_then(Value::as_str);
            match (code, text) {
                (Some(code), Some(text)) => Ok(Reply::Error {
                    code,
                    message: text.chars().take(500).collect(),
                }),
                _ => Err(FrameError::Malformed("error without code and message")),
            }
        }
        _ => Err(FrameError::Malformed(
            "response needs exactly one of result and error",
        )),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn requests_are_one_line_of_json_rpc() {
        let line = encode_request(7, "case.items", &json!({})).unwrap();
        assert_eq!(line.last(), Some(&b'\n'));
        let parsed: Value = serde_json::from_slice(&line).unwrap();
        assert_eq!(
            parsed,
            json!({"jsonrpc": "2.0", "id": 7, "method": "case.items", "params": {}})
        );
    }

    #[test]
    fn oversized_requests_are_refused_before_sending() {
        let big = "x".repeat(MAX_REQUEST_BYTES);
        assert_eq!(
            encode_request(1, "case.import", &json!({"path": big})).err(),
            Some(FrameError::RequestTooLarge)
        );
    }

    #[test]
    fn results_and_errors_are_decoded() {
        let ok = br#"{"jsonrpc":"2.0","id":3,"result":{"locked":true}}"#;
        assert_eq!(
            decode_response(ok, 3),
            Ok(Reply::Result(json!({"locked": true})))
        );
        let refused =
            br#"{"jsonrpc":"2.0","id":3,"error":{"code":-32000,"message":"no case is unlocked"}}"#;
        assert_eq!(
            decode_response(refused, 3),
            Ok(Reply::Error {
                code: -32000,
                message: "no case is unlocked".into()
            })
        );
    }

    #[test]
    fn malformed_responses_are_refused() {
        for (line, id) in [
            (&b"not json"[..], 1),
            (br#"[1]"#, 1),
            (br#"{"jsonrpc":"1.0","id":1,"result":1}"#, 1),
            (br#"{"jsonrpc":"2.0","id":2,"result":1}"#, 1),
            (br#"{"jsonrpc":"2.0","id":1}"#, 1),
            (br#"{"jsonrpc":"2.0","id":1,"result":1,"error":{}}"#, 1),
            (br#"{"jsonrpc":"2.0","id":1,"error":{"code":"x"}}"#, 1),
        ] {
            assert!(
                decode_response(line, id).is_err(),
                "{}",
                String::from_utf8_lossy(line)
            );
        }
    }

    #[test]
    fn long_error_messages_are_truncated() {
        let line = format!(
            r#"{{"jsonrpc":"2.0","id":1,"error":{{"code":-32000,"message":"{}"}}}}"#,
            "a".repeat(2000)
        );
        match decode_response(line.as_bytes(), 1) {
            Ok(Reply::Error { message, .. }) => assert_eq!(message.len(), 500),
            other => panic!("unexpected {other:?}"),
        }
    }
}
