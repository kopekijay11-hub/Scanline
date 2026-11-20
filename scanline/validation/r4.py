"""R4 parameter binding validation (SCAN-015)."""

import hashlib
from typing import Any, Dict, List

from scanline.validation.context import ValidationContext
from scanline.validation import utils
from scanline.sessions import validate_session_config


def validate_r4(ctx: ValidationContext) -> List[Dict[str, Any]]:
    violations: List[Dict[str, Any]] = []
    module = ctx.module
    events = ctx.events
    header = ctx.header
    param_data = ctx.param_data
    param_bytes = ctx.param_bytes

    computed_hash = hashlib.sha256(param_bytes).hexdigest()
    header_hash = header.get("param_sha256") if isinstance(header, dict) else None
    if header_hash is None:
        violations.append({"rule": "R4", "event_index": None, "detail": "header missing param_sha256"})
    elif computed_hash != header_hash:
        violations.append({
            "rule": "R4",
            "event_index": None,
            "detail": f"param_sha256 mismatch: computed={computed_hash}, header={header_hash}",
        })

    try:
        param_file_version = param_data.get("param_version") or param_data.get("version")
    except Exception:
        param_file_version = None

    header_version = header.get("param_version") if isinstance(header, dict) else None

    if param_file_version != header_version:
        violations.append({
            "rule": "R4",
            "event_index": None,
            "detail": f"version mismatch: param_file={param_file_version}, header={header_version}",
        })

    for idx, event in enumerate(events):
        event_version = event.get("param_version")
        if event_version != header_version:
            violations.append({
                "rule": "R4",
                "event_index": idx,
                "detail": f"event param_version '{event_version}' != header '{header_version}'",
            })

    scan_mode = header.get("scan_mode") if isinstance(header, dict) else None
    if scan_mode is not None and scan_mode not in ("forward", "retrospective"):
        violations.append({"rule": "R4", "event_index": None, "detail": f"invalid scan_mode '{scan_mode}'"})

    evidence_tier = header.get("evidence_tier") if isinstance(header, dict) else None
    _tier_for_mode = {"forward": "forward_asof", "retrospective": "retrospective_membership"}
    if scan_mode in _tier_for_mode and evidence_tier is not None:
        if evidence_tier != _tier_for_mode[scan_mode]:
            violations.append({
                "rule": "R4",
                "event_index": None,
                "detail": f"evidence_tier '{evidence_tier}' inconsistent with scan_mode '{scan_mode}'",
            })

    try:
        frozen_at_str = param_data.get("frozen_at")
    except Exception:
        frozen_at_str = None

    if scan_mode == "forward":
        if frozen_at_str is None:
            violations.append({"rule": "R4", "event_index": None, "detail": "param file frozen_at is null"})
        else:
            if not utils.validate_timestamp(frozen_at_str):
                violations.append({"rule": "R4", "event_index": None, "detail": f"param file frozen_at invalid: {frozen_at_str}"})
            else:
                frozen_dt = utils.parse_ts(frozen_at_str)
                if events:
                    first_event_dt = utils.get_first_event_ts(events)
                    if frozen_dt >= first_event_dt:
                        violations.append({
                            "rule": "R4",
                            "event_index": None,
                            "detail": f"frozen_at ({frozen_at_str}) not strictly before first event_ts ({first_event_dt.isoformat()})",
                        })

    if module == "session_anomalies":
        try:
            validate_session_config(param_data)
        except Exception as e:
            violations.append({"rule": "R4", "event_index": None, "detail": f"invalid session configuration: {e}"})

    violations.sort(key=lambda x: (x["event_index"] is None, x["event_index"] if x["event_index"] is not None else -1))
    return violations
