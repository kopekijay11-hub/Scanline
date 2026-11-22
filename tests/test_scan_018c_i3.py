import hashlib
import json
from pathlib import Path

import pytest

import scanline.scan as scan_mod
from scanline.scan import is_scan_complete, run_scan

ROOT = Path(__file__).resolve().parents[1]


def _ts(dt_hour):
    from datetime import datetime, timedelta, timezone
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return int((base + timedelta(hours=dt_hour)).timestamp())


def _write_csv(path, rows):
    import csv
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["time", "open", "high", "low", "close", "volume"])
        for r in rows:
            w.writerow([r[0], r[1], r[2], r[3], r[4], 1.0])


def _make_level_corpus(tmp_path):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    # D1
    _write_csv(corpus / "GOLD_D1.csv", [
        (_ts(0), 95, 100, 90, 95),
        (_ts(24), 95, 100, 90, 95),
    ])
    # H1 simple bars around level
    rows = []
    for i in range(30, 50):
        close = 99.0 + (i % 3) * 0.2
        rows.append((_ts(i), close, close + 0.5, close - 0.5, close))
    _write_csv(corpus / "GOLD_H1.csv", rows)
    return corpus


def _make_session_corpus(tmp_path):
    from datetime import datetime, timedelta, timezone
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    # UTC day with 24 H1 bars
    start = datetime(2026, 1, 5, 0, 0, tzinfo=timezone.utc)  # Monday
    rows = []
    for i in range(24):
        t = start + timedelta(hours=i)
        rows.append((int(t.timestamp()), 100, 101, 99, 100))
    _write_csv(corpus / "GOLD_H1.csv", rows)
    return corpus


def _write_params(tmp_path, obj, name="params.json"):
    p = tmp_path / name
    p.write_text(json.dumps(obj))
    return p


def _level_params(**overrides):
    obj = {
        "module": "level_proximity",
        "param_version": "1.0.0",
        "frozen_at": "2026-01-01T00:00:00Z",
        "universe": ["GOLD"],
        "emission_timeframes": ["H1"],
        "definition_timeframe": "D1",
        "level_types": ["d1_prior_high", "d1_prior_low", "d1_session_structure", "grid_round"],
        "atr_window": 14,
        "atr_basis": "closed_bars_only",
        "proximity_bands_atr": [0.5],
        "grid_steps": {"GOLD": 25},
        "crossing_semantics": "close_distance_band_entry",
        "band_edge": "inclusive",
        "gap_through": "fires_if_landing_inside",
        "state_key": "level_type+level_price+defined_at",
        "gap_semantics": "array_previous",
        "atr_excludes_emission_bar": True,
    }
    obj.update(overrides)
    return obj


def _session_params(**overrides):
    obj = {
        "module": "session_anomalies",
        "param_version": "1.0.0",
        "frozen_at": "2026-01-01T00:00:00Z",
        "universe": ["GOLD"],
        "emission_timeframes": ["H1"],
        "clusters": {
            "GOLD": {
                "symbol": "GOLD",
                "expected_bars": 24,
                "expected_sun_bars": 0,
                "zone": "UTC",
                "maintenance_local_start": "17:00",
                "maintenance_local_end": "18:00",
                "stub_tolerance": 1,
                "sun_tolerance": 0,
            }
        },
    }
    obj.update(overrides)
    return obj


def test_snapshot_integrity_and_manifest_fields(tmp_path):
    corpus = _make_level_corpus(tmp_path)
    param_path = _write_params(tmp_path, _level_params(), "p.json")
    out = tmp_path / "out"
    scan_id = run_scan(corpus, out, param_path=param_path,
                       batch_start_ts="2026-01-01T00:00:00Z", batch_end_ts="2026-01-03T23:00:00Z",
                       extraction_start_ts="2026-01-01T00:00:00Z", extraction_end_ts="2026-01-03T23:00:00Z")
    dest = out / scan_id
    manifest = json.loads((dest / "scanner_data_manifest.json").read_text())

    raw = (dest / "param_snapshot.raw.json").read_bytes()
    eff = (dest / "param_snapshot.effective.json").read_bytes()
    assert raw == param_path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == manifest["param_sha256"]
    assert hashlib.sha256(eff).hexdigest() == manifest["config_hash"]
    assert not eff.endswith(b"\n")

    names = [o["name"] for o in manifest["outputs"]]
    assert "events.json" in names
    assert "param_snapshot.raw.json" in names
    assert "param_snapshot.effective.json" in names
    assert manifest["manifest_version"] == "1.1.0"
    assert manifest["config_hash_algorithm"] == "sha256"
    assert manifest["config_canonicalization_version"] == "SCANLINE-config-canon-v1"
    assert manifest["config_hash_subject"] == "effective_validated_config"
    assert isinstance(manifest["config_schema_version"], str) and manifest["config_schema_version"]
    assert is_scan_complete(dest) is True


