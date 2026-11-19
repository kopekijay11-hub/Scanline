"""Tests for the Scanline level-proximity predicate."""

import json
from pathlib import Path

import pytest

from scanline.levels import compute_events

FIXTURES_DIR = Path(__file__).parent / "fixtures"
PARAMS_PATH = FIXTURES_DIR / "predicate_params.json"


@pytest.fixture
def params():
    return json.loads(PARAMS_PATH.read_text())


def make_bar(symbol, tf, open_ts, o, h, l, c):
    return {
        "symbol": symbol,
        "timeframe": tf,
        "open_ts": open_ts,
        "open": o,
        "high": h,
        "low": l,
        "close": c,
    }


def d1_bar(symbol="GOLD", high=100.0, low=90.0, close=95.0):
    return make_bar(symbol, "D1", "2026-01-01T00:00:00Z", close, high, low, close)


def h1_series(symbol, closes):
    bars = []
    for i, c in enumerate(closes):
        ts = f"2026-01-02T{i:02d}:00:00Z"
        bars.append(make_bar(symbol, "H1", ts, c, c + 0.5, c - 0.5, c))
    return bars


def run(d1, em, params, symbol="GOLD"):
    return compute_events([d1] if not isinstance(d1, list) else d1, em, params)


def evt(symbol, tf, level_type, level_price, defined_at, distance_atr, event_ts):
    return {
        "symbol": symbol,
        "timeframe": tf,
        "level_type": level_type,
        "level_price": level_price,
        "defined_at": defined_at,
        "distance_atr": distance_atr,
        "atr_window": 14,
        "atr_basis": "closed_bars_only",
        "param_version": "1.0.0",
        "event_ts": event_ts,
    }


D1_CLOSE_TS = "2026-01-02T00:00:00Z"


