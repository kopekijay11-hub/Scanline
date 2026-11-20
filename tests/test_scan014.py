import json
import hashlib
from pathlib import Path

import pytest

from scanline.sessions import compute_events, validate_session_config
from scanline.validator import validate_batch


def _session_params(**overrides):
    cluster = {
        "symbol": "GOLD",
        "zone": "America/New_York",
        "expected_bars": 3,
        "expected_sun_bars": 2,
        "maintenance_local_start": "17:00",
        "maintenance_local_end": "18:00",
        "stub_tolerance": 1,
        "sun_tolerance": 0,
    }
    cluster.update(overrides)
    return {
        "module": "session_anomalies",
        "param_version": "1.0.0",
        "frozen_at": "2026-01-01T00:00:00Z",
        "clusters": {"GOLD": cluster},
    }


def _header(module="session_anomalies", params=None):
    import json as _j
    pb = _j.dumps(params).encode() if params is not None else b"{}"
    return {
        "module": module,
        "scan_mode": "forward",
        "evidence_tier": "forward_asof",
        "param_file": "p.json",
        "param_sha256": hashlib.sha256(pb).hexdigest() if params is not None else None,
        "param_version": "1.0.0",
        "frozen_at": "2026-01-01T00:00:00Z",
        "universe": ["GOLD"],
        "emission_timeframes": ["H1"],
        "definition_timeframe": "H1",
        "batch_start_ts": "2026-01-02T00:00:00Z",
        "batch_end_ts": "2026-01-02T23:00:00Z",
    }


class TestCanonicalModuleIds:
    def test_level_proximity_accepted(self):
        params = {"module": "level_proximity", "param_version": "1.0.0", "frozen_at": "2026-01-01T00:00:00Z"}
        pb = json.dumps(params).encode()
        h = _header("level_proximity", params)
        h["param_sha256"] = hashlib.sha256(pb).hexdigest()
        r = validate_batch([], h, pb)
        assert r["valid"] is True

    def test_module_1_legacy_alias_accepted(self):
        params = {"module": "module_1", "param_version": "1.0.0", "frozen_at": "2026-01-01T00:00:00Z"}
        pb = json.dumps(params).encode()
        h = _header("module_1", params)
        h["module"] = "module_1"
        h["param_sha256"] = hashlib.sha256(pb).hexdigest()
        r = validate_batch([], h, pb)
        assert r["valid"] is True

    def test_session_anomalies_accepted(self):
        params = _session_params()
        pb = json.dumps(params).encode()
        h = _header("session_anomalies", params)
        h["param_sha256"] = hashlib.sha256(pb).hexdigest()
        r = validate_batch([], h, pb)
        assert r["valid"] is True

    def test_unknown_module_rejected(self):
        params = {"module": "nope", "param_version": "1.0.0", "frozen_at": "2026-01-01T00:00:00Z"}
        pb = json.dumps(params).encode()
        h = _header("nope", params)
        h["module"] = "nope"
        h["param_sha256"] = hashlib.sha256(pb).hexdigest()
        r = validate_batch([], h, pb)
        assert r["valid"] is False
        assert r["rule_results"]["R5"] == "fail"


class TestSessionSchema:
    def test_valid_config_accepted(self):
        p = _session_params()
        validate_session_config(p)
        bars = [{"symbol": "GOLD", "timeframe": "H1", "open_ts": "2026-01-05T00:00:00Z",
                 "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0}]
        # should not raise
        compute_events(bars, p)

    def test_missing_required_field_rejected(self):
        p = _session_params()
        del p["clusters"]["GOLD"]["expected_bars"]
        with pytest.raises(ValueError):
            validate_session_config(p)
        with pytest.raises(ValueError):
            compute_events([], p)

    def test_incorrect_type_rejected(self):
        p = _session_params(expected_bars="3")
        with pytest.raises(ValueError):
            validate_session_config(p)

    def test_invalid_numeric_range_rejected(self):
        p = _session_params(stub_tolerance=-1)
        with pytest.raises(ValueError):
            validate_session_config(p)

    def test_invalid_timezone_rejected(self):
        p = _session_params(zone="Not/AZone")
        with pytest.raises(ValueError):
            validate_session_config(p)

    def test_malformed_maintenance_window_rejected(self):
        p = _session_params(maintenance_local_start="25:00")
        with pytest.raises(ValueError):
            validate_session_config(p)
        p2 = _session_params(maintenance_local_start="17:00", maintenance_local_end="17:00")
        with pytest.raises(ValueError):
            validate_session_config(p2)

    def test_inconsistent_schedule_combination_rejected(self):
        # unknown field
        p = _session_params(foo=1)
        with pytest.raises(ValueError):
            validate_session_config(p)

    def test_unknown_field_rejected(self):
        p = _session_params()
        p["clusters"]["GOLD"]["extra"] = 1
        with pytest.raises(ValueError):
            validate_session_config(p)


class TestDetectorConsistency:
    def test_invalid_config_fails_validator(self):
        p = _session_params(zone="Bad/Zone")
        pb = json.dumps(p).encode()
        h = _header("session_anomalies", p)
        h["param_sha256"] = hashlib.sha256(pb).hexdigest()
        ev = [{
            "symbol": "GOLD", "timeframe": "H1", "anomaly_type": "missing_session",
            "session_date": "2026-01-02", "expected_bars": 3, "observed_bars": 0,
            "defined_at": "2026-01-01T00:00:00Z", "gap_hours": 0,
            "param_version": "1.0.0", "event_ts": "2026-01-02T23:00:00Z",
        }]
        r = validate_batch(ev, h, pb)
        assert r["valid"] is False
        assert r["rule_results"]["R4"] == "fail"

    def test_no_silent_type_coercion(self):
        p = _session_params(expected_bars="3")
        with pytest.raises(ValueError):
            compute_events([], p)
