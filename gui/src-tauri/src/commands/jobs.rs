//! Job and record commands: run, list, reports, reproduction, processing record, comparison sheet.

use std::time::Duration;

use serde::Deserialize;
use serde_json::{json, Map, Value};
use tauri::{AppHandle, WebviewWindow};

use crate::error::IpcError;
use crate::state::{call, path_text};
use crate::windows::{require, MAIN_LABEL};
use crate::{dialogs, validate};

const QUICK: Duration = Duration::from_secs(30);
const RECORD_IO: Duration = Duration::from_secs(120);
const JOB: Duration = Duration::from_secs(20 * 60);
const JSON_FILE: (&str, &[&str]) = ("JSON", &["json"]);
const PNG: (&str, &[&str]) = ("PNG image", &["png"]);

/// Opt-in method variants (ADR-014); the sidecar validates them again.
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
pub struct MethodOptionsRequest {
    channel: String,
    specular_mask: bool,
    upright: bool,
    local_frequency: bool,
}

const CHANNELS: [&str; 5] = ["green", "red", "blue", "luma", "auto"];

/// Extraction options as the review panel sends them (all fields required: no hidden defaults).
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
pub struct JobRequest {
    evidence: String,
    period: Option<f64>,
    min_quality: f64,
    flip: bool,
    crop: bool,
    debug: bool,
    export: bool,
    mirror: bool,
    ppi: f64,
    ruler: Option<[f64; 5]>,
    reference: String,
    minutiae: bool,
    roi: Option<[u32; 4]>,
    finger_position: u8,
    source_agency: Option<String>,
    options: MethodOptionsRequest,
}

impl JobRequest {
    /// Validate and build the sidecar's `job.run` parameters.
    pub fn params(&self) -> Result<Map<String, Value>, IpcError> {
        let mut params = Map::new();
        params.insert("evidence".into(), json!(validate::sha256(&self.evidence)?));
        if let Some(period) = self.period {
            params.insert(
                "period".into(),
                json!(validate::number(period, 2.0, 200.0, "ridge period")?),
            );
        }
        params.insert(
            "min_quality".into(),
            json!(validate::number(
                self.min_quality,
                0.0,
                1.0,
                "minimum quality"
            )?),
        );
        params.insert(
            "ppi".into(),
            json!(validate::number(
                self.ppi,
                250.0,
                2000.0,
                "export resolution"
            )?),
        );
        for (name, value) in [
            ("flip", self.flip),
            ("crop", self.crop),
            ("debug", self.debug),
            ("export", self.export),
            ("mirror", self.mirror),
            ("minutiae", self.minutiae),
        ] {
            params.insert(name.into(), json!(value));
        }
        if let Some(ruler) = self.ruler {
            params.insert("ruler".into(), checked_ruler(ruler)?);
        }
        params.insert(
            "reference".into(),
            json!(checked_reference(&self.reference)?),
        );
        if self.finger_position > 10 {
            return Err(IpcError::invalid(
                "the finger position must be a code from 0 (unknown) to 10",
            ));
        }
        params.insert("finger_position".into(), json!(self.finger_position));
        if !CHANNELS.contains(&self.options.channel.as_str()) {
            return Err(IpcError::invalid("not a known colour plane"));
        }
        params.insert(
            "options".into(),
            json!({
                "channel": self.options.channel,
                "specular_mask": self.options.specular_mask,
                "upright": self.options.upright,
                "local_frequency": self.options.local_frequency
            }),
        );
        params.insert(
            "source_agency".into(),
            json!(validate::optional_text(
                self.source_agency.as_deref(),
                "source agency",
                200
            )?),
        );
        if let Some(roi) = self.roi {
            params.insert("roi".into(), checked_roi(roi)?);
        }
        Ok(params)
    }
}

/// Two points in photo pixels and the distance between them in millimetres.
fn checked_ruler([x1, y1, x2, y2, mm]: [f64; 5]) -> Result<Value, IpcError> {
    for c in [x1, y1, x2, y2] {
        validate::number(c, 0.0, 1_000_000.0, "ruler point")?;
    }
    validate::number(mm, 0.1, 1000.0, "ruler distance")?;
    if (x1 - x2).hypot(y1 - y2) < 2.0 {
        return Err(IpcError::invalid("the two ruler points must be apart"));
    }
    Ok(json!([x1, y1, x2, y2, mm]))
}

