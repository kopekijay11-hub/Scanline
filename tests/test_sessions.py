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


from scanline.sessions import _parse_hhmm, GAP_TOLERANCE


class TestScan016A:
    def test_parse_hhmm_raises_on_malformed(self):
        import pytest
        for bad in (None, "abc", "1:2:3", [], {}):
            with pytest.raises(ValueError):
                _parse_hhmm(bad)

    def test_gap_tolerance_constant(self):
        from datetime import timedelta
        assert GAP_TOLERANCE == timedelta(minutes=1)

    def test_parse_hhmm_valid(self):
        assert _parse_hhmm("17:30") == (17, 30)
        assert _parse_hhmm("17") == (17, 0)
        assert _parse_hhmm(5) == (5, 0)


class TestScan016B:
    def test_honolulu_defect_fixed(self):
        bars = [
            mk("GOLD", "2026-01-15T03:00:00Z"),
            mk("GOLD", "2026-01-15T04:30:00Z"),
            mk("GOLD", "2026-01-16T00:00:00Z"),
        ]
        ev = compute_events(bars, params(zone="Pacific/Honolulu"))
        gaps = [e for e in ev if e["anomaly_type"] == "intra_session_gap"]
        assert gaps == []

    def test_utc_maintenance_window(self):
        bars = [
            mk("GOLD", "2026-01-15T16:30:00Z"),
            mk("GOLD", "2026-01-15T18:30:00Z"),
            mk("GOLD", "2026-01-16T00:00:00Z"),
        ]
        ev = compute_events(bars, params(zone="UTC"))
        gaps = [e for e in ev if e["anomaly_type"] == "intra_session_gap"]
        assert gaps == []

    def test_positive_offset_tokyo(self):
        bars = [
            mk("GOLD", "2026-01-15T08:00:00Z"),
            mk("GOLD", "2026-01-15T09:30:00Z"),
            mk("GOLD", "2026-01-16T00:00:00Z"),
        ]
        ev = compute_events(bars, params(zone="Asia/Tokyo"))
        gaps = [e for e in ev if e["anomaly_type"] == "intra_session_gap"]
        assert gaps == []

    def test_negative_offset_ny_winter(self):
        bars = [
            mk("GOLD", "2026-01-15T21:00:00Z"),
            mk("GOLD", "2026-01-15T23:30:00Z"),
            mk("GOLD", "2026-01-16T00:00:00Z"),
        ]
        ev = compute_events(bars, params(zone="America/New_York"))
        gaps = [e for e in ev if e["anomaly_type"] == "intra_session_gap"]
        assert gaps == []

    def test_local_date_differs_from_utc(self):
        bars = [
            mk("GOLD", "2026-01-15T03:00:00Z"),
            mk("GOLD", "2026-01-15T04:30:00Z"),
            mk("GOLD", "2026-01-16T00:00:00Z"),
        ]
        ev = compute_events(bars, params(zone="Pacific/Honolulu"))
        gaps = [e for e in ev if e["anomaly_type"] == "intra_session_gap"]
        assert gaps == []

    def test_cross_midnight_maintenance(self):
        bars = [
            mk("GOLD", "2026-01-16T02:30:00Z"),
            mk("GOLD", "2026-01-16T04:30:00Z"),
            mk("GOLD", "2026-01-17T00:00:00Z"),
        ]
        ev = compute_events(bars, params(zone="America/New_York", maint_start="22:00", maint_end="02:00"))
        gaps = [e for e in ev if e["anomaly_type"] == "intra_session_gap"]
        assert gaps == []

    def test_utc_day_boundary_tolerance_allowed(self):
        bars = [
            mk("GOLD", "2026-01-15T05:00:00Z"),
            mk("GOLD", "2026-01-15T06:10:00Z"),
            mk("GOLD", "2026-01-16T00:00:00Z"),
        ]
        ev = compute_events(bars, params(zone="America/New_York", maint_start="00:00", maint_end="00:30"))
        gaps = [e for e in ev if e["anomaly_type"] == "intra_session_gap"]
        assert gaps == []

    def test_utc_day_boundary_tolerance_not_relaxed(self):
        bars = [
            mk("GOLD", "2026-01-15T05:15:00Z"),
            mk("GOLD", "2026-01-15T06:25:00Z"),
            mk("GOLD", "2026-01-16T00:00:00Z"),
        ]
        ev = compute_events(bars, params(zone="America/New_York", maint_start="00:00", maint_end="00:30"))
        gaps = [e for e in ev if e["anomaly_type"] == "intra_session_gap"]
        assert len(gaps) >= 1

    def test_dst_spring_offset(self):
        bars = [
            mk("GOLD", "2026-03-08T21:00:00Z"),
            mk("GOLD", "2026-03-08T22:30:00Z"),
            mk("GOLD", "2026-03-09T00:00:00Z"),
        ]
        ev = compute_events(bars, params(zone="America/New_York"))
        gaps = [e for e in ev if e["anomaly_type"] == "intra_session_gap"]
        assert gaps == []

    def test_dst_autumn_offset(self):
        bars = [
            mk("GOLD", "2026-11-01T22:00:00Z"),
            mk("GOLD", "2026-11-01T23:30:00Z"),
            mk("GOLD", "2026-11-02T00:00:00Z"),
        ]
        ev = compute_events(bars, params(zone="America/New_York"))
        gaps = [e for e in ev if e["anomaly_type"] == "intra_session_gap"]
        assert gaps == []

    def test_negative_case_real_gap(self):
        bars = [
            mk("GOLD", "2026-01-15T00:00:00Z"),
            mk("GOLD", "2026-01-15T02:00:00Z"),
            mk("GOLD", "2026-01-16T00:00:00Z"),
        ]
        ev = compute_events(bars, params(zone="Pacific/Honolulu"))
        gaps = [e for e in ev if e["anomaly_type"] == "intra_session_gap"]
        assert len(gaps) >= 1

    def test_fixed_utc_unchanged(self):
        # fixed UTC mode still uses UTC date directly
        bars = [
            mk("GOLD", "2026-01-15T16:30:00Z"),
            mk("GOLD", "2026-01-15T18:30:00Z"),
            mk("GOLD", "2026-01-16T00:00:00Z"),
        ]
        p = params(zone="UTC")
        # inject fixed utc fields
        p["clusters"]["GOLD"]["maintenance_utc_start"] = "17:00"
        p["clusters"]["GOLD"]["maintenance_utc_end"] = "18:00"
        ev = compute_events(bars, p)
        gaps = [e for e in ev if e["anomaly_type"] == "intra_session_gap"]
        assert gaps == []

    def test_existing_dst_summer_no_false_gap(self):
        bars = [
            mk("GOLD", "2026-07-15T20:00:00Z"),
            mk("GOLD", "2026-07-15T22:00:00Z"),
            mk("GOLD", "2026-07-16T00:00:00Z"),
        ]
        ev = compute_events(bars, params(zone="America/New_York"))
        gaps = [e for e in ev if e["anomaly_type"] == "intra_session_gap"]
        assert gaps == []

    def test_existing_dst_winter_no_false_gap(self):
        bars = [
            mk("GOLD", "2026-01-15T21:00:00Z"),
            mk("GOLD", "2026-01-15T23:00:00Z"),
            mk("GOLD", "2026-01-16T00:00:00Z"),
        ]
        ev = compute_events(bars, params(zone="America/New_York"))
        gaps = [e for e in ev if e["anomaly_type"] == "intra_session_gap"]
        assert gaps == []