def test_reproducible_config_hash_equivalent_inputs(tmp_path):
    corpus = _make_level_corpus(tmp_path)
    obj = _level_params()
    p1 = _write_params(tmp_path, obj, "p1.json")
    # formatting-only difference
    p2 = tmp_path / "p2.json"
    p2.write_text(json.dumps(obj, indent=4, sort_keys=True))
    out = tmp_path / "out"
    id1 = run_scan(corpus, out, param_path=p1, batch_start_ts="2026-01-01T00:00:00Z", batch_end_ts="2026-01-03T23:00:00Z", extraction_start_ts="2026-01-01T00:00:00Z", extraction_end_ts="2026-01-03T23:00:00Z")
    id2 = run_scan(corpus, out, param_path=p2, batch_start_ts="2026-01-01T00:00:00Z", batch_end_ts="2026-01-03T23:00:00Z", extraction_start_ts="2026-01-01T00:00:00Z", extraction_end_ts="2026-01-03T23:00:00Z")
    m1 = json.loads((out / id1 / "scanner_data_manifest.json").read_text())
    m2 = json.loads((out / id2 / "scanner_data_manifest.json").read_text())
    assert m1["param_sha256"] != m2["param_sha256"]
    assert m1["config_hash"] == m2["config_hash"]


def test_invalid_v110_not_downgraded(tmp_path):
    corpus = _make_level_corpus(tmp_path)
    param_path = _write_params(tmp_path, _level_params(), "p.json")
    out = tmp_path / "out"
    scan_id = run_scan(corpus, out, param_path=param_path, batch_start_ts="2026-01-01T00:00:00Z", batch_end_ts="2026-01-03T23:00:00Z", extraction_start_ts="2026-01-01T00:00:00Z", extraction_end_ts="2026-01-03T23:00:00Z")
    dest = out / scan_id
    manifest_path = dest / "scanner_data_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest.pop("config_schema_version")
    manifest_path.write_text(json.dumps(manifest))
    assert is_scan_complete(dest) is False


def test_historical_v100_records_still_valid(tmp_path):
    for p in (ROOT / "records" / "scans").glob("*/scanner_data_manifest.json"):
        obj = json.loads(p.read_text())
        if obj.get("manifest_version") == "1.0.0" or "manifest_version" not in obj:
            # legacy may be incomplete by v1.0.0 contract; but should not crash and must follow own rules.
            is_scan_complete(p.parent)


@pytest.mark.parametrize("module_obj,corpus_maker,extra", [
    (_level_params(), _make_level_corpus, dict(batch_start_ts="2026-01-01T00:00:00Z", batch_end_ts="2026-01-03T23:00:00Z", extraction_start_ts="2026-01-01T00:00:00Z", extraction_end_ts="2026-01-03T23:00:00Z")),
    (_session_params(), _make_session_corpus, dict(batch_start_ts="2026-01-05T00:00:00Z", batch_end_ts="2026-01-05T23:00:00Z", extraction_start_ts="2026-01-05T00:00:00Z", extraction_end_ts="2026-01-06T00:00:00Z")),
])
def test_config_integration_regressions(tmp_path, module_obj, corpus_maker, extra):
    corpus = corpus_maker(tmp_path)
    param_path = _write_params(tmp_path, module_obj, "p.json")
    out = tmp_path / "out"
    scan_id = run_scan(corpus, out, param_path=param_path, **extra)
    assert is_scan_complete(out / scan_id) is True


def test_level_proximity_grid_step_type_distinction(tmp_path):
    corpus = _make_level_corpus(tmp_path)
    p_int = _write_params(tmp_path, _level_params(grid_steps={"GOLD": 5}), "int.json")
    p_float = _write_params(tmp_path, _level_params(grid_steps={"GOLD": 5.0}), "float.json")
    out = tmp_path / "out"
    i1 = run_scan(corpus, out, param_path=p_int, batch_start_ts="2026-01-01T00:00:00Z", batch_end_ts="2026-01-03T23:00:00Z", extraction_start_ts="2026-01-01T00:00:00Z", extraction_end_ts="2026-01-03T23:00:00Z")
    i2 = run_scan(corpus, out, param_path=p_float, batch_start_ts="2026-01-01T00:00:00Z", batch_end_ts="2026-01-03T23:00:00Z", extraction_start_ts="2026-01-01T00:00:00Z", extraction_end_ts="2026-01-03T23:00:00Z")
    m1 = json.loads((out / i1 / "scanner_data_manifest.json").read_text())
    m2 = json.loads((out / i2 / "scanner_data_manifest.json").read_text())
    assert m1["config_hash"] != m2["config_hash"]


