"""As-of validator for Scanline event batches.

Implements 5 rules:
- R1: as-of check (defined_at <= event_ts, non-strict)
- R2: D1-definition check (level_type in LEVEL_TYPES)
- R3: closed-bar ATR basis check (atr_basis == "closed_bars_only")
- R4: param binding check (hash, version, frozen_at)
- R5: no-forward-field check (closed schema)
"""

import hashlib
import json
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone
from typing import Any, Dict, List, Set, Tuple

from .schema import (
    ATR_BASIS,
    BATCH_HEADER_FIELDS,
    EMISSION_TIMEFRAMES,
    EVENT_FIELDS,
    LEVEL_TYPES,
)


def _parse_ts(ts_str: str) -> datetime:
    """Parse ISO-8601 UTC timestamp string to datetime."""
    # Handle various ISO-8601 formats
    if ts_str.endswith("Z"):
        ts_str = ts_str[:-1] + "+00:00"
    return datetime.fromisoformat(ts_str)


def _validate_timestamp(ts_str: str) -> bool:
    """Check if string is a valid ISO-8601 UTC timestamp."""
    try:
        _parse_ts(ts_str)
        return True
    except (ValueError, TypeError):
        return False


def _check_numeric(value: Any) -> bool:
    """Check if value is numeric (int or float)."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _get_first_event_ts(events: List[Dict[str, Any]]) -> datetime:
    """Get the earliest event_ts from events."""
    parsed_ts = [_parse_ts(e["event_ts"]) for e in events]
    return min(parsed_ts)


def validate_batch(
    events: List[Dict[str, Any]],
    header: Dict[str, Any],
    param_file_bytes: bytes,
) -> Dict[str, Any]:
    """Validate a batch of events against the header and param file.
    
    Args:
        events: List of event dictionaries
        header: Batch header dictionary
        param_file_bytes: Raw bytes of the parameter file
    
    Returns:
        {valid: bool, rule_results: dict, violations: list}
        where rule_results maps rule names to "pass"|"fail"
        and violations is a list of {rule, event_index, detail} dicts
        sorted by rule name then event_index
    """
    violations: List[Dict[str, Any]] = []
    rule_results: Dict[str, str] = {}
    
    # R1: as-of check.
    # D1-defined levels: defined_at <= event_ts (non-strict).
    # grid_round: grid-membership rule - level_price must be a member of the
    # symbol's grid enumeration derived from frozen steps (set membership).
    r1_violations = []
    # load grid_steps from param file once
    try:
        _param_data = json.loads(param_file_bytes)
    except (json.JSONDecodeError, TypeError):
        _param_data = {}
    _grid_steps = (_param_data.get("grid_steps") or {}) if isinstance(_param_data, dict) else {}

    def _grid_member(symbol, price):
        step = _grid_steps.get(symbol) if isinstance(_grid_steps, dict) else None
        if step is None:
            return False
        try:
            dprice = Decimal(str(price))
            dstep = Decimal(str(step))
        except (InvalidOperation, ValueError, TypeError):
            return False
        if dstep <= 0:
            return False
        try:
            return (dprice % dstep) == 0
        except Exception:
            return False

    for idx, event in enumerate(events):
        level_type = event.get("level_type")
        if level_type == "grid_round":
            symbol = event.get("symbol")
            level_price = event.get("level_price")
            if not _grid_member(symbol, level_price):
                r1_violations.append({
                    "rule": "R1",
                    "event_index": idx,
                    "detail": f"grid_round level_price {level_price} not a member of {symbol} grid"
                })
            continue
        # D1-defined levels
        defined_at = event.get("defined_at")
        event_ts = event.get("event_ts")
        if defined_at is None or event_ts is None:
            r1_violations.append({"rule": "R1", "event_index": idx, "detail": "missing timestamp"})
        elif not _validate_timestamp(defined_at) or not _validate_timestamp(event_ts):
            r1_violations.append({"rule": "R1", "event_index": idx, "detail": "invalid timestamp format"})
        else:
            defined_dt = _parse_ts(defined_at)
            event_dt = _parse_ts(event_ts)
            if defined_dt > event_dt:
                r1_violations.append({
                    "rule": "R1",
                    "event_index": idx,
                    "detail": f"defined_at ({defined_at}) > event_ts ({event_ts})"
                })
    
    # Sort R1 violations by event_index
    r1_violations.sort(key=lambda x: x["event_index"])
    violations.extend(r1_violations)
    rule_results["R1"] = "pass" if not r1_violations else "fail"
    
    # R2: D1-definition check - every level_type is in LEVEL_TYPES
    #     and every timeframe is in EMISSION_TIMEFRAMES
    r2_violations = []
    for idx, event in enumerate(events):
        level_type = event.get("level_type")
        if level_type not in LEVEL_TYPES:
            r2_violations.append({
                "rule": "R2",
                "event_index": idx,
                "detail": f"level_type '{level_type}' not in LEVEL_TYPES"
            })
        timeframe = event.get("timeframe")
        if timeframe not in EMISSION_TIMEFRAMES:
            r2_violations.append({
                "rule": "R2",
                "event_index": idx,
                "detail": f"timeframe '{timeframe}' not in EMISSION_TIMEFRAMES"
            })
    
    r2_violations.sort(key=lambda x: x["event_index"])
    violations.extend(r2_violations)
    rule_results["R2"] = "pass" if not r2_violations else "fail"
    
    # R3: closed-bar ATR basis - every event's atr_basis == "closed_bars_only"
    r3_violations = []
    for idx, event in enumerate(events):
        atr_basis = event.get("atr_basis")
        if atr_basis != ATR_BASIS:
            r3_violations.append({
                "rule": "R3",
                "event_index": idx,
                "detail": f"atr_basis '{atr_basis}' != '{ATR_BASIS}'"
            })
    
    r3_violations.sort(key=lambda x: x["event_index"])
    violations.extend(r3_violations)
    rule_results["R3"] = "pass" if not r3_violations else "fail"
    
    # R4: param binding check
    r4_violations = []
    
    # 4a: sha256(param_file_bytes) == header.param_sha256
    computed_hash = hashlib.sha256(param_file_bytes).hexdigest()
    header_hash = header.get("param_sha256")
    if header_hash is None:
        r4_violations.append({
            "rule": "R4",
            "event_index": None,
            "detail": "header missing param_sha256"
        })
    elif computed_hash != header_hash:
        r4_violations.append({
            "rule": "R4",
            "event_index": None,
            "detail": f"param_sha256 mismatch: computed={computed_hash}, header={header_hash}"
        })
    
    # 4b: param file version == header.param_version == every event's param_version
    try:
        param_file_data = json.loads(param_file_bytes)
        param_file_version = param_file_data.get("param_version") or param_file_data.get("version")
    except (json.JSONDecodeError, TypeError):
        param_file_version = None
    
    header_version = header.get("param_version")
    
    if param_file_version != header_version:
        r4_violations.append({
            "rule": "R4",
            "event_index": None,
            "detail": f"version mismatch: param_file={param_file_version}, header={header_version}"
        })
    
    # Check all events have matching version
    for idx, event in enumerate(events):
        event_version = event.get("param_version")
        if event_version != header_version:
            r4_violations.append({
                "rule": "R4",
                "event_index": idx,
                "detail": f"event param_version '{event_version}' != header '{header_version}'"
            })
    
    # scan_mode from header
    scan_mode = header.get("scan_mode")
    if scan_mode is not None and scan_mode not in ("forward", "retrospective"):
        r4_violations.append({
            "rule": "R4",
            "event_index": None,
            "detail": f"invalid scan_mode '{scan_mode}'"
        })

    # Tier-mode binding check (contract v3): scan_mode <-> evidence_tier.
    evidence_tier = header.get("evidence_tier")
    _tier_for_mode = {"forward": "forward_asof", "retrospective": "retrospective_membership"}
    if scan_mode in _tier_for_mode and evidence_tier is not None:
        if evidence_tier != _tier_for_mode[scan_mode]:
            r4_violations.append({
                "rule": "R4",
                "event_index": None,
                "detail": f"evidence_tier '{evidence_tier}' inconsistent with scan_mode '{scan_mode}'"
            })

    # 4c: frozen_at handling depends on mode.
    # forward: frozen_at strictly before batch's first event_ts.
    # retrospective: skip in-batch frozen_at check (proof lives outside).
    try:
        param_file_data = json.loads(param_file_bytes)
        frozen_at_str = param_file_data.get("frozen_at")
    except (json.JSONDecodeError, TypeError):
        frozen_at_str = None

    if scan_mode == "forward":
        if frozen_at_str is None:
            r4_violations.append({
                "rule": "R4",
                "event_index": None,
                "detail": "param file frozen_at is null"
            })
        else:
            if not _validate_timestamp(frozen_at_str):
                r4_violations.append({
                    "rule": "R4",
                    "event_index": None,
                    "detail": f"param file frozen_at invalid: {frozen_at_str}"
                })
            else:
                frozen_dt = _parse_ts(frozen_at_str)
                if events:
                    first_event_dt = _get_first_event_ts(events)
                    if frozen_dt >= first_event_dt:
                        r4_violations.append({
                            "rule": "R4",
                            "event_index": None,
                            "detail": f"frozen_at ({frozen_at_str}) not strictly before first event_ts ({first_event_dt.isoformat()})"
                        })
    
    # Sort R4 violations: None event_index first, then by event_index
    r4_violations.sort(key=lambda x: (x["event_index"] is None, x["event_index"] if x["event_index"] is not None else -1))
    violations.extend(r4_violations)
    rule_results["R4"] = "pass" if not r4_violations else "fail"
    
    # R5: no-forward-field check
    r5_violations = []
    
    # Check each event has exactly EVENT_FIELDS
    for idx, event in enumerate(events):
        event_fields = set(event.keys())
        extra_fields = event_fields - EVENT_FIELDS
        missing_fields = EVENT_FIELDS - event_fields
        
        if extra_fields:
            r5_violations.append({
                "rule": "R5",
                "event_index": idx,
                "detail": f"extra fields: {sorted(extra_fields)}"
            })
        if missing_fields:
            r5_violations.append({
                "rule": "R5",
                "event_index": idx,
                "detail": f"missing fields: {sorted(missing_fields)}"
            })
        
        # Numeric / structural checks (schema conformance)
        if "level_price" in event and not _check_numeric(event.get("level_price")):
            r5_violations.append({
                "rule": "R5",
                "event_index": idx,
                "detail": "level_price is not numeric"
            })
        if "distance_atr" in event and not _check_numeric(event.get("distance_atr")):
            r5_violations.append({
                "rule": "R5",
                "event_index": idx,
                "detail": "distance_atr is not numeric"
            })
        if "atr_window" in event:
            aw = event.get("atr_window")
            if not (isinstance(aw, int) and not isinstance(aw, bool) and aw > 0):
                r5_violations.append({
                    "rule": "R5",
                    "event_index": idx,
                    "detail": "atr_window is not a positive integer"
                })
    
    # Check header has exactly BATCH_HEADER_FIELDS
    header_fields = set(header.keys())
    extra_header_fields = header_fields - BATCH_HEADER_FIELDS
    missing_header_fields = BATCH_HEADER_FIELDS - header_fields
    
    if extra_header_fields:
        r5_violations.append({
            "rule": "R5",
            "event_index": None,
            "detail": f"header extra fields: {sorted(extra_header_fields)}"
        })
    if missing_header_fields:
        r5_violations.append({
            "rule": "R5",
            "event_index": None,
            "detail": f"header missing fields: {sorted(missing_header_fields)}"
        })

    # R5 enum check for evidence_tier (contract v3).
    if "evidence_tier" in header:
        et = header.get("evidence_tier")
        if et not in ("forward_asof", "retrospective_membership"):
            r5_violations.append({
                "rule": "R5",
                "event_index": None,
                "detail": f"header evidence_tier invalid enum: {et!r}"
            })
    
    # Sort R5 violations: None event_index first, then by event_index, then by detail
    r5_violations.sort(key=lambda x: (
        x["event_index"] is None,
        x["event_index"] if x["event_index"] is not None else -1,
        x["detail"]
    ))
    violations.extend(r5_violations)
    rule_results["R5"] = "pass" if not r5_violations else "fail"
    
    # Sort all violations by rule name, then by event_index
    violations.sort(key=lambda x: (
        x["rule"],
        x["event_index"] if x["event_index"] is not None else -1
    ))

    is_valid = all(r == "pass" for r in rule_results.values())
    
    return {
        "valid": is_valid,
        "rule_results": rule_results,
        "violations": violations,
    }