# ---------------------------------------------------------------------------
# Characterization tests (SCAN-017B): document CURRENT session anomaly behavior.
# These tests record existing implementation behavior for unresolved product
# decisions (boundary exclusion, weekday one-sided counts, Sunday absolute
# tolerance, Saturday skip, holiday-as-weekday, duplicate inflation). They are
# NOT approval of those behaviors and must not be treated as desired policy.
# ---------------------------------------------------------------------------


class TestSessionCurrentBehavior:
    """Characterization of current session anomaly behavior (not approved policy)."""

    def _bars(self, dates_counts):
        bars = []
        for d, n in dates_counts:
            for h in range(n):
                bars.append(mk("GOLD", f"{d}T{h:02d}:00:00Z"))
        return bars

    # --- 1. Boundary tests ---

    def test_boundary_first_date_excluded_even_if_incomplete(self):
        # first UTC date has 1 bar (incomplete) but is excluded from session-level
        # detection; interior dates are complete.
        bars = self._bars([
            ("2026-01-05", 1),  # first, incomplete
            ("2026-01-06", 3),
            ("2026-01-07", 3),
            ("2026-01-08", 3),
            ("2026-01-09", 3),  # last
        ])
        ev = compute_events(bars, params(expected=3, sun=2))
        session_dates = [e["session_date"] for e in ev if e["anomaly_type"] in ("missing_session", "stub_session", "sunday_anomaly")]
        assert "2026-01-05" not in session_dates

    def test_boundary_last_date_excluded_even_if_incomplete(self):
        bars = self._bars([
            ("2026-01-05", 3),  # first
            ("2026-01-06", 3),
            ("2026-01-07", 3),
            ("2026-01-08", 3),
            ("2026-01-09", 1),  # last, incomplete
        ])
        ev = compute_events(bars, params(expected=3, sun=2))
        session_dates = [e["session_date"] for e in ev if e["anomaly_type"] in ("missing_session", "stub_session", "sunday_anomaly")]
        assert "2026-01-09" not in session_dates

    def test_boundary_one_date_input_no_session_anomalies(self):
        bars = self._bars([("2026-01-05", 1)])
        ev = compute_events(bars, params(expected=3, sun=2))
        session_types = {"missing_session", "stub_session", "sunday_anomaly"}
        assert not (set(e["anomaly_type"] for e in ev) & session_types)
        assert ev == []

    def test_boundary_two_date_input_no_session_anomalies(self):
        bars = self._bars([("2026-01-05", 1), ("2026-01-06", 1)])
        ev = compute_events(bars, params(expected=3, sun=2))
        session_types = {"missing_session", "stub_session", "sunday_anomaly"}
        assert not (set(e["anomaly_type"] for e in ev) & session_types)

    def test_boundary_interior_missing_weekday_fires(self):
        bars = self._bars([
            ("2026-01-05", 3),  # first
            ("2026-01-07", 3),  # last (skip interior Tuesday)
        ])
        ev = compute_events(bars, params(expected=3, sun=2))
        missing = [e for e in ev if e["anomaly_type"] == "missing_session"]
        assert any(e["session_date"] == "2026-01-06" for e in missing)

    # --- 2. Weekday count tests ---

    def _weekday_scenario(self, observed):
        bars = self._bars([
            ("2026-01-05", 3),   # first
            ("2026-01-07", observed),  # interior Wednesday target
            ("2026-01-09", 3),   # last
        ])
        return compute_events(bars, params(expected=3, sun=2, stub_tol=1))

    def test_weekday_exact_expected_count_no_anomaly(self):
        ev = self._weekday_scenario(3)
        target_events = [e for e in ev if e["session_date"] == "2026-01-07" and e["anomaly_type"] in ("missing_session", "stub_session")]
        assert target_events == []

    def test_weekday_count_at_stub_tolerance_boundary_accepted(self):
        # observed == expected - stub_tolerance (2) is accepted (no anomaly)
        ev = self._weekday_scenario(2)
        target_events = [e for e in ev if e["session_date"] == "2026-01-07" and e["anomaly_type"] in ("missing_session", "stub_session")]
        assert target_events == []

    def test_weekday_count_beyond_stub_tolerance_boundary_fires(self):
        # observed == expected - stub_tolerance - 1 (1) fires stub_session
        ev = self._weekday_scenario(1)
        target_events = [e for e in ev if e["session_date"] == "2026-01-07" and e["anomaly_type"] == "stub_session"]
        assert len(target_events) == 1

    def test_weekday_zero_observed_bars_missing(self):
        ev = self._weekday_scenario(0)
        target_events = [e for e in ev if e["session_date"] == "2026-01-07" and e["anomaly_type"] == "missing_session"]
        assert len(target_events) == 1

    def test_weekday_over_count_no_anomaly(self):
        ev = self._weekday_scenario(5)
        target_events = [e for e in ev if e["session_date"] == "2026-01-07" and e["anomaly_type"] in ("missing_session", "stub_session")]
        assert target_events == []

    def test_weekday_expected_bars_zero_disables_detection(self):
        bars = self._bars([
            ("2026-01-05", 3),   # first
            ("2026-01-07", 0),   # interior Wednesday target, 0 bars
            ("2026-01-09", 3),   # last
        ])
        ev = compute_events(bars, params(expected=0, sun=2, stub_tol=1))
        target_events = [e for e in ev if e["session_date"] == "2026-01-07" and e["anomaly_type"] in ("missing_session", "stub_session")]
        assert target_events == []

    # --- 3. Sunday tests ---

    def _sunday_scenario(self, observed, sun, sun_tol):
        bars = self._bars([
            ("2026-01-05", 3),   # first Monday
            ("2026-01-11", observed),  # interior Sunday
            ("2026-01-13", 3),   # last Tuesday
        ])
        return compute_events(bars, params(expected=3, sun=sun, sun_tol=sun_tol))

    def test_sunday_expected_zero_observed_zero_no_anomaly(self):
        ev = self._sunday_scenario(0, 0, 0)
        target_events = [e for e in ev if e["session_date"] == "2026-01-11" and e["anomaly_type"] == "sunday_anomaly"]
        assert target_events == []

    def test_sunday_observed_greater_than_zero_with_zero_expectation(self):
        ev = self._sunday_scenario(2, 0, 0)
        target_events = [e for e in ev if e["session_date"] == "2026-01-11" and e["anomaly_type"] == "sunday_anomaly"]
        assert len(target_events) == 1

    def test_sunday_nonzero_tolerance_absolute(self):
        # within tolerance both directions: no anomaly
        for observed in (1, 2, 3):
            ev = self._sunday_scenario(observed, 2, 1)
            target_events = [e for e in ev if e["session_date"] == "2026-01-11" and e["anomaly_type"] == "sunday_anomaly"]
            assert target_events == [], observed
        # beyond tolerance both directions: anomaly
        for observed in (0, 4):
            ev = self._sunday_scenario(observed, 2, 1)
            target_events = [e for e in ev if e["session_date"] == "2026-01-11" and e["anomaly_type"] == "sunday_anomaly"]
            assert len(target_events) == 1, observed

    def test_sunday_under_count_fires(self):
        ev = self._sunday_scenario(1, 2, 0)
        target_events = [e for e in ev if e["session_date"] == "2026-01-11" and e["anomaly_type"] == "sunday_anomaly"]
        assert len(target_events) == 1

    def test_sunday_exact_expected_count_no_anomaly(self):
        ev = self._sunday_scenario(2, 2, 0)
        target_events = [e for e in ev if e["session_date"] == "2026-01-11" and e["anomaly_type"] == "sunday_anomaly"]
        assert target_events == []

    def test_sunday_over_count_fires(self):
        ev = self._sunday_scenario(3, 2, 0)
        target_events = [e for e in ev if e["session_date"] == "2026-01-11" and e["anomaly_type"] == "sunday_anomaly"]
        assert len(target_events) == 1

    def test_sunday_zero_observed_with_nonzero_expectation(self):
        ev = self._sunday_scenario(0, 2, 0)
        target_events = [e for e in ev if e["session_date"] == "2026-01-11" and e["anomaly_type"] == "sunday_anomaly"]
        assert len(target_events) == 1

    # --- 4. Saturday and holiday tests ---

    def test_saturday_skipped(self):
        bars = self._bars([
            ("2026-01-05", 3),   # first Monday
            ("2026-01-10", 0),   # interior Saturday (zero bars)
            ("2026-01-12", 3),   # last Monday
        ])
        ev = compute_events(bars, params(expected=3, sun=2))
        target_events = [e for e in ev if e["session_date"] == "2026-01-10" and e["anomaly_type"] in ("missing_session", "stub_session", "sunday_anomaly")]
        assert target_events == []

    def test_interior_weekday_zero_bars_missing_even_holiday(self):
        # 2026-01-01 is a Thursday (New Year's Day) but treated as ordinary weekday.
        bars = self._bars([
            ("2025-12-29", 3),   # first Monday
            ("2026-01-01", 0),   # interior Thursday holiday, zero bars
            ("2026-01-05", 3),   # last Monday
        ])
        ev = compute_events(bars, params(expected=3, sun=2))
        target_events = [e for e in ev if e["session_date"] == "2026-01-01" and e["anomaly_type"] == "missing_session"]
        assert len(target_events) == 1

    # --- 5. Duplicate input tests ---

    def test_duplicate_identical_bars_inflate_count(self):
        bars = self._bars([
            ("2026-01-05", 3),   # first
            ("2026-01-09", 3),   # last
        ])
        # interior Wednesday: one unique bar plus two identical duplicates -> 3 observed
        bars.append(mk("GOLD", "2026-01-07T00:00:00Z"))
        bars.append(mk("GOLD", "2026-01-07T00:00:00Z"))
        bars.append(mk("GOLD", "2026-01-07T00:00:00Z"))
        ev = compute_events(bars, params(expected=3, sun=2, stub_tol=1))
        target_events = [e for e in ev if e["session_date"] == "2026-01-07" and e["anomaly_type"] in ("missing_session", "stub_session")]
        assert target_events == []

    def test_duplicate_same_timestamp_differing_ohlcv_no_gap(self):
        bars = [
            mk("GOLD", "2026-01-05T00:00:00Z"),
        ]
        bar2 = mk("GOLD", "2026-01-05T00:00:00Z")
        bar2["close"] = 2.0
        bars.append(bar2)
        bars.append(mk("GOLD", "2026-01-06T00:00:00Z"))
        ev = compute_events(bars, params(expected=3, sun=2))
        gaps = [e for e in ev if e["anomaly_type"] == "intra_session_gap"]
        assert gaps == []

    def test_duplicate_bars_inflating_observed_counts_suppress_stub(self):
        bars = self._bars([
            ("2026-01-05", 3),   # first
            ("2026-01-09", 3),   # last
        ])
        # interior Wednesday: one unique bar plus one duplicate -> 2 observed (boundary)
        bars.append(mk("GOLD", "2026-01-07T00:00:00Z"))
        bars.append(mk("GOLD", "2026-01-07T00:00:00Z"))
        ev = compute_events(bars, params(expected=3, sun=2, stub_tol=1))
        target_events = [e for e in ev if e["session_date"] == "2026-01-07" and e["anomaly_type"] == "stub_session"]
        assert target_events == []

    def test_duplicate_timestamps_no_positive_duration_gap(self):
        bars = [
            mk("GOLD", "2026-01-05T00:00:00Z"),
            mk("GOLD", "2026-01-05T00:00:00Z"),
            mk("GOLD", "2026-01-05T01:00:00Z"),
            mk("GOLD", "2026-01-06T00:00:00Z"),
        ]
        ev = compute_events(bars, params(expected=3, sun=2))
        gaps = [e for e in ev if e["anomaly_type"] == "intra_session_gap"]
        assert gaps == []

    # --- 6. Other tests ---

    def test_empty_input_returns_empty_event_list(self):
        assert compute_events([], params()) == []

    def test_existing_defaults_unchanged(self):
        from scanline.sessions import _cluster_info
        info = _cluster_info({"expected_bars": 3}, "")
        assert info["zone"] == "UTC"
        assert info["maintenance_local_start"] == "17:00"
        assert info["maintenance_local_end"] == "18:00"
        assert info["stub_tolerance"] == 1
        assert info["sun_tolerance"] == 0
        assert info["expected_sun_bars"] == 0

    def test_existing_config_validation_unchanged(self):
        import pytest
        from scanline.sessions import validate_session_config
        # missing required expected_bars
        p = {"module": "session_anomalies", "param_version": "1.0.0", "frozen_at": "2026-01-01T00:00:00Z", "clusters": {"GOLD": {"symbol": "GOLD", "zone": "UTC"}}}
        with pytest.raises(ValueError):
            validate_session_config(p)
        # unknown field
        p2 = {"module": "session_anomalies", "param_version": "1.0.0", "frozen_at": "2026-01-01T00:00:00Z", "clusters": {"GOLD": {"symbol": "GOLD", "zone": "UTC", "expected_bars": 3}}, "foo": 1}
        with pytest.raises(ValueError):
            validate_session_config(p2)
        # invalid type
        p3 = {"module": "session_anomalies", "param_version": "1.0.0", "frozen_at": "2026-01-01T00:00:00Z", "clusters": {"GOLD": {"symbol": "GOLD", "zone": "UTC", "expected_bars": "3"}}}
        with pytest.raises(ValueError):
            validate_session_config(p3)


