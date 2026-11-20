"""Hermetic tests for Scanline session-anomaly detector."""

from datetime import datetime, timedelta, timezone
from scanline.sessions import compute_events


def mk(symbol, ts):
    return {"symbol": symbol, "timeframe": "H1", "open_ts": ts, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0}


def params(expected=3, sun=2, zone="America/New_York", maint_start="17:00", maint_end="18:00", stub_tol=1, sun_tol=0):
    return {
        "module": "session_anomalies",
        "param_version": "1.0.0",
        "frozen_at": "2026-01-01T00:00:00Z",
        "clusters": {
            "GOLD": {
                "symbol": "GOLD",
                "zone": zone,
                "expected_bars": expected,
                "expected_sun_bars": sun,
                "maintenance_local_start": maint_start,
                "maintenance_local_end": maint_end,
                "stub_tolerance": stub_tol,
                "sun_tolerance": sun_tol,
            }
        },
    }


class TestAnomalies:
    def test_missing_and_stub_and_sunday(self):
        bars = []
        # first bound Monday 2026-01-05
        for h in range(2):
            bars.append(mk("GOLD", f"2026-01-05T{h:02d}:00:00Z"))
        # stub day Wednesday 2026-01-07: 1 bar (expected 3, tol 1 -> stub)
        bars.append(mk("GOLD", "2026-01-07T00:00:00Z"))
        # normal Thursday
        for h in range(3):
            bars.append(mk("GOLD", f"2026-01-08T{h:02d}:00:00Z"))
        # sunday 2026-01-11: 1 bar vs expected 2 -> sunday_anomaly
        bars.append(mk("GOLD", "2026-01-11T00:00:00Z"))
        # last bound Tuesday 2026-01-13
        for h in range(3):
            bars.append(mk("GOLD", f"2026-01-13T{h:02d}:00:00Z"))
        ev = compute_events(bars, params(expected=3, sun=2))
        types = [e["anomaly_type"] for e in ev]
        assert "missing_session" in types  # 2026-01-06
        assert "stub_session" in types      # 2026-01-07
        assert "sunday_anomaly" in types    # 2026-01-11
        # missing date is Jan 6
        miss = [e for e in ev if e["anomaly_type"] == "missing_session"][0]
        assert miss["session_date"] == "2026-01-06"

    def test_sunday_stubs_do_not_fire(self):
        # documented Sunday stubs: 2,3,0
        for sun_bars in (2, 3, 0):
            bars = []
            for h in range(3):
                bars.append(mk("GOLD", f"2026-01-05T{h:02d}:00:00Z"))
            # sunday with exactly expected stub count
            for h in range(sun_bars):
                bars.append(mk("GOLD", f"2026-01-11T{h:02d}:00:00Z"))
            for h in range(3):
                bars.append(mk("GOLD", f"2026-01-13T{h:02d}:00:00Z"))
            ev = compute_events(bars, params(expected=3, sun=sun_bars, sun_tol=0))
            sun_events = [e for e in ev if e["anomaly_type"] == "sunday_anomaly"]
            assert sun_events == [], (sun_bars, sun_events)

    def test_outside_bounds_do_not_fire(self):
        bars = []
        # only two days; no strictly inside dates
        for h in range(3):
            bars.append(mk("GOLD", f"2026-01-05T{h:02d}:00:00Z"))
        for h in range(3):
            bars.append(mk("GOLD", f"2026-01-06T{h:02d}:00:00Z"))
        ev = compute_events(bars, params(expected=3, sun=2))
        # no missing/stub/sunday session events (no inside dates)
        session_types = {"missing_session", "stub_session", "sunday_anomaly"}
        assert not (set(e["anomaly_type"] for e in ev) & session_types)

    def test_intra_session_gap_fires(self):
        bars = [
            mk("GOLD", "2026-01-05T00:00:00Z"),
            mk("GOLD", "2026-01-05T03:00:00Z"),
        ]
        # bounds same day? need last after; add another day
        bars.append(mk("GOLD", "2026-01-06T00:00:00Z"))
        ev = compute_events(bars, params(expected=3, sun=2))
        gaps = [e for e in ev if e["anomaly_type"] == "intra_session_gap"]
        assert len(gaps) >= 1

    def test_dst_summer_no_false_gap(self):
        # summer: maintenance 21-22 UTC; bars 20:00 and 22:00 UTC (gap across maintenance)
        bars = [
            mk("GOLD", "2026-07-15T20:00:00Z"),
            mk("GOLD", "2026-07-15T22:00:00Z"),
            mk("GOLD", "2026-07-16T00:00:00Z"),
        ]
        ev = compute_events(bars, params(expected=3, sun=2, zone="America/New_York"))
        gaps = [e for e in ev if e["anomaly_type"] == "intra_session_gap"]
        assert gaps == []

    def test_dst_winter_no_false_gap(self):
        # winter: maintenance 22-23 UTC; bars 21:00 and 23:00 UTC
        bars = [
            mk("GOLD", "2026-01-15T21:00:00Z"),
            mk("GOLD", "2026-01-15T23:00:00Z"),
            mk("GOLD", "2026-01-16T00:00:00Z"),
        ]
        ev = compute_events(bars, params(expected=3, sun=2, zone="America/New_York"))
        gaps = [e for e in ev if e["anomaly_type"] == "intra_session_gap"]
        assert gaps == []