/// What the two scale points lie on (FR-31 a): a ruler, or an edge of an ISO/IEC 7810 ID-1 card.
fn checked_reference(kind: &str) -> Result<&str, IpcError> {
    match kind {
        "ruler" | "id1-long" | "id1-short" => Ok(kind),
        _ => Err(IpcError::invalid("not a known scale reference")),
    }
}

/// x, y, width and height in photo pixels; the sidecar checks that it lies on the photo.
fn checked_roi([x, y, w, h]: [u32; 4]) -> Result<Value, IpcError> {
    if w < 32 || h < 32 {
        return Err(IpcError::invalid(
            "the region must be at least 32 x 32 pixels",
        ));
    }
    Ok(json!([x, y, w, h]))
}

/// Run one extraction job (FR-23, FR-30 to FR-35, FR-40).
#[tauri::command]
pub async fn run_job(
    app: AppHandle,
    window: WebviewWindow,
    request: JobRequest,
) -> Result<Value, IpcError> {
    require(&window, MAIN_LABEL)?;
    let params = request.params()?;
    call(&app, "job.run", Value::Object(params), JOB).await
}

/// Jobs recorded in the custody log.
#[tauri::command]
pub async fn list_jobs(app: AppHandle, window: WebviewWindow) -> Result<Value, IpcError> {
    require(&window, MAIN_LABEL)?;
    call(&app, "case.jobs", json!({}), QUICK).await
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
pub struct JobRef {
    job_id: String,
}

/// A job's report, shown only after its hash and signature verify (FR-28).
#[tauri::command]
pub async fn get_report(
    app: AppHandle,
    window: WebviewWindow,
    request: JobRef,
) -> Result<Value, IpcError> {
    require(&window, MAIN_LABEL)?;
    let job_id = validate::uuid(&request.job_id, "job")?;
    call(&app, "report.get", json!({"job_id": job_id}), QUICK).await
}

/// Export a verified report and its detached signature (FR-28).
#[tauri::command]
pub async fn export_report(
    app: AppHandle,
    window: WebviewWindow,
    request: JobRef,
) -> Result<Value, IpcError> {
    require(&window, MAIN_LABEL)?;
    let job_id = validate::uuid(&request.job_id, "job")?;
    let suggested = Some(format!("ridge_job_{}_report.json", &job_id[..8]));
    let dest = path_text(
        &dialogs::save_file(&app, "Export the signed report", suggested, JSON_FILE).await?,
    )?;
    call(
        &app,
        "report.export",
        json!({"job_id": job_id, "dest": dest, "overwrite": false}),
        RECORD_IO,
    )
    .await
}

/// Re-run a signed job from its report and compare every output (FR-34, NFR-3).
#[tauri::command]
pub async fn reproduce_job(
    app: AppHandle,
    window: WebviewWindow,
    request: JobRef,
) -> Result<Value, IpcError> {
    require(&window, MAIN_LABEL)?;
    let job_id = validate::uuid(&request.job_id, "job")?;
    call(&app, "job.reproduce", json!({"job_id": job_id}), JOB).await
}

/// Export the signed processing record for the DPO (PRIV-3).
#[tauri::command]
pub async fn export_log(app: AppHandle, window: WebviewWindow) -> Result<Value, IpcError> {
    require(&window, MAIN_LABEL)?;
    let suggested = Some("ridge_processing_record.json".to_owned());
    let dest = path_text(
        &dialogs::save_file(&app, "Export the processing record", suggested, JSON_FILE).await?,
    )?;
    call(
        &app,
        "log.export",
        json!({"dest": dest, "overwrite": false}),
        RECORD_IO,
    )
    .await
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Comparison {
    export: String,
    reference: String,
    reference_ppi: Option<f64>,
}

/// Write an equal-scale side-by-side sheet of an export and a reference (FR-52; nothing is matched).
#[tauri::command]
pub async fn export_comparison(
    app: AppHandle,
    window: WebviewWindow,
    request: Comparison,
) -> Result<Value, IpcError> {
    require(&window, MAIN_LABEL)?;
    let export = validate::sha256(&request.export)?;
    let reference = validate::sha256(&request.reference)?;
    let reference_ppi = match request.reference_ppi {
        Some(ppi) => Some(validate::number(
            ppi,
            250.0,
            2000.0,
            "reference resolution",
        )?),
        None => None,
    };
    let suggested = Some(format!(
        "ridge_comparison_{}_{}.png",
        &export[..8],
        &reference[..8]
    ));
    let dest =
        path_text(&dialogs::save_file(&app, "Export the comparison sheet", suggested, PNG).await?)?;
    let params = json!({
        "export": export, "reference": reference, "dest": dest, "reference_ppi": reference_ppi, "overwrite": false
    });
    call(&app, "compare.export", params, RECORD_IO).await
}

/// Export the signed custody head for out-of-band countersigning (OQ-8; logged).
#[tauri::command]
pub async fn export_head(app: AppHandle, window: WebviewWindow) -> Result<Value, IpcError> {
    require(&window, MAIN_LABEL)?;
    let suggested = Some("ridge_custody_head.json".to_owned());
    let dest = path_text(
        &dialogs::save_file(&app, "Export the custody head", suggested, JSON_FILE).await?,
    )?;
    call(
        &app,
        "head.export",
        json!({"dest": dest, "overwrite": false}),
        RECORD_IO,
    )
    .await
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
pub struct MinutiaeRef {
    sha256: String,
}

/// A job's minutiae for the viewer overlay (unvalidated, orientation only; a logged read).
#[tauri::command]
pub async fn get_minutiae(
    app: AppHandle,
    window: WebviewWindow,
    request: MinutiaeRef,
) -> Result<Value, IpcError> {
    require(&window, MAIN_LABEL)?;
    let sha256 = validate::sha256(&request.sha256)?;
    call(&app, "minutiae.get", json!({"sha256": sha256}), QUICK).await
}

#[cfg(test)]
mod tests {
    use super::*;

    fn request(extra: Value) -> Result<JobRequest, serde_json::Error> {
        let mut base = json!({
            "evidence": "a".repeat(64), "period": null, "min_quality": 0.25, "flip": false, "crop": true,
            "debug": false, "export": true, "mirror": true, "ppi": 500.0, "ruler": null, "reference": "ruler",
            "minutiae": false, "roi": null, "finger_position": 0, "source_agency": null,
            "options": {"channel": "green", "specular_mask": false, "upright": false, "local_frequency": false}
        });
        if let (Some(base), Some(extra)) = (base.as_object_mut(), extra.as_object()) {
            base.extend(extra.clone());
        }
        serde_json::from_value(base)
    }

    #[test]
    fn a_valid_request_maps_to_job_run() {
        let params =
            request(json!({"roi": [10, 20, 300, 400], "ruler": [0.0, 0.0, 200.0, 0.0, 10.0]}))
                .unwrap()
                .params()
                .unwrap();
        assert_eq!(params["roi"], json!([10, 20, 300, 400]));
        assert_eq!(params["ruler"], json!([0.0, 0.0, 200.0, 0.0, 10.0]));
        assert_eq!(params["reference"], json!("ruler"));
        assert!(!params.contains_key("period"));
        let card = request(json!({"reference": "id1-long", "ruler": [0.0, 0.0, 856.0, 0.0, 85.6]}))
            .unwrap()
            .params()
            .unwrap();
        assert_eq!(card["reference"], json!("id1-long"));
        let stated = request(json!({"finger_position": 7, "source_agency": "  Lab A "}))
            .unwrap()
            .params()
            .unwrap();
        assert_eq!(stated["finger_position"], json!(7));
        assert_eq!(stated["source_agency"], json!("Lab A"));
        assert_eq!(params["source_agency"], json!(null));
        assert_eq!(
            params["options"],
            json!({"channel": "green", "specular_mask": false, "upright": false, "local_frequency": false})
        );
    }

    #[test]
    fn unknown_or_mistyped_fields_are_refused() {
        assert!(request(json!({"path": "C:/x"})).is_err());
        assert!(request(json!({"flip": "yes"})).is_err());
        assert!(request(json!({"roi": [-1, 0, 64, 64]})).is_err());
        assert!(request(json!({"ruler": [0, 0, 1]})).is_err());
    }

    #[test]
    fn out_of_range_values_are_refused() {
        for extra in [
            json!({"evidence": "../../x"}),
            json!({"min_quality": 1.5}),
            json!({"ppi": 72.0}),
            json!({"period": 0.5}),
            json!({"roi": [0, 0, 8, 8]}),
            json!({"ruler": [5.0, 5.0, 5.5, 5.0, 10.0]}),
            json!({"ruler": [0.0, 0.0, 100.0, 0.0, 0.0]}),
            json!({"reference": "coin"}),
            json!({"finger_position": 11}),
            json!({"source_agency": "x".repeat(201)}),
            json!({"options": {"channel": "cyan", "specular_mask": false, "upright": false, "local_frequency": false}}),
        ] {
            assert!(request(extra.clone()).unwrap().params().is_err(), "{extra}");
        }
    }
}
