"""R2 type/timeframe validation (SCAN-015)."""

from typing import Any, Dict, List

from scanline.schema import (
    ANOMALY_TYPES,
    EMISSION_TIMEFRAMES,
    LEVEL_TYPES,
    SESSION_EMISSION_TIMEFRAMES,
)
from scanline.validation.context import ValidationContext


def validate_r2(ctx: ValidationContext) -> List[Dict[str, Any]]:
    violations: List[Dict[str, Any]] = []
    module = ctx.module
    events = ctx.events

    if module == "session_anomalies":
        for idx, event in enumerate(events):
            anomaly_type = event.get("anomaly_type")
            if anomaly_type not in ANOMALY_TYPES:
                violations.append({
                    "rule": "R2",
                    "event_index": idx,
                    "detail": f"anomaly_type '{anomaly_type}' not in ANOMALY_TYPES",
                })
            timeframe = event.get("timeframe")
            if timeframe not in SESSION_EMISSION_TIMEFRAMES:
                violations.append({
                    "rule": "R2",
                    "event_index": idx,
                    "detail": f"timeframe '{timeframe}' not in SESSION_EMISSION_TIMEFRAMES",
                })
    elif module == "level_proximity":
        for idx, event in enumerate(events):
            level_type = event.get("level_type")
            if level_type not in LEVEL_TYPES:
                violations.append({
                    "rule": "R2",
                    "event_index": idx,
                    "detail": f"level_type '{level_type}' not in LEVEL_TYPES",
                })
            timeframe = event.get("timeframe")
            if timeframe not in EMISSION_TIMEFRAMES:
                violations.append({
                    "rule": "R2",
                    "event_index": idx,
                    "detail": f"timeframe '{timeframe}' not in EMISSION_TIMEFRAMES",
                })
    else:
        pass

    violations.sort(key=lambda x: x["event_index"])
    return violations