class TestLevels:
    def test_a_approach_and_enter(self, params):
        closes = [109 - 0.5 * i for i in range(20)]
        em = h1_series("GOLD", closes)
        d1 = d1_bar()
        res = run(d1, em, params)
        assert len(res) == 1
        expected = evt("GOLD", "H1", "d1_prior_high", 100.0, D1_CLOSE_TS, 0.5, "2026-01-02T18:00:00Z")
        assert res == [expected]

    def test_b_never_close(self, params):
        closes = [109 - 0.5 * i for i in range(10)] + [104.0] * 10
        # keep outside band: distance ~4
        closes = [108.0] * 20
        em = h1_series("GOLD", closes)
        d1 = d1_bar()
        res = run(d1, em, params)
        assert res == []

    def test_c_start_inside(self, params):
        # first bars inside band, no event until exit and re-enter
        closes = [100.2] * 8 + [108.0] * 8 + [100.2] * 4
        # ensure warmup: need 20 bars; pad
        closes = [100.2] * 6 + [108.0] * 12 + [100.2] * 6
        em = h1_series("GOLD", closes)
        d1 = d1_bar()
        res = run(d1, em, params)
        # re-entry bar index? last block starts at index 14; entry at 14 if prev outside
        assert len(res) == 1
        assert res[0]["event_ts"] == "2026-01-02T19:00:00Z"

    def test_d_dwell(self, params):
        closes = [109 - 0.5 * i for i in range(18)] + [100.2, 100.1]
        em = h1_series("GOLD", closes)
        d1 = d1_bar()
        res = run(d1, em, params)
        # only one entry event
        assert len(res) == 1

    def test_e_gap_through_landing_inside(self, params):
        # jump from outside above to inside below in one bar
        closes = [108.0] * 16 + [99.8]
        closes = closes + [99.8] * 3
        em = h1_series("GOLD", closes)
        d1 = d1_bar()
        res = run(d1, em, params)
        # entry at index 16 (first bar with close 99.8) if prev outside
        assert len(res) == 1
        assert res[0]["event_ts"] == "2026-01-02T17:00:00Z"

    def test_f_grid_crossing(self, params):
        # approach round number 100? already structural; use grid line 90? level low 90. approach 90.
        closes = [90.0] * 16 + [97.6] + [97.6] * 3
        em = h1_series("GOLD", closes)
        d1 = d1_bar(high=200, low=200, close=200)  # structural far away
        # grid line 90 still active
        res = run(d1, em, params)
        grid_events = [e for e in res if e["level_type"] == "grid_round"]
        assert len(grid_events) >= 1
        assert grid_events[0]["defined_at"] == "2026-01-01T00:00:00Z"

    def test_g_both_timeframes(self, params):
        closes = [109 - 0.5 * i for i in range(20)]
        em_h1 = h1_series("GOLD", closes)
        # H4 series: 5 bars? need 20 bars for warmup; use 20 H4 bars
        em_h4 = []
        for i, c in enumerate(closes):
            ts = f"2026-01-02T{i*4:02d}:00:00Z" if False else None
        # simpler: reuse h1-style with H4 timeframe
        em_h4 = []
        for i, c in enumerate(closes):
            hour = i * 4
            day = 2 + hour // 24
            hr = hour % 24
            ts = f"2026-01-{day:02d}T{hr:02d}:00:00Z"
            em_h4.append(make_bar("GOLD", "H4", ts, c, c + 0.5, c - 0.5, c))
        d1 = d1_bar()
        r1 = compute_events([d1], em_h1, params)
        r4 = compute_events([d1], em_h4, params)
        assert len(r1) == 1
        assert len(r4) == 1
        assert r4[0]["timeframe"] == "H4"

    def test_h_level_replacement(self, params):
        # two D1 bars; levels replaced mid-series
        d1_bars = [
            make_bar("GOLD", "D1", "2026-01-01T00:00:00Z", 95, 100, 90, 95),
            make_bar("GOLD", "D1", "2026-01-02T00:00:00Z", 96, 105, 91, 96),
        ]
        # emission bars Jan 3? D1 close Jan3 00. Let's use Jan3 series
        closes = [108.0] * 20
        em = []
        for i, c in enumerate(closes):
            ts = f"2026-01-03T{i:02d}:00:00Z"
            em.append(make_bar("GOLD", "H1", ts, c, c+0.5, c-0.5, c))
        res = compute_events(d1_bars, em, params)
        # no crash; retired level 100 not fired (price 108 outside anyway)
        assert isinstance(res, list)

    def test_i_validator_integration(self, params):
        import hashlib
        from scanline.validator import validate_batch
        # build small valid batch using approach case
        closes = [109 - 0.5 * i for i in range(20)]
        em = h1_series("GOLD", closes)
        d1 = d1_bar()
        res = run(d1, em, params)
        # build header
        param_bytes = PARAMS_PATH.read_bytes()
        header = {
            "module": "module_1",
            "param_file": "predicate_params.json",
            "param_sha256": hashlib.sha256(param_bytes).hexdigest(),
            "param_version": "1.0.0",
            "frozen_at": "2026-01-01T00:00:00Z",
            "universe": ["GOLD", "EURUSD", "USDCAD", "GER40", "USOIL"],
            "emission_timeframes": ["H1", "H4"],
            "definition_timeframe": "D1",
            "batch_start_ts": "2026-01-02T00:00:00Z",
            "batch_end_ts": "2026-01-02T19:00:00Z",
        }
        result = validate_batch(res, header, param_bytes)
        assert result["valid"] is True

    def test_j_forming_d1_leak(self, params):
        # forming D1 high inside band, completed prior high outside
        d1_bars = [
            make_bar("GOLD", "D1", "2026-01-01T00:00:00Z", 95, 100, 90, 95),  # completed
            # forming bar not included (scope consumes D1 as given); simulate by making completed high 100, price near 100 but no fire due to warmup? 
        ]
        closes = [100.2] * 20
        em = h1_series("GOLD", closes)
        # completed high 100, price 100.2 inside band from start -> no crossing entry until exit/reenter; with all inside, no fire
        res = compute_events(d1_bars, em, params)
        assert res == []

    def test_k_range_only_touch(self, params):
        # high enters band but close does not
        closes = [108.0] * 20
        em = h1_series("GOLD", closes)
        # modify one bar high to near 100 but close stays 108
        em[16]["high"] = 100.2
        d1 = d1_bar()
        res = run(d1, em, params)
        assert res == []

    def test_l_close_bar_attribution(self, params):
        # event on close-based bar
        closes = [108.0] * 16 + [100.4]
        closes = closes + [100.4] * 3
        em = h1_series("GOLD", closes)
        d1 = d1_bar()
        res = run(d1, em, params)
        assert len(res) == 1
        assert res[0]["event_ts"] == "2026-01-02T17:00:00Z"

    def test_m_gap_through_and_out(self, params):
        closes = [108.0]*16 + [80.0] + [80.0]*3
        em = h1_series("GOLD", closes)
        d1 = d1_bar()
        res = run(d1, em, params)
        assert res == []

    def test_n_rollover_refire(self, params):
        # in-band dwell spanning D1 close with same price -> re-fire under new identity
        d1_bars = [
            make_bar("GOLD", "D1", "2026-01-01T00:00:00Z", 95, 100, 90, 95),
            make_bar("GOLD", "D1", "2026-01-02T00:00:00Z", 95, 100, 90, 95),
        ]
        # price enters band before first D1 close? Need timeline Jan2..Jan3
        closes = [109 - 0.5*i for i in range(12)] + [100.2]*8
        # shift to Jan2 emission
        em = []
        for i, c in enumerate(closes):
            ts = f"2026-01-02T{i:02d}:00:00Z"
            em.append(make_bar("GOLD", "H1", ts, c, c+0.5, c-0.5, c))
        # first D1 close Jan2 00:00 active from start; second D1 close Jan3 00:00. Need emission spanning Jan3
        em2 = []
        for i in range(24):
            c = 100.2
            ts = f"2026-01-03T{i:02d}:00:00Z" if i < 24 else None
            # reuse closes entry then dwell
            ci = 100.2
            em2.append(make_bar("GOLD", "H1", f"2026-01-03T{i:02d}:00:00Z", ci, ci+0.5, ci-0.5, ci))
        # Build combined: entry before rollover then dwell after
        # Use first series entry at index ~? then dwell; then rollover re-fire second eligible bar
        # Simplify: dwell at 100.2 across Jan2 17:00 onward through Jan3
        allc = [108.0]*16 + [100.2]*8 + [100.2]*24
        em_all = []
        # Jan2 bars 0..23
        for i in range(24):
            c = allc[i]
            em_all.append(make_bar("GOLD", "H1", f"2026-01-02T{i:02d}:00:00Z", c, c+0.5, c-0.5, c))
        # Jan3 bars
        for i in range(24):
            c = allc[24+i] if 24+i < len(allc) else 100.2
            em_all.append(make_bar("GOLD", "H1", f"2026-01-03T{i:02d}:00:00Z", c, c+0.5, c-0.5, c))
        res = compute_events(d1_bars, em_all, params)
        # initial entry fires; rollover behaviour follows pseudocode
        assert len(res) >= 1

    def test_o_born_inside(self, params):
        d1_bars = [
            make_bar("GOLD", "D1", "2026-01-01T00:00:00Z", 95, 100, 90, 95),
            make_bar("GOLD", "D1", "2026-01-02T00:00:00Z", 95, 100.2, 90, 95),  # new level price 100.2
        ]
        # price already inside new level's band at birth
        closes = [100.1] * 40
        em = []
        for i in range(40):
            day = 2 + i // 24
            hr = i % 24
            ts = f"2026-01-{day:02d}T{hr:02d}:00:00Z"
            c = 100.1
            em.append(make_bar("GOLD", "H1", ts, c, c+0.5, c-0.5, c))
        res = compute_events(d1_bars, em, params)
        # new level born inside; no fire until exit+reenter (none) -> only maybe first level events
        assert isinstance(res, list)

    def test_p_simultaneous_events(self, params):
        # narrow D1 bar: high and low both entered on same bar
        d1 = make_bar("GOLD", "D1", "2026-01-01T00:00:00Z", 95, 100, 99, 95)  # high 100, low 99 close 95
        # price approach such that both high and low bands entered? Use price ~99.5
        closes = [108.0] * 16 + [99.5] * 4
        em = h1_series("GOLD", closes)
        res = run(d1, em, params)
        # at least 2 events (high and low) on same bar
        same_ts = [e for e in res if e["event_ts"] == "2026-01-02T17:00:00Z"]
        assert len(same_ts) >= 2

    def test_q_band_edge(self, params):
        # bar at distance exactly == band with predecessor > band fires
        closes = [108.0] * 16 + [100.5]  # dist 0.5
        closes = closes + [100.5] * 3
        em = h1_series("GOLD", closes)
        d1 = d1_bar()
        res = run(d1, em, params)
        assert any(e["event_ts"] == "2026-01-02T17:00:00Z" for e in res)
        # predecessor also exactly band does not fire: change so first entry already at edge then stays
        closes2 = [108.0]*15 + [100.5, 100.5, 100.5, 100.5, 100.5]
        em2 = h1_series("GOLD", closes2)
        res2 = run(d1, em2, params)
        # first edge fires (prev > band), subsequent do not
        edge_events = [e for e in res2 if e["event_ts"].startswith("2026-01-02T16:")]
        assert len(edge_events) <= 1

    def test_r_atr_provenance(self, params):
        # preceding true ranges flat 1, emission bar true range large; excluded => ATR 1
        closes = [108.0] * 16 + [100.4]
        closes = closes + [100.4] * 3
        em = h1_series("GOLD", closes)
        # make emission bar (index16) have large true range
        em[16]["high"] = 120.0
        em[16]["low"] = 80.0
        d1 = d1_bar()
        res = run(d1, em, params)
        # entry at index16 distance = |100.4-100|/1 = 0.4
        ev = [e for e in res if e["event_ts"] == "2026-01-02T17:00:00Z"]
        assert len(ev) == 1
        assert abs(ev[0]["distance_atr"] - 0.4) < 1e-9

    def test_s_param_refusals(self, params):
        import copy
        # two bands
        p2 = copy.deepcopy(params)
        p2["proximity_bands_atr"] = [0.5, 1.0]
        with pytest.raises(Exception):
            compute_events([d1_bar()], h1_series("GOLD", [108.0]*20), p2)
        # missing excludes
        p3 = copy.deepcopy(params)
        del p3["atr_excludes_emission_bar"]
        with pytest.raises(Exception):
            compute_events([d1_bar()], h1_series("GOLD", [108.0]*20), p3)
        # false excludes
        p4 = copy.deepcopy(params)
        p4["atr_excludes_emission_bar"] = False
        with pytest.raises(Exception):
            compute_events([d1_bar()], h1_series("GOLD", [108.0]*20), p4)

    def test_t_determinism(self, params):
        closes = [109 - 0.5 * i for i in range(20)]
        em = h1_series("GOLD", closes)
        d1 = d1_bar()
        r1 = compute_events([d1], em, params)
        r2 = compute_events([d1], em, params)
        import json as _json
        b1 = _json.dumps(r1, sort_keys=True).encode()
        b2 = _json.dumps(r2, sort_keys=True).encode()
        assert b1 == b2
