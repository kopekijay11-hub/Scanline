import json
from pathlib import Path
from scanline.calendar_attribution import load_calendar, attribute_clusters, ATTRIBUTABLE_ANOMALY_TYPES

SCAN19 = Path("records/scans/20261123T021148750070Z_72046b8e81b86046bcef1aa65486ee26")
CAL = Path("config/calendars/session_anomalies.calendar.v2.json")


def test_v2_calendar_load_has_sha256():
    cal, sha = load_calendar(CAL)
    assert len(sha) == 64
    assert cal["calendar_version"] == "2.0.0"
    assert cal["calendar_id"] == "session_anomalies.calendar.v2"


def test_v2_restricts_to_missing_stub():
    events = json.loads((SCAN19 / "events.json").read_text())["events"]
    cal, sha = load_calendar(CAL)
    out = attribute_clusters(events, cal, sha, years=[2026])
    assert out["matches"]
    assert {m["cluster_key"][0] for m in out["matches"]} <= set(ATTRIBUTABLE_ANOMALY_TYPES)
    keys = {tuple(m["cluster_key"]) for m in out["matches"]}
    assert ("missing_session", "2026-06-19") in keys
    assert ("stub_session", "2026-06-19") in keys
    # SCAN-021 v1 false positives must not appear
    assert ("intra_session_gap", "2024-07-04", "2024-07-04T22") not in keys
    assert not any(k[0] in {"intra_session_gap", "sunday_anomaly"} for k in keys)


def test_v2_attribution_is_additive():
    events = json.loads((SCAN19 / "events.json").read_text())["events"]
    before = json.dumps(events)
    cal, sha = load_calendar(CAL)
    attribute_clusters(events, cal, sha, years=[2026])
    assert json.dumps(events) == before
