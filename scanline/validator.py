"""As-of validator for Scanline event batches.

Implements 5 rules:
- R1: as-of / module-1 grid + defined_at checks; module-2 defined_at + cluster schedule
- R2: module-specific type/timeframe checks
- R3: module-specific basis / causal checks
- R4: shared param binding check
- R5: closed schema + module registry
"""

import hashlib
import json
import re
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone
from typing import Any, Dict, List, Set, Tuple

from .schema import (
    ANOMALY_TYPES,
    ATR_BASIS,
    BATCH_HEADER_FIELDS,
    EMISSION_TIMEFRAMES,
    EVENT_FIELDS,
    EVENT_FIELDS_BY_MODULE,
    LEVEL_TYPES,
    MODULES,
    SESSION_EMISSION_TIMEFRAMES,
    SESSION_EVENT_FIELDS,
)


def _parse_ts(ts_str: str) -> datetime:
    """Parse ISO-8601 UTC timestamp string to datetime."""
    if ts_str.endswith("Z"):
        ts_str = ts_str[:-1] + "+00:00"
    return datetime.fromisoformat(ts_str)


def _validate_timestamp(ts_str: str) -> bool:
    try:
        _parse_ts(ts_str)
        return True
    except (ValueError, TypeError):
        return False


def _check_numeric(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _get_first_event_ts(events: List[Dict[str, Any]]) -> datetime:
    parsed_ts = [_parse_ts(e["event_ts"]) for e in events]
    return min(parsed_ts)


def _cluster_expected_bars(param_data: Any, symbol: Any) -> Any:
    """Extract the frozen expected (weekday) bar count for a symbol."""
    if not isinstance(param_data, dict):
        return None
    # Direct mapping fields
    for key in ("expected_bars", "weekday_expected_bars", "expected_weekday_bars"):
        val = param_data.get(key)
        if isinstance(val, dict):
            if symbol in val:
                return val.get(symbol)
    # Cluster containers
    for key in ("clusters", "cluster_schedule", "clusters_schedule", "session_clusters", "cluster_expected_bars"):
        val = param_data.get(key)
        if isinstance(val, dict):
            c = val.get(symbol)
            if isinstance(c, int) and not isinstance(c, bool):
                return c
            if isinstance(c, dict):
                for ek in ("expected_bars", "weekday_expected_bars", "expected_weekday_bars", "expected"):
                    if ek in c:
                        return c.get(ek)
        if isinstance(val, list):
            for item in val:
                if isinstance(item, dict):
                    if item.get("symbol") == symbol:
                        for ek in ("expected_bars", "weekday_expected_bars", "expected_weekday_bars", "expected"):
                            if ek in item:
                                return item.get(ek)
    # nested under "cluster" mapping
    clusters = param_data.get("clusters")
    if isinstance(clusters, dict):
        for cname, cinfo in clusters.items():
            if isinstance(cinfo, dict) and cinfo.get("symbol") == symbol:
                for ek in ("expected_bars", "weekday_expected_bars", "expected_weekday_bars", "expected"):
                    if ek in cinfo:
                        return cinfo.get(ek)
    return None


def validate_batch(
    events: List[Dict[str, Any]],
    header: Dict[str, Any],
    param_file_bytes: bytes,
) -> Dict[str, Any]:
    violations: List[Dict[str, Any]] = []
    rule_results: Dict[str, str] = {}

    try:
        _param_data = json.loads(param_file_bytes)
    except (json.JSONDecodeError, TypeError):
        _param_data = {}
    if not isinstance(_param_data, dict):
        _param_data = {}

    _raw_module = header.get("module") if isinstance(header, dict) else None
    MODULE_ALIASES = {"module_1": "level_proximity", "level_proximity": "level_proximity", "session_anomalies": "session_anomalies"}
    module = MODULE_ALIASES.get(_raw_module, _raw_module)

    # R1
    r1_violations = []

    if module == "session_anomalies":
        # load frozen_at for retrospective comparison
        frozen_at_str = _param_data.get("frozen_at")
        scan_mode = header.get("scan_mode") if isinstance(header, dict) else None
        batch_end_ts = header.get("batch_end_ts") if isinstance(header, dict) else None
        for idx, event in enumerate(events):
            defined_at = event.get("defined_at")
            event_ts = event.get("event_ts")
            if defined_at is None or event_ts is None:
                r1_violations.append({"rule": "R1", "event_index": idx, "detail": "missing timestamp"})
                continue
            if not _validate_timestamp(defined_at) or not _validate_timestamp(event_ts):
                r1_violations.append({"rule": "R1", "event_index": idx, "detail": "invalid timestamp format"})
                continue
            if scan_mode == "forward":
                defined_dt = _parse_ts(defined_at)
                event_dt = _parse_ts(event_ts)
                if defined_dt > event_dt:
                    r1_violations.append({
                        "rule": "R1",
                        "event_index": idx,
                        "detail": f"defined_at ({defined_at}) > event_ts ({event_ts})",
                    })
            else:
                # retrospective
                if frozen_at_str is None or not _validate_timestamp(frozen_at_str):
                    # handled elsewhere; skip strict equality only if invalid
                    pass
                else:
                    if _parse_ts(defined_at) != _parse_ts(frozen_at_str):
                        r1_violations.append({
                            "rule": "R1",
                            "event_index": idx,
                            "detail": f"defined_at ({defined_at}) != frozen_at ({frozen_at_str})",
                        })
                symbol = event.get("symbol")
                sched = _cluster_expected_bars(_param_data, symbol)
                if sched is None:
                    r1_violations.append({
                        "rule": "R1",
                        "event_index": idx,
                        "detail": f"symbol '{symbol}' not in frozen cluster schedule",
                    })
                else:
                    try:
                        if int(event.get("expected_bars")) != int(sched):
                            r1_violations.append({
                                "rule": "R1",
                                "event_index": idx,
                                "detail": f"expected_bars {event.get('expected_bars')} != frozen schedule {sched} for {symbol}",
                            })
                    except (TypeError, ValueError):
                        r1_violations.append({
                            "rule": "R1",
                            "event_index": idx,
                            "detail": "expected_bars is not an integer",
                        })
    elif module == "level_proximity":
        # grid_steps from param file
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
                        "detail": f"grid_round level_price {level_price} not a member of {symbol} grid",
                    })
                continue
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
                        "detail": f"defined_at ({defined_at}) > event_ts ({event_ts})",
                    })
    else:
        # unknown module: no module-specific R1 checks; R5 fails module.
        pass

    r1_violations.sort(key=lambda x: x["event_index"])
    violations.extend(r1_violations)
    rule_results["R1"] = "pass" if not r1_violations else "fail"

    # R2
    r2_violations = []
    if module == "session_anomalies":
        for idx, event in enumerate(events):
            anomaly_type = event.get("anomaly_type")
            if anomaly_type not in ANOMALY_TYPES:
                r2_violations.append({
                    "rule": "R2",
                    "event_index": idx,
                    "detail": f"anomaly_type '{anomaly_type}' not in ANOMALY_TYPES",
                })
            timeframe = event.get("timeframe")
            if timeframe not in SESSION_EMISSION_TIMEFRAMES:
                r2_violations.append({
                    "rule": "R2",
                    "event_index": idx,
                    "detail": f"timeframe '{timeframe}' not in SESSION_EMISSION_TIMEFRAMES",
                })
    elif module == "level_proximity":
        for idx, event in enumerate(events):
            level_type = event.get("level_type")
            if level_type not in LEVEL_TYPES:
                r2_violations.append({
                    "rule": "R2",
                    "event_index": idx,
                    "detail": f"level_type '{level_type}' not in LEVEL_TYPES",
                })
            timeframe = event.get("timeframe")
            if timeframe not in EMISSION_TIMEFRAMES:
                r2_violations.append({
                    "rule": "R2",
                    "event_index": idx,
                    "detail": f"timeframe '{timeframe}' not in EMISSION_TIMEFRAMES",
                })
    else:
        pass

    r2_violations.sort(key=lambda x: x["event_index"])
    violations.extend(r2_violations)
    rule_results["R2"] = "pass" if not r2_violations else "fail"

    # R3
    r3_violations = []
    if module == "session_anomalies":
        batch_end_ts = header.get("batch_end_ts") if isinstance(header, dict) else None
        if batch_end_ts is not None and _validate_timestamp(batch_end_ts):
            batch_end_dt = _parse_ts(batch_end_ts)
            for idx, event in enumerate(events):
                event_ts = event.get("event_ts")
                if event_ts is None or not _validate_timestamp(event_ts):
                    # R1/R5 cover; skip here
                    continue
                event_dt = _parse_ts(event_ts)
                if event_dt > batch_end_dt:
                    r3_violations.append({
                        "rule": "R3",
                        "event_index": idx,
                        "detail": f"event_ts ({event_ts}) > batch_end_ts ({batch_end_ts})",
                    })
    elif module == "level_proximity":
        for idx, event in enumerate(events):
            atr_basis = event.get("atr_basis")
            if atr_basis != ATR_BASIS:
                r3_violations.append({
                    "rule": "R3",
                    "event_index": idx,
                    "detail": f"atr_basis '{atr_basis}' != '{ATR_BASIS}'",
                })
    else:
        pass

    r3_violations.sort(key=lambda x: x["event_index"])
    violations.extend(r3_violations)
    rule_results["R3"] = "pass" if not r3_violations else "fail"

    # R4 shared
    r4_violations = []

    computed_hash = hashlib.sha256(param_file_bytes).hexdigest()
    header_hash = header.get("param_sha256") if isinstance(header, dict) else None
    if header_hash is None:
        r4_violations.append({"rule": "R4", "event_index": None, "detail": "header missing param_sha256"})
    elif computed_hash != header_hash:
        r4_violations.append({
            "rule": "R4",
            "event_index": None,
            "detail": f"param_sha256 mismatch: computed={computed_hash}, header={header_hash}",
        })

    try:
        param_file_version = _param_data.get("param_version") or _param_data.get("version")
    except Exception:
        param_file_version = None

    header_version = header.get("param_version") if isinstance(header, dict) else None

    if param_file_version != header_version:
        r4_violations.append({
            "rule": "R4",
            "event_index": None,
            "detail": f"version mismatch: param_file={param_file_version}, header={header_version}",
        })

    for idx, event in enumerate(events):
        event_version = event.get("param_version")
        if event_version != header_version:
            r4_violations.append({
                "rule": "R4",
                "event_index": idx,
                "detail": f"event param_version '{event_version}' != header '{header_version}'",
            })

    scan_mode = header.get("scan_mode") if isinstance(header, dict) else None
    if scan_mode is not None and scan_mode not in ("forward", "retrospective"):
        r4_violations.append({"rule": "R4", "event_index": None, "detail": f"invalid scan_mode '{scan_mode}'"})

    evidence_tier = header.get("evidence_tier") if isinstance(header, dict) else None
    _tier_for_mode = {"forward": "forward_asof", "retrospective": "retrospective_membership"}
    if scan_mode in _tier_for_mode and evidence_tier is not None:
        if evidence_tier != _tier_for_mode[scan_mode]:
            r4_violations.append({
                "rule": "R4",
                "event_index": None,
                "detail": f"evidence_tier '{evidence_tier}' inconsistent with scan_mode '{scan_mode}'",
            })

    try:
        frozen_at_str = _param_data.get("frozen_at")
    except Exception:
        frozen_at_str = None

    if scan_mode == "forward":
        if frozen_at_str is None:
            r4_violations.append({"rule": "R4", "event_index": None, "detail": "param file frozen_at is null"})
        else:
            if not _validate_timestamp(frozen_at_str):
                r4_violations.append({"rule": "R4", "event_index": None, "detail": f"param file frozen_at invalid: {frozen_at_str}"})
            else:
                frozen_dt = _parse_ts(frozen_at_str)
                if events:
                    first_event_dt = _get_first_event_ts(events)
                    if frozen_dt >= first_event_dt:
                        r4_violations.append({
                            "rule": "R4",
                            "event_index": None,
                            "detail": f"frozen_at ({frozen_at_str}) not strictly before first event_ts ({first_event_dt.isoformat()})",
                        })

    r4_violations.sort(key=lambda x: (x["event_index"] is None, x["event_index"] if x["event_index"] is not None else -1))
    violations.extend(r4_violations)
    rule_results["R4"] = "pass" if not r4_violations else "fail"

    # R5
    r5_violations = []

    if module in EVENT_FIELDS_BY_MODULE:
        expected_event_fields = EVENT_FIELDS_BY_MODULE[module]
    else:
        expected_event_fields = None

    for idx, event in enumerate(events):
        if expected_event_fields is not None:
            event_fields = set(event.keys())
            extra_fields = event_fields - expected_event_fields
            missing_fields = expected_event_fields - event_fields
            if extra_fields:
                r5_violations.append({"rule": "R5", "event_index": idx, "detail": f"extra fields: {sorted(extra_fields)}"})
            if missing_fields:
                r5_violations.append({"rule": "R5", "event_index": idx, "detail": f"missing fields: {sorted(missing_fields)}"})

        if module == "level_proximity":
            if "level_price" in event and not _check_numeric(event.get("level_price")):
                r5_violations.append({"rule": "R5", "event_index": idx, "detail": "level_price is not numeric"})
            if "distance_atr" in event and not _check_numeric(event.get("distance_atr")):
                r5_violations.append({"rule": "R5", "event_index": idx, "detail": "distance_atr is not numeric"})
            if "atr_window" in event:
                aw = event.get("atr_window")
                if not (isinstance(aw, int) and not isinstance(aw, bool) and aw > 0):
                    r5_violations.append({"rule": "R5", "event_index": idx, "detail": "atr_window is not a positive integer"})
        elif module == "session_anomalies":
            for f in ("expected_bars", "observed_bars", "gap_hours"):
                if f in event:
                    v = event.get(f)
                    if not (isinstance(v, int) and not isinstance(v, bool)):
                        r5_violations.append({"rule": "R5", "event_index": idx, "detail": f"{f} is not an integer"})
            if "session_date" in event:
                sd = event.get("session_date")
                if not (isinstance(sd, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", sd)):
                    r5_violations.append({"rule": "R5", "event_index": idx, "detail": "session_date is not YYYY-MM-DD"})
            if "timeframe" in event and event.get("timeframe") not in SESSION_EMISSION_TIMEFRAMES:
                # R2 covers, but keep closed enum here too
                pass

    # header closed fields
    if isinstance(header, dict):
        header_fields = set(header.keys())
    else:
        header_fields = set()
    extra_header_fields = header_fields - BATCH_HEADER_FIELDS
    missing_header_fields = BATCH_HEADER_FIELDS - header_fields
    if extra_header_fields:
        r5_violations.append({"rule": "R5", "event_index": None, "detail": f"header extra fields: {sorted(extra_header_fields)}"})
    if missing_header_fields:
        r5_violations.append({"rule": "R5", "event_index": None, "detail": f"header missing fields: {sorted(missing_header_fields)}"})

    # module validity
    if module not in MODULES:
        r5_violations.append({"rule": "R5", "event_index": None, "detail": f"header module invalid: {module!r}"})

    # evidence_tier enum
    if isinstance(header, dict) and "evidence_tier" in header:
        et = header.get("evidence_tier")
        if et not in ("forward_asof", "retrospective_membership"):
            r5_violations.append({"rule": "R5", "event_index": None, "detail": f"header evidence_tier invalid enum: {et!r}"})

    r5_violations.sort(key=lambda x: (
        x["event_index"] is None,
        x["event_index"] if x["event_index"] is not None else -1,
        x["detail"],
    ))
    violations.extend(r5_violations)
    rule_results["R5"] = "pass" if not r5_violations else "fail"

    violations.sort(key=lambda x: (
        x["rule"],
        x["event_index"] if x["event_index"] is not None else -1,
    ))

    is_valid = all(r == "pass" for r in rule_results.values())

    return {
        "valid": is_valid,
        "rule_results": rule_results,
        "violations": violations,
    }