class TestMixedSymbolInput:
    """Mixed-symbol input protection (SCAN-017C)."""

    def _multi_params(self):
        p = params()
        p["clusters"]["SILVER"] = {
            "symbol": "SILVER",
            "zone": "America/New_York",
            "expected_bars": 3,
            "expected_sun_bars": 2,
            "maintenance_local_start": "17:00",
            "maintenance_local_end": "18:00",
            "stub_tolerance": 1,
            "sun_tolerance": 0,
        }
        return p

    def test_homogeneous_gold_input_succeeds(self):
        bars = [mk("GOLD", "2026-01-05T00:00:00Z"), mk("GOLD", "2026-01-06T00:00:00Z")]
        ev = compute_events(bars, params())
        assert isinstance(ev, list)

    def test_mixed_gold_silver_list_rejected(self):
        import pytest
        bars = [mk("GOLD", "2026-01-05T00:00:00Z"), mk("SILVER", "2026-01-06T00:00:00Z")]
        with pytest.raises(ValueError, match="mixed-symbol"):
            compute_events(bars, self._multi_params())

    def test_mixed_symbol_rejection_independent_of_order(self):
        import pytest
        bars = [mk("SILVER", "2026-01-05T00:00:00Z"), mk("GOLD", "2026-01-06T00:00:00Z")]
        with pytest.raises(ValueError, match="mixed-symbol"):
            compute_events(bars, self._multi_params())

    def test_explicit_symbol_with_symbolless_bars_works(self):
        bars = [
            {"timeframe": "H1", "open_ts": "2026-01-05T00:00:00Z", "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0},
            {"timeframe": "H1", "open_ts": "2026-01-06T00:00:00Z", "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0},
        ]
        ev = compute_events("GOLD", bars, params())
        assert isinstance(ev, list)

    def test_dictionary_multi_symbol_input_works(self):
        bars = {
            "GOLD": [mk("GOLD", "2026-01-05T00:00:00Z")],
            "SILVER": [mk("SILVER", "2026-01-05T00:00:00Z")],
        }
        ev = compute_events(bars, self._multi_params())
        assert isinstance(ev, list)

    def test_list_of_tuples_multi_symbol_input_works(self):
        bars = [
            ("GOLD", [mk("GOLD", "2026-01-05T00:00:00Z")]),
            ("SILVER", [mk("SILVER", "2026-01-05T00:00:00Z")]),
        ]
        ev = compute_events(bars, self._multi_params())
        assert isinstance(ev, list)

    def test_scan_execution_unaffected(self):
        # Covered by test_scan.py; keep a smoke import here.
        from scanline.scan import run_scan
        assert run_scan is not None


class TestMixedTimeframeInput:
    """Mixed-timeframe input protection (SCAN-017D)."""

    def test_homogeneous_h1_input_succeeds(self):
        bars = [mk("GOLD", "2026-01-05T00:00:00Z"), mk("GOLD", "2026-01-06T00:00:00Z")]
        ev = compute_events(bars, params())
        assert isinstance(ev, list)

    def test_mixed_h1_h4_input_rejected(self):
        import pytest
        b1 = mk("GOLD", "2026-01-05T00:00:00Z")
        b2 = mk("GOLD", "2026-01-06T00:00:00Z")
        b2["timeframe"] = "H4"
        with pytest.raises(ValueError, match="mixed-timeframe"):
            compute_events([b1, b2], params())

    def test_mixed_timeframe_rejection_independent_of_order(self):
        import pytest
        b1 = mk("GOLD", "2026-01-05T00:00:00Z")
        b1["timeframe"] = "H4"
        b2 = mk("GOLD", "2026-01-06T00:00:00Z")
        with pytest.raises(ValueError, match="mixed-timeframe"):
            compute_events([b1, b2], params())

    def test_bars_without_timeframe_preserve_behavior(self):
        bars = [
            {"symbol": "GOLD", "open_ts": "2026-01-05T00:00:00Z", "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0},
            {"symbol": "GOLD", "open_ts": "2026-01-06T00:00:00Z", "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0},
        ]
        ev = compute_events(bars, params())
        assert isinstance(ev, list)

    def test_dictionary_input_separate_homogeneous_groups_succeeds(self):
        bars = {
            "GOLD": [mk("GOLD", "2026-01-05T00:00:00Z")],
            "SILVER": [mk("SILVER", "2026-01-05T00:00:00Z")],
        }
        p = params()
        p["clusters"]["SILVER"] = p["clusters"]["GOLD"].copy()
        p["clusters"]["SILVER"]["symbol"] = "SILVER"
        ev = compute_events(bars, p)
        assert isinstance(ev, list)

    def test_list_of_tuples_preserves_behavior(self):
        bars = [
            ("GOLD", [mk("GOLD", "2026-01-05T00:00:00Z")]),
            ("SILVER", [mk("SILVER", "2026-01-05T00:00:00Z")]),
        ]
        p = params()
        p["clusters"]["SILVER"] = p["clusters"]["GOLD"].copy()
        p["clusters"]["SILVER"]["symbol"] = "SILVER"
        ev = compute_events(bars, p)
        assert isinstance(ev, list)

    def test_scan_execution_unaffected(self):
        from scanline.scan import run_scan
        assert run_scan is not None