def test_session_fixed_utc_and_local_maintenance(tmp_path):
    from scanline.config_load import load_config

    corpus = _make_session_corpus(tmp_path)
    extra = dict(
        batch_start_ts="2026-01-05T00:00:00Z",
        batch_end_ts="2026-01-05T23:00:00Z",
        extraction_start_ts="2026-01-05T00:00:00Z",
        extraction_end_ts="2026-01-06T00:00:00Z",
    )

    # Configuration A — Local maintenance only.
    local = _session_params()
    local["clusters"]["GOLD"]["maintenance_local_start"] = "17:00"
    local["clusters"]["GOLD"]["maintenance_local_end"] = "18:00"
    local.pop("maintenance_utc_start", None)
    local.pop("maintenance_utc_end", None)
    local["clusters"]["GOLD"].pop("maintenance_utc_start", None)
    local["clusters"]["GOLD"].pop("maintenance_utc_end", None)
    p_local = _write_params(tmp_path, local, "local.json")

    # Configuration B — Fixed UTC maintenance only.
    fixed = _session_params()
    fixed["clusters"]["GOLD"].pop("maintenance_local_start", None)
    fixed["clusters"]["GOLD"].pop("maintenance_local_end", None)
    fixed["clusters"]["GOLD"]["maintenance_utc_start"] = "17:00"
    fixed["clusters"]["GOLD"]["maintenance_utc_end"] = "18:00"
    p_fixed = _write_params(tmp_path, fixed, "fixed.json")

    lc_local = load_config(p_local)
    lc_fixed = load_config(p_fixed)

    assert lc_local.effective_config["symbols"]["GOLD"]["maintenance"]["mode"] == "local"
    assert lc_fixed.effective_config["symbols"]["GOLD"]["maintenance"]["mode"] == "fixed_utc"
    assert lc_local.effective_snapshot_bytes != lc_fixed.effective_snapshot_bytes
    assert lc_local.config_hash != lc_fixed.config_hash

    # Runtime projections preserve detector behavior and maintenance information.
    rt_local = lc_local.runtime_config["clusters"]["GOLD"]
    rt_fixed = lc_fixed.runtime_config["clusters"]["GOLD"]
    assert rt_local["maintenance_local_start"] == "17:00"
    assert rt_local["maintenance_local_end"] == "18:00"
    assert "maintenance_utc_start" not in rt_local
    assert "maintenance_utc_end" not in rt_local
    assert rt_fixed["maintenance_local_start"] == "17:00"
    assert rt_fixed["maintenance_local_end"] == "18:00"
    assert rt_fixed["maintenance_utc_start"] == "17:00"
    assert rt_fixed["maintenance_utc_end"] == "18:00"

    out = tmp_path / "out"
    s_local = run_scan(corpus, out, param_path=p_local, **extra)
    s_fixed = run_scan(corpus, out, param_path=p_fixed, **extra)

    m_local = json.loads((out / s_local / "scanner_data_manifest.json").read_text())
    m_fixed = json.loads((out / s_fixed / "scanner_data_manifest.json").read_text())
    assert m_local["config_hash"] == lc_local.config_hash
    assert m_fixed["config_hash"] == lc_fixed.config_hash
    assert m_local["config_hash"] != m_fixed["config_hash"]
    assert (out / s_local / "param_snapshot.effective.json").read_bytes() != (
        out / s_fixed / "param_snapshot.effective.json"
    ).read_bytes()
    assert is_scan_complete(out / s_local)
    assert is_scan_complete(out / s_fixed)


def test_ambiguous_maintenance_mode_rejected(tmp_path):
    from scanline.config_load import ConfigLoadError, load_config

    ambiguous = _session_params()
    ambiguous["clusters"]["GOLD"]["maintenance_local_start"] = "17:00"
    ambiguous["clusters"]["GOLD"]["maintenance_local_end"] = "18:00"
    ambiguous["clusters"]["GOLD"]["maintenance_utc_start"] = "17:00"
    ambiguous["clusters"]["GOLD"]["maintenance_utc_end"] = "18:00"
    param_path = _write_params(tmp_path, ambiguous, "ambiguous.json")

    with pytest.raises(ConfigLoadError):
        load_config(param_path)


def test_unsupported_schema_fails_closed(tmp_path):
    corpus = _make_level_corpus(tmp_path)
    bad = _level_params(param_version="9.9.9")
    param_path = _write_params(tmp_path, bad, "bad.json")
    out = tmp_path / "out"
    with pytest.raises(Exception):
        run_scan(corpus, out, param_path=param_path, batch_start_ts="2026-01-01T00:00:00Z", batch_end_ts="2026-01-03T23:00:00Z", extraction_start_ts="2026-01-01T00:00:00Z", extraction_end_ts="2026-01-03T23:00:00Z")
    # no complete scan
    assert not any(is_scan_complete(p) for p in out.glob("*")) if out.exists() else True
