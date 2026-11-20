"""R5 closed-schema validation (SCAN-015)."""

import re
from typing import Any, Dict, List

from scanline.schema import (
    BATCH_HEADER_FIELDS,
    EVENT_FIELDS_BY_MODULE,
    MODULES,
    SESSION_EMISSION_TIMEFRAMES,
)
from scanline.validation.context import ValidationContext
from scanline.validation import utils


def validate_r5(ctx: ValidationContext) -> List[Dict[str, Any]]:
    violations: List[Dict[str, Any]] = []
    module = ctx.module
    events = ctx.events
    header = ctx.header

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
                violations.append({"rule": "R5", "event_index": idx, "detail": f"extra fields: {sorted(extra_fields)}"})
            if missing_fields:
                violations.append({"rule": "R5", "event_index": idx, "detail": f"missing fields: {sorted(missing_fields)}"})

        if module == "level_proximity":
            if "level_price" in event and not utils.check_numeric(event.get("level_price")):
                violations.append({"rule": "R5", "event_index": idx, "detail": "level_price is not numeric"})
            if "distance_atr" in event and not utils.check_numeric(event.get("distance_atr")):
                violations.append({"rule": "R5", "event_index": idx, "detail": "distance_atr is not numeric"})
            if "atr_window" in event:
                aw = event.get("atr_window")
                if not (isinstance(aw, int) and not isinstance(aw, bool) and aw > 0):
                    violations.append({"rule": "R5", "event_index": idx, "detail": "atr_window is not a positive integer"})
        elif module == "session_anomalies":
            for f in ("expected_bars", "observed_bars", "gap_hours"):
                if f in event:
                    v = event.get(f)
                    if not (isinstance(v, int) and not isinstance(v, bool)):
                        violations.append({"rule": "R5", "event_index": idx, "detail": f"{f} is not an integer"})
            if "session_date" in event:
                sd = event.get("session_date")
                if not (isinstance(sd, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", sd)):
                    violations.append({"rule": "R5", "event_index": idx, "detail": "session_date is not YYYY-MM-DD"})
            if "timeframe" in event and event.get("timeframe") not in SESSION_EMISSION_TIMEFRAMES:
                pass

    if isinstance(header, dict):
        header_fields = set(header.keys())
    else:
        header_fields = set()
    extra_header_fields = header_fields - BATCH_HEADER_FIELDS
    missing_header_fields = BATCH_HEADER_FIELDS - header_fields
    if extra_header_fields:
        violations.append({"rule": "R5", "event_index": None, "detail": f"header extra fields: {sorted(extra_header_fields)}"})
    if missing_header_fields:
        violations.append({"rule": "R5", "event_index": None, "detail": f"header missing fields: {sorted(missing_header_fields)}"})

    if module not in MODULES:
        violations.append({"rule": "R5", "event_index": None, "detail": f"header module invalid: {module!r}"})

    if isinstance(header, dict) and "evidence_tier" in header:
        et = header.get("evidence_tier")
        if et not in ("forward_asof", "retrospective_membership"):
            violations.append({"rule": "R5", "event_index": None, "detail": f"header evidence_tier invalid enum: {et!r}"})

    violations.sort(key=lambda x: (
        x["event_index"] is None,
        x["event_index"] if x["event_index"] is not None else -1,
        x["detail"],
    ))
    return violations
