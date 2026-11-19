"""End-to-end test under the frozen production params (SCAN-004 Step 4)."""

import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from scanline.levels import compute_events
from scanline.validator import validate_batch

ROOT = Path(__file__).resolve().parents[1]
PARAMS_PATH = ROOT / "config" / "scanner_params.level_proximity.json"


def _fmt(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


@pytest.fixture
def production_params():
    return json.loads(PARAMS_PATH.read_text())


def test_frozen_params_e2e():
    params_bytes = PARAMS_PATH.read_bytes()
    params = json.loads(params_bytes)
    frozen_at = params["frozen_at"]
    frozen_dt = datetime.fromisoformat(frozen_at.replace("Z", "+00:00"))

    # D1 bar defining a structural level, closing before first emission.
    d1 = {
        "symbol": "GOLD",
        "timeframe": "D1",
        "open_ts": _fmt(frozen_dt - timedelta(days=1)),
        "open": 4020.0,
        "high": 4030.0,
        "low": 4010.0,
        "close": 4020.0,
    }

    # H1 emission series at real scale crossing grid line 4025.00.
    em = []
    for i in range(20):
        close = 4050.0 if i < 16 else 4024.5
        em.append({
            "symbol": "GOLD",
            "timeframe": "H1",
            "open_ts": _fmt(frozen_dt + timedelta(hours=i + 1)),
            "open": close,
            "high": close + 0.5,
            "low": close - 0.5,
            "close": close,
        })

    events = compute_events([d1], em, params)

    grid_events = [e for e in events if e["level_type"] == "grid_round" and e["level_price"] == 4025]
    assert len(grid_events) >= 1
    assert 0.0 <= grid_events[0]["distance_atr"] <= 0.5

    # Build header from the production file itself.
    event_ts_list = [e["event_ts"] for e in events]
    header = {
        "module": params["module"],
        "scan_mode": "forward",
        "evidence_tier": "forward_asof",
        "param_file": "scanner_params.level_proximity.json",
        "param_sha256": hashlib.sha256(params_bytes).hexdigest(),
        "param_version": params["param_version"],
        "frozen_at": params["frozen_at"],
        "universe": params["universe"],
        "emission_timeframes": params["emission_timeframes"],
        "definition_timeframe": params["definition_timeframe"],
        "batch_start_ts": min(event_ts_list),
        "batch_end_ts": max(event_ts_list),
    }

    result = validate_batch(events, header, params_bytes)
    assert result["valid"] is True
    assert all(r == "pass" for r in result["rule_results"].values())
    assert len(result["violations"]) == 0
