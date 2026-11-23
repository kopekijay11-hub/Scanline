import math
import pytest

from scanline.prereg import (
    CeilingResult,
    binom_pmf,
    binom_sf,
    ceiling_breach,
    cluster_ceiling,
    cluster_key_for_event,
    count_clusters,
    zero_baseline_min_exposure,
)


def test_review_verified_ceiling_pins():
    # SCAN-020 §5(b) script-verified values (authoritative)
    alpha = 0.0125
    assert cluster_ceiling(0, 1.0, alpha) == 6
    assert cluster_ceiling(1, 1.0, alpha) == 8
    assert cluster_ceiling(16, 1.0, alpha) == 32
    assert cluster_ceiling(3, 1.0, alpha) == 12


def test_review_batch_arithmetic():
    alpha = 0.0125
    cases = [
        (16, 18, 32, False),
        (1, 1, 8, False),
        (0, 2, 6, False),
        (3, 4, 12, False),
    ]
    for kb, ka, c, breach in cases:
        r = ceiling_breach(kb, ka, 100.0, 100.0, alpha)
        assert r.ceiling == c
        assert r.breach is breach


def test_zero_baseline_min_exposure():
    alpha = 0.0125
    # review §5(b) table values
    assert math.isclose(zero_baseline_min_exposure(alpha, 0.500 / 100), 876.4, rel_tol=0, abs_tol=0.1)
    assert math.isclose(zero_baseline_min_exposure(alpha, 0.100 / 100), 4382.0, rel_tol=0, abs_tol=0.1)
    assert math.isclose(zero_baseline_min_exposure(alpha, 0.200 / 100), 2191.0, rel_tol=0, abs_tol=0.1)


def test_cluster_key_gap_includes_hour():
    e = {"anomaly_type": "intra_session_gap", "session_date": "2026-06-01", "event_ts": "2026-06-01T22:00:00Z"}
    assert cluster_key_for_event(e) == ("intra_session_gap", "2026-06-01", "2026-06-01T22")
    m = {"anomaly_type": "missing_session", "session_date": "2026-06-19", "event_ts": "2026-06-19T23:00:00Z"}
    assert cluster_key_for_event(m) == ("missing_session", "2026-06-19")


def test_count_clusters_known():
    events = [
        {"anomaly_type": "intra_session_gap", "session_date": "2026-06-01", "event_ts": "2026-06-01T22:00:00Z", "symbol": "A"},
        {"anomaly_type": "intra_session_gap", "session_date": "2026-06-01", "event_ts": "2026-06-01T22:00:00Z", "symbol": "B"},
        {"anomaly_type": "missing_session", "session_date": "2026-06-19", "event_ts": "2026-06-19T23:00:00Z", "symbol": "A"},
    ]
    c = count_clusters(events)
    assert c["events"] == 3
    assert c["clusters"] == 2
    assert c["per_type"]["intra_session_gap"]["clusters"] == 1
    assert c["per_type"]["intra_session_gap"]["events"] == 2


def test_binom_sf_basic():
    assert math.isclose(binom_sf(10, 0, 0.5), 1.0)
    assert math.isclose(binom_sf(10, 11, 0.5), 0.0)
    assert math.isclose(binom_sf(1, 1, 0.3), 0.3)


def test_invalid_inputs():
    with pytest.raises(Exception):
        cluster_ceiling(-1, 1.0, 0.0125)
    with pytest.raises(Exception):
        cluster_ceiling(0, 0.0, 0.0125)
    with pytest.raises(Exception):
        cluster_ceiling(0, 1.0, 1.0)
    with pytest.raises(Exception):
        zero_baseline_min_exposure(0.0125, 0.0)


def test_rho_floor_material_gate():
    # arithmetic breach but not material
    r = ceiling_breach(0, 7, 100.0, 100.0, 0.0125, rho_floor=0.1)
    assert r.ceiling == 6
    assert r.breach is False  # 7/100 = 0.07 not > 0.1
    assert r.material is False
    r2 = ceiling_breach(0, 7, 100.0, 100.0, 0.0125, rho_floor=0.05)
    assert r2.breach is True
    assert r2.material is True
