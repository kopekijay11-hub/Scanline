"""R3 batch causality validation (SCAN-015)."""

from typing import Any, Dict, List

from scanline.schema import ATR_BASIS
from scanline.validation.context import ValidationContext
from scanline.validation import utils


def validate_r3(ctx: ValidationContext) -> List[Dict[str, Any]]:
    violations: List[Dict[str, Any]] = []
    module = ctx.module
    events = ctx.events
    header = ctx.header

    if module == "session_anomalies":
        batch_end_ts = header.get("batch_end_ts") if isinstance(header, dict) else None
        if batch_end_ts is not None and utils.validate_timestamp(batch_end_ts):
            batch_end_dt = utils.parse_ts(batch_end_ts)
            for idx, event in enumerate(events):
                event_ts = event.get("event_ts")
                if event_ts is None or not utils.validate_timestamp(event_ts):
                    continue
                event_dt = utils.parse_ts(event_ts)
                if event_dt > batch_end_dt:
                    violations.append({
                        "rule": "R3",
                        "event_index": idx,
                        "detail": f"event_ts ({event_ts}) > batch_end_ts ({batch_end_ts})",
                    })
    elif module == "level_proximity":
        for idx, event in enumerate(events):
            atr_basis = event.get("atr_basis")
            if atr_basis != ATR_BASIS:
                violations.append({
                    "rule": "R3",
                    "event_index": idx,
                    "detail": f"atr_basis '{atr_basis}' != '{ATR_BASIS}'",
                })
    else:
        pass

    violations.sort(key=lambda x: x["event_index"])
    return violations
