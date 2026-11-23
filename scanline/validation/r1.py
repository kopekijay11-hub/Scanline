"""R1 causal validation (SCAN-015)."""

from typing import Any, Dict, List

from scanline.schema import (
    ANOMALY_TYPES,
    EMISSION_TIMEFRAMES,
    LEVEL_TYPES,
    SESSION_EMISSION_TIMEFRAMES,
)
from scanline.validation.context import ValidationContext
from scanline.validation import utils


def validate_r1(ctx: ValidationContext) -> List[Dict[str, Any]]:
    violations: List[Dict[str, Any]] = []
    module = ctx.module
    events = ctx.events
    header = ctx.header
    param_data = ctx.param_data

    if module == "session_anomalies":
        frozen_at_str = param_data.get("frozen_at")
        scan_mode = header.get("scan_mode") if isinstance(header, dict) else None
        batch_end_ts = header.get("batch_end_ts") if isinstance(header, dict) else None
        for idx, event in enumerate(events):
            defined_at = event.get("defined_at")
            event_ts = event.get("event_ts")
            if defined_at is None or event_ts is None:
                violations.append({"rule": "R1", "event_index": idx, "detail": "missing timestamp"})
                continue
            if not utils.validate_timestamp(defined_at) or not utils.validate_timestamp(event_ts):
                violations.append({"rule": "R1", "event_index": idx, "detail": "invalid timestamp format"})
                continue
            if scan_mode == "forward":
                defined_dt = utils.parse_ts(defined_at)
                event_dt = utils.parse_ts(event_ts)
                if defined_dt > event_dt:
                    violations.append({
                        "rule": "R1",
                        "event_index": idx,
                        "detail": f"defined_at ({defined_at}) > event_ts ({event_ts})",
                    })
            else:
                if frozen_at_str is not None and utils.validate_timestamp(frozen_at_str):
                    if utils.parse_ts(defined_at) != utils.parse_ts(frozen_at_str):
                        violations.append({
                            "rule": "R1",
                            "event_index": idx,
                            "detail": f"defined_at ({defined_at}) != frozen_at ({frozen_at_str})",
                        })
                symbol = event.get("symbol")
                atype = event.get("anomaly_type")
                if atype == "sunday_anomaly":
                    sched = utils.cluster_expected_sun_bars(param_data, symbol)
                    sched_label = "expected_sun_bars"
                else:
                    sched = utils.cluster_expected_bars(param_data, symbol)
                    sched_label = "expected_bars"
                if sched is None:
                    violations.append({
                        "rule": "R1",
                        "event_index": idx,
                        "detail": f"symbol '{symbol}' not in frozen cluster schedule",
                    })
                else:
                    try:
                        if int(event.get("expected_bars")) != int(sched):
                            violations.append({
                                "rule": "R1",
                                "event_index": idx,
                                "detail": f"expected_bars {event.get('expected_bars')} != frozen {sched_label} {sched} for {symbol}",
                            })
                    except (TypeError, ValueError):
                        violations.append({
                            "rule": "R1",
                            "event_index": idx,
                            "detail": "expected_bars is not an integer",
                        })
    elif module == "level_proximity":
        grid_steps = (param_data.get("grid_steps") or {}) if isinstance(param_data, dict) else {}

        for idx, event in enumerate(events):
            level_type = event.get("level_type")
            if level_type == "grid_round":
                symbol = event.get("symbol")
                level_price = event.get("level_price")
                if not utils.grid_member(grid_steps, symbol, level_price):
                    violations.append({
                        "rule": "R1",
                        "event_index": idx,
                        "detail": f"grid_round level_price {level_price} not a member of {symbol} grid",
                    })
                continue
            defined_at = event.get("defined_at")
            event_ts = event.get("event_ts")
            if defined_at is None or event_ts is None:
                violations.append({"rule": "R1", "event_index": idx, "detail": "missing timestamp"})
            elif not utils.validate_timestamp(defined_at) or not utils.validate_timestamp(event_ts):
                violations.append({"rule": "R1", "event_index": idx, "detail": "invalid timestamp format"})
            else:
                defined_dt = utils.parse_ts(defined_at)
                event_dt = utils.parse_ts(event_ts)
                if defined_dt > event_dt:
                    violations.append({
                        "rule": "R1",
                        "event_index": idx,
                        "detail": f"defined_at ({defined_at}) > event_ts ({event_ts})",
                    })
    else:
        pass

    violations.sort(key=lambda x: x["event_index"])
    return violations
