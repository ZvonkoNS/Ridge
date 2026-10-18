"""Compare the recorded settings of two jobs (the CLI twin of the GUI comparison).

Only settings are compared: the input photo, the Ridge version and platform, and every recorded
parameter. Nothing about the outputs is ranked or scored; which enhancement helps is the
examiner's judgement.
"""

from __future__ import annotations

import json
from typing import Any

from ridge.case.reports import printable


def setting_text(value: object) -> str:
    """Write a recorded setting as the signed JSON has it: none, a scalar, or compact JSON."""
    if value is None:
        return "none"
    return value if isinstance(value, str) else json.dumps(value, separators=(",", ":"), sort_keys=True)


def differences(a: dict[str, Any], b: dict[str, Any]) -> tuple[list[tuple[str, str, str]], int]:
    """Return the settings that differ between two reports, and how many are the same."""
    env_a, env_b = a.get("ridge") or {}, b.get("ridge") or {}
    pairs: list[tuple[str, object, object]] = [
        ("input (SHA-256)", (a.get("input") or {}).get("sha256"), (b.get("input") or {}).get("sha256")),
        ("Ridge version", env_a.get("version"), env_b.get("version")),
        (
            "platform",
            f"{env_a.get('platform')} ({env_a.get('machine')})",
            f"{env_b.get('platform')} ({env_b.get('machine')})",
        ),
    ]
    params_a, params_b = a.get("parameters") or {}, b.get("parameters") or {}
    pairs += [(key, params_a.get(key), params_b.get(key)) for key in sorted({*params_a, *params_b})]
    rows = [(name, setting_text(x), setting_text(y)) for name, x, y in pairs if setting_text(x) != setting_text(y)]
    return rows, len(pairs) - len(rows)


def render_differences(job_a: str, job_b: str, rows: list[tuple[str, str, str]], same: int) -> list[str]:
    """Text lines for the CLI (control characters removed)."""
    if not rows:
        return [f"jobs {job_a[:8]} and {job_b[:8]} were run with the same input and settings"]
    width = max(len(name) for name, _, _ in rows)
    lines = [f"{'setting':{width}}  job {job_a[:8]}  ->  job {job_b[:8]}"]
    lines += [f"{name:{width}}  {x}  ->  {y}" for name, x, y in rows]
    lines.append(f"{same} setting(s) the same; comparing settings does not rank the outputs")
    return [printable(line) for line in lines]
