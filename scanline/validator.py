"""As-of validator for Scanline event batches (SCAN-015 decomposition)."""

import json

from typing import Any, Dict, List

from scanline.validation.context import ValidationContext
from scanline.validation import r1, r2, r3, r4, r5
from scanline.validation import utils
from scanline.schema import normalize_module_id

# Backward-compatible helper aliases.
_parse_ts = utils.parse_ts
_validate_timestamp = utils.validate_timestamp
_check_numeric = utils.check_numeric
_get_first_event_ts = utils.get_first_event_ts
_cluster_expected_bars = utils.cluster_expected_bars


def validate_batch(
    events: List[Dict[str, Any]],
    header: Dict[str, Any],
    param_file_bytes: bytes,
) -> Dict[str, Any]:
    violations: List[Dict[str, Any]] = []
    rule_results: Dict[str, str] = {}

    try:
        _param_data = json.loads(param_file_bytes)
    except Exception:
        _param_data = {}
    if not isinstance(_param_data, dict):
        _param_data = {}

    _raw_module = header.get("module") if isinstance(header, dict) else None
    module = normalize_module_id(_raw_module)

    ctx = ValidationContext(
        events=events,
        header=header,
        param_bytes=param_file_bytes,
        param_data=_param_data,
        raw_module=_raw_module,
        module=module,
    )

    r1_v = r1.validate_r1(ctx)
    r2_v = r2.validate_r2(ctx)
    r3_v = r3.validate_r3(ctx)
    r4_v = r4.validate_r4(ctx)
    r5_v = r5.validate_r5(ctx)

    for rule_v in (r1_v, r2_v, r3_v, r4_v, r5_v):
        violations.extend(rule_v)

    rule_results["R1"] = "pass" if not r1_v else "fail"
    rule_results["R2"] = "pass" if not r2_v else "fail"
    rule_results["R3"] = "pass" if not r3_v else "fail"
    rule_results["R4"] = "pass" if not r4_v else "fail"
    rule_results["R5"] = "pass" if not r5_v else "fail"

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
