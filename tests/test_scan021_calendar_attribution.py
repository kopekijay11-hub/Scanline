import json
from pathlib import Path
from scanline.calendar_attribution import load_calendar, attribute_clusters, rule_applies_to_symbol

SCAN19 = Path("records/scans/20261123T021148750070Z_72046b8e81b86046bcef1aa65486ee26")
CAL = Path("config/calendars/session_anomalies.calendar.v1.json")


def test_calendar_load_has_sha256():
    cal, sha = load_calendar(CAL)
    assert len(sha) == 64
    assert cal["calendar_version"] == "1.0.0"
    assert len(cal["rules"]) >= 10


def test_juneteenth_cluster_attributed():
    events = json.loads((SCAN19 / "events.json").read_text())["events"]
    cal, sha = load_calendar(CAL)
    out = attribute_clusters(events, cal, sha, years=[2026])
    # all Juneteenth clusters in window A: missing 2026-06-19 and stubs 2026-06-19
    jun_matches = [m for m in out["matches"] if m["session_date"] == "2026-06-19"]
    keys = {tuple(m["cluster_key"]) for m in jun_matches}
    assert ("missing_session", "2026-06-19") in keys
    assert ("stub_session", "2026-06-19") in keys
    # FEEDBEEF 2026-06-04 stub is not Juneteenth
    assert ("stub_session", "2026-06-04") not in keys


def test_control_days_no_false_attribution():
    # control set: 10th trading day of each month in fixture span - simple mechanical pick
    # We check no matches on those dates in window A events.
    events = json.loads((SCAN19 / "events.json").read_text())["events"]
    cal, sha = load_calendar(CAL)
    out = attribute_clusters(events, cal, sha, years=[2026])
    control_dates = {"2026-05-13", "2026-06-10"}  # 10th trading-ish days in window A
    for m in out["matches"]:
        assert m["session_date"] not in control_dates


def test_attribution_is_additive():
    # attribute_clusters returns annotations only; it must not mutate events
    events = json.loads((SCAN19 / "events.json").read_text())["events"]
    before = json.dumps(events)
    cal, sha = load_calendar(CAL)
    attribute_clusters(events, cal, sha, years=[2026])
    assert json.dumps(events) == before
