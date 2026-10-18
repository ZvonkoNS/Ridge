//! Validation of values that arrive from the untrusted WebView (desktop_gui_tauri_standards.md §3).
//!
//! The sidecar validates everything again; these checks make the Rust core refuse malformed or
//! forged values before they reach it (deny by default), with messages safe to show.

use crate::error::IpcError;

/// SHA-256 handles of stored items: exactly 64 lower-case hex digits.
pub fn sha256(value: &str) -> Result<String, IpcError> {
    if value.len() == 64
        && value
            .bytes()
            .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
    {
        Ok(value.to_owned())
    } else {
        Err(IpcError::invalid("not a stored item"))
    }
}

/// Case and job ids: a hyphenated UUID, returned in lower case.
pub fn uuid(value: &str, what: &str) -> Result<String, IpcError> {
    let bytes = value.as_bytes();
    let shaped = bytes.len() == 36
        && bytes.iter().enumerate().all(|(i, b)| match i {
            8 | 13 | 18 | 23 => *b == b'-',
            _ => b.is_ascii_hexdigit(),
        });
    if shaped {
        Ok(value.to_ascii_lowercase())
    } else {
        Err(IpcError::invalid(&format!(
            "{what} must be an id from the list"
        )))
    }
}

/// Free text: trimmed, 1..=`max` characters, no control characters.
pub fn text(value: &str, what: &str, max: usize) -> Result<String, IpcError> {
    let trimmed = value.trim();
    let count = trimmed.chars().count();
    if count == 0 || count > max || trimmed.chars().any(char::is_control) {
        return Err(IpcError::invalid(&format!(
            "{what} must be 1 to {max} printable characters"
        )));
    }
    Ok(trimmed.to_owned())
}

/// An examiner note: like `text`, but line breaks and tabs are kept. Bidirectional overrides and
/// isolates are refused so that a stored note cannot read differently from what it contains.
pub fn note(value: &str, max: usize) -> Result<String, IpcError> {
    let joined = value.replace("\r\n", "\n");
    let trimmed = joined.trim();
    let count = trimmed.chars().count();
    let refused = |c: char| (c.is_control() && c != '\n' && c != '\t') || disguises(c);
    if count == 0 || count > max || trimmed.chars().any(refused) {
        return Err(IpcError::invalid(&format!(
            "a note must be 1 to {max} printable characters (line breaks are allowed)"
        )));
    }
    Ok(trimmed.to_owned())
}

/// Bidirectional overrides and isolates: text with them can display differently from what it is.
fn disguises(c: char) -> bool {
    ('\u{202a}'..='\u{202e}').contains(&c) || ('\u{2066}'..='\u{2069}').contains(&c)
}

/// A person's name for a key card: plain text, no bidirectional overrides or isolates.
pub fn holder(value: &str) -> Result<String, IpcError> {
    let name = text(value, "the name", 200)?;
    if name.chars().any(disguises) {
        return Err(IpcError::invalid("the name must be plain text"));
    }
    Ok(name)
}

/// Optional free text: absent or blank means none.
pub fn optional_text(
    value: Option<&str>,
    what: &str,
    max: usize,
) -> Result<Option<String>, IpcError> {
    match value {
        Some(v) if !v.trim().is_empty() => text(v, what, max).map(Some),
        _ => Ok(None),
    }
}

/// A calendar date shaped YYYY-MM-DD (the sidecar checks that it exists).
pub fn date(value: &str, what: &str) -> Result<String, IpcError> {
    let b = value.as_bytes();
    let shaped = b.len() == 10
        && b.iter().enumerate().all(|(i, c)| {
            if i == 4 || i == 7 {
                *c == b'-'
            } else {
                c.is_ascii_digit()
            }
        });
    if shaped {
        Ok(value.to_owned())
    } else {
        Err(IpcError::invalid(&format!(
            "{what} must be a date, YYYY-MM-DD"
        )))
    }
}

/// A finite number within `lo..=hi`.
pub fn number(value: f64, lo: f64, hi: f64, what: &str) -> Result<f64, IpcError> {
    if value.is_finite() && (lo..=hi).contains(&value) {
        Ok(value)
    } else {
        Err(IpcError::invalid(&format!(
            "{what} must be between {lo} and {hi}"
        )))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn sha256_handles_must_be_full_lower_case_hex() {
        let good = "a".repeat(64);
        assert!(sha256(&good).is_ok());
        for bad in [
            "",
            "abc",
            &"A".repeat(64),
            &"g".repeat(64),
            &format!("{}/", "a".repeat(63)),
            &"a".repeat(65),
        ] {
            assert!(sha256(bad).is_err(), "{bad}");
        }
    }

    #[test]
    fn uuids_must_be_hyphenated() {
        assert_eq!(
            uuid("0F8FAD5B-D9CB-469F-A165-70867728950E", "case").unwrap(),
            "0f8fad5b-d9cb-469f-a165-70867728950e"
        );
        for bad in [
            "../escape",
            "0f8fad5bd9cb469fa16570867728950e",
            "0f8fad5b-d9cb-469f-a165-70867728950g",
            "",
        ] {
            assert!(uuid(bad, "case").is_err(), "{bad}");
        }
    }

    #[test]
    fn text_is_trimmed_bounded_and_printable() {
        assert_eq!(text("  Exhibit 12  ", "source", 200).unwrap(), "Exhibit 12");
        assert!(text("", "source", 200).is_err());
        assert!(text("a\u{7}b", "source", 200).is_err());
        assert!(text(&"x".repeat(201), "source", 200).is_err());
        assert_eq!(
            text(&"č".repeat(200), "source", 200)
                .unwrap()
                .chars()
                .count(),
            200
        );
        assert_eq!(optional_text(Some("  "), "source", 10).unwrap(), None);
        assert_eq!(optional_text(None, "source", 10).unwrap(), None);
    }

    #[test]
    fn notes_keep_line_breaks_and_refuse_disguises() {
        assert_eq!(note(" a\r\nb\tc ", 10).unwrap(), "a\nb\tc");
        for bad in [
            "",
            " \n ",
            "a\rb",
            "esc\u{1b}[2J",
            "abc\u{202e}cba",
            "x\u{2066}y",
        ] {
            assert!(note(bad, 10).is_err(), "{bad:?}");
        }
        assert!(note(&"x".repeat(11), 10).is_err());
    }

    #[test]
    fn holders_are_plain_names() {
        assert_eq!(holder("  Examiner A ").unwrap(), "Examiner A");
        assert!(holder("").is_err());
        assert!(holder("Examiner\u{202e}A").is_err());
        assert!(holder(&"x".repeat(201)).is_err());
    }

    #[test]
    fn dates_and_numbers() {
        assert!(date("2027-01-31", "retention").is_ok());
        for bad in ["2027-1-31", "next year", "2027/01/31", "２０２７-01-31"] {
            assert!(date(bad, "retention").is_err(), "{bad}");
        }
        assert!(number(0.25, 0.0, 1.0, "q").is_ok());
        for bad in [f64::NAN, f64::INFINITY, -0.1, 1.1] {
            assert!(number(bad, 0.0, 1.0, "q").is_err());
        }
    }
}
