import hashlib
import json
from pathlib import Path

import pytest

from scanline.config_load import load_config, LoadedConfig, ConfigLoadError
from scanline.config_registry import (
    UnknownModuleError,
    UnknownParamVersionError,
    MissingSchemaVersionError,
    AmbiguousConfigFamilyError,
    UnknownFieldError,
    InvalidFieldTypeError,
    UnsupportedLegacyFormError,
    resolve_schema,
    _REGISTRY,
)
from scanline.scan import run_scan, is_scan_complete


ROOT = Path(__file__).resolve().parents[1]


def _write(path: Path, obj):
    path.write_text(json.dumps(obj))
    return path


def _lp_base(**overrides):
    obj = {
        "module": "level_proximity",
        "param_version": "1.0.0",
        "frozen_at": "2026-11-19T03:25:04Z",
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


def _session_base(**overrides):
    obj = {
        "module": "session_anomalies",
        "param_version": "1.0.0",
        "frozen_at": "2026-01-01T00:00:00Z",
        "clusters": {
            "GOLD": {
                "symbol": "GOLD",
                "expected_bars": 24,
                "zone": "UTC",
            }
        },
    }
    obj.update(overrides)
    return obj


class TestSchemaRegistry:
    def test_known_module_and_version_mappings(self):
        from scanline.config_load import _ensure_default_registry
        _ensure_default_registry()
        for pv in ["1.0.0", "1.1.0", "2.0.0", "2.1.0"]:
            entry = resolve_schema(_lp_base(param_version=pv))
            assert entry.module == "level_proximity"
            assert entry.config_family == "level_proximity"
            assert entry.config_schema_version == "1"
            assert entry.param_version == pv

        s = resolve_schema(_session_base())
        assert s.module == "session_anomalies"
        assert s.config_family == "session_anomalies"

    def test_unknown_module(self):
        with pytest.raises(UnknownModuleError):
            resolve_schema(_lp_base(module="nope"))

    def test_unknown_param_version(self):
        with pytest.raises(UnknownParamVersionError):
            resolve_schema(_lp_base(param_version="9.9.9"))

    def test_missing_schema_version_request_mismatch(self):
        # requesting a schema_version not matching resolved mapping fails closed
        with pytest.raises(MissingSchemaVersionError):
            resolve_schema(_lp_base(), schema_version="999")

    def test_ambiguous_family_detection(self):
        # registry has no ambiguity by default; simulate ambiguity guard by duplicate key check
        from scanline.config_registry import register_schema, SchemaEntry
        from scanline.config_load import _ensure_default_registry
        _ensure_default_registry()
        entry = _REGISTRY[("level_proximity", "1.0.0")]
        # same entry re-register ok
        register_schema(entry)
        # conflicting entry should raise
        bad = SchemaEntry(**{**entry.__dict__, "config_schema_version": "2"})
        with pytest.raises(AmbiguousConfigFamilyError):
            register_schema(bad)

    def test_unknown_configuration_field(self, tmp_path):
        p = _write(tmp_path / "p.json", _lp_base(extra="nope"))
        with pytest.raises(UnknownFieldError):
            load_config(p)

    def test_invalid_numeric_type(self, tmp_path):
        p = _write(tmp_path / "p.json", _lp_base(atr_window="14"))
        with pytest.raises((InvalidFieldTypeError, ConfigLoadError)):
            load_config(p)

    def test_unsupported_legacy_form(self, tmp_path):
        p = _write(tmp_path / "p.json", _lp_base(proximity_bands_atr=[0.5, 0.5]))
        with pytest.raises(UnsupportedLegacyFormError):
            load_config(p)


@pytest.fixture(autouse=True)
def _restore_registry():
    from scanline.config_load import _ensure_default_registry
    _ensure_default_registry()
    snap = dict(_REGISTRY)
    yield
    _REGISTRY.clear()
    _REGISTRY.update(snap)


class TestLoadConfig:
    def test_single_read_raw_hash_effective_hash(self, tmp_path, monkeypatch):
        p = _write(tmp_path / "p.json", _lp_base())
        raw = p.read_bytes()
        reads = {"n": 0}
        real = Path.read_bytes

        def counting(self):
            if self == p:
                reads["n"] += 1
            return real(self)

        monkeypatch.setattr(Path, "read_bytes", counting)
        lc = load_config(p)
        assert reads["n"] == 1
        assert lc.param_sha256 == hashlib.sha256(raw).hexdigest()
        assert lc.config_hash == hashlib.sha256(lc.effective_snapshot_bytes).hexdigest()
        assert lc.raw_snapshot_bytes == raw

    def test_repeated_loads_identical(self, tmp_path):
        p = _write(tmp_path / "p.json", _lp_base())
        a = load_config(p)
        b = load_config(p)
        assert a.effective_config == b.effective_config
        assert a.effective_snapshot_bytes == b.effective_snapshot_bytes
        assert a.config_hash == b.config_hash
        assert a.runtime_config == b.runtime_config

    def test_effective_and_runtime_agree(self, tmp_path):
        p = _write(tmp_path / "p.json", _lp_base(grid_steps={"GOLD": 25, "EURUSD": 0.0050}))
        lc = load_config(p)
        assert lc.runtime_config["grid_steps"]["GOLD"] == 25
        assert isinstance(lc.runtime_config["grid_steps"]["GOLD"], int)
        assert lc.runtime_config["grid_steps"]["EURUSD"] == 0.005
        assert isinstance(lc.runtime_config["grid_steps"]["EURUSD"], float)
        assert lc.effective_config["grid_steps"]["GOLD"] == {"numeric_type": "integer", "value": 25}
        assert lc.effective_config["grid_steps"]["EURUSD"]["numeric_type"] == "binary64"

    def test_hash_subject_excludes_metadata(self, tmp_path):
        p = _write(tmp_path / "p.json", _lp_base())
        lc = load_config(p)
        eff = json.loads(lc.effective_snapshot_bytes)
        for k in ["config_hash", "config_hash_algorithm", "config_canonicalization_version",
                  "config_hash_subject", "param_sha256", "raw_snapshot_bytes", "effective_snapshot_bytes"]:
            assert k not in eff


class TestLevelProximityNormalization:
    def test_module_alias_normalization(self, tmp_path):
        p = _write(tmp_path / "p.json", _lp_base(module="module_1"))
        lc = load_config(p)
        assert lc.module == "level_proximity"
        assert lc.effective_config["module"] == "level_proximity"

    def test_defaults_and_legacy_band_normalization(self, tmp_path):
        p = _write(tmp_path / "p.json", _lp_base(proximity_bands_atr=[0.5]))
        lc = load_config(p)
        bands = lc.effective_config["proximity_bands_atr"]
        assert bands["structural"]["numeric_type"] == "binary64"
        assert bands["grid"]["numeric_type"] == "binary64"
        assert lc.runtime_config["proximity_bands_atr"] == {"structural": 0.5, "grid": 0.5}

    def test_integer_vs_binary64_grid_steps(self, tmp_path):
        p = _write(tmp_path / "p.json", _lp_base(grid_steps={"GOLD": 5, "SILVER": 5.0}))
        lc = load_config(p)
        assert lc.effective_config["grid_steps"]["GOLD"] == {"numeric_type": "integer", "value": 5}
        assert lc.effective_config["grid_steps"]["SILVER"]["numeric_type"] == "binary64"
        assert lc.effective_config["grid_steps"]["SILVER"]["value"] == "5.0"
        assert isinstance(lc.runtime_config["grid_steps"]["GOLD"], int)
        assert isinstance(lc.runtime_config["grid_steps"]["SILVER"], float)
        # hashes differ for int vs float
        p2 = _write(tmp_path / "p2.json", _lp_base(grid_steps={"GOLD": 5}))
        p3 = _write(tmp_path / "p3.json", _lp_base(grid_steps={"GOLD": 5.0}))
        assert load_config(p2).config_hash != load_config(p3).config_hash

    def test_runtime_native_types(self, tmp_path):
        p = _write(tmp_path / "p.json", _lp_base(grid_steps={"GOLD": 1, "EURUSD": 0.01}))
        lc = load_config(p)
        assert type(lc.runtime_config["grid_steps"]["GOLD"]) is int
        assert type(lc.runtime_config["grid_steps"]["EURUSD"]) is float

    def test_detection_behaviour_preserved(self, tmp_path):
        # integer step 5 emits integer level_price, float step 5.0 emits float level_price
        from scanline.levels import compute_events
        d1 = [{"symbol":"GOLD","timeframe":"D1","open_ts":"2026-01-01T00:00:00Z","open":100,"high":110,"low":90,"close":100}]
        em = []
        for i in range(20):
            ts = f"2026-01-01T{i:02d}:00:00Z"
            em.append({"symbol":"GOLD","timeframe":"H1","open_ts":ts,"open":100,"high":101,"low":99,"close":100})
        params_int = {
            "atr_window":14,"atr_basis":"closed_bars_only","proximity_bands_atr":{"structural":0.5,"grid":0.5},
            "atr_excludes_emission_bar":True,"crossing_semantics":"close_distance_band_entry","band_edge":"inclusive",
            "gap_through":"fires_if_landing_inside","state_key":"level_type+level_price+defined_at","gap_semantics":"array_previous",
            "frozen_at":"2026-01-01T00:00:00Z","param_version":"1.0.0","grid_steps":{"GOLD":5}
        }
        params_float = dict(params_int)
        params_float["grid_steps"] = {"GOLD": 5.0}
        ev_i = compute_events(d1, em, params_int)
        ev_f = compute_events(d1, em, params_float)
        # events may be empty depending on inputs; but grid level prices in internal generation preserve type.
        # Directly inspect generated grid levels via helper behavior by checking no crash and type-sensitive formatting.
        from scanline.levels import _grid_levels
        li = _grid_levels("GOLD", {"GOLD": 5}, [90.0,110.0], "2026-01-01T00:00:00Z")
        lf = _grid_levels("GOLD", {"GOLD": 5.0}, [90.0,110.0], "2026-01-01T00:00:00Z")
        assert any(isinstance(l.price, int) for l in li)
        assert all(isinstance(l.price, float) for l in lf)


class TestSessionNormalization:
    def test_aliases_container_and_defaults(self, tmp_path):
        obj = {
            "module": "session_anomalies",
            "param_version": "1.0.0",
            "frozen_at": "2026-01-01T00:00:00Z",
            "cluster_schedule": [{"symbol": "GOLD", "weekday_expected_bars": 24, "tz": "UTC"}],
        }
        p = _write(tmp_path / "s.json", obj)
        lc = load_config(p)
        gold = lc.effective_config["symbols"]["GOLD"]
        assert gold["expected_bars"] == 24
        assert gold["expected_sun_bars"] == 0
        assert gold["stub_tolerance"] == 1
        assert gold["sun_tolerance"] == 0
        assert gold["maintenance"]["mode"] == "local"
        assert gold["maintenance"]["start_hhmm"] == "17:00"

    def test_fixed_utc_maintenance(self, tmp_path):
        obj = _session_base()
        obj["clusters"]["GOLD"]["maintenance_utc_start"] = "17:00"
        obj["clusters"]["GOLD"]["maintenance_utc_end"] = "18:00"
        p = _write(tmp_path / "s.json", obj)
        lc = load_config(p)
        m = lc.effective_config["symbols"]["GOLD"]["maintenance"]
        assert m == {"mode": "fixed_utc", "start_hhmm": "17:00", "end_hhmm": "18:00"}

    def test_local_vs_fixed_utc_hash_distinct(self, tmp_path):
        local = _session_base()
        fixed = _session_base()
        fixed["clusters"]["GOLD"]["maintenance_utc_start"] = "17:00"
        fixed["clusters"]["GOLD"]["maintenance_utc_end"] = "18:00"
        p1 = _write(tmp_path / "l.json", local)
        p2 = _write(tmp_path / "f.json", fixed)
        assert load_config(p1).config_hash != load_config(p2).config_hash

    def test_conflicting_aliases_fail(self, tmp_path):
        obj = _session_base()
        obj["clusters"]["GOLD"]["expected_bars"] = 24
        obj["clusters"]["GOLD"]["weekday_expected_bars"] = 23
        p = _write(tmp_path / "s.json", obj)
        with pytest.raises(ConfigLoadError):
            load_config(p)

    def test_missing_symbol_scope_fail_closed(self, tmp_path):
        obj = {
            "module": "session_anomalies",
            "param_version": "1.0.0",
            "frozen_at": "2026-01-01T00:00:00Z",
            "expected_bars": 24,
        }
        p = _write(tmp_path / "s.json", obj)
        with pytest.raises(ConfigLoadError):
            load_config(p)

    def test_invalid_timezone_fail(self, tmp_path):
        obj = _session_base()
        obj["clusters"]["GOLD"]["zone"] = "Not/AZone"
        p = _write(tmp_path / "s.json", obj)
        with pytest.raises(ConfigLoadError):
            load_config(p)

    def test_ambiguous_maintenance_mode_fail_closed(self, tmp_path):
        obj = _session_base()
        obj["clusters"]["GOLD"]["maintenance_local_start"] = "17:00"
        obj["clusters"]["GOLD"]["maintenance_utc_start"] = "17:00"
        p = _write(tmp_path / "s.json", obj)
        with pytest.raises(ConfigLoadError):
            load_config(p)


class TestRegression:
    def test_new_scan_manifest_v110_with_provenance(self, tmp_path):
        from tests.test_scan import _make_corpus, _params_path
        corpus = _make_corpus(tmp_path)
        param_path = _params_path(tmp_path)
        out = tmp_path / "out"
        scan_id = run_scan(corpus, out, param_path=param_path)
        dest = out / scan_id
        manifest = json.loads((dest / "scanner_data_manifest.json").read_text())
        assert manifest["manifest_version"] == "1.1.0"
        assert manifest["config_hash_algorithm"] == "sha256"
        assert manifest["config_canonicalization_version"] == "SCANLINE-config-canon-v1"
        assert manifest["config_hash_subject"] == "effective_validated_config"
        assert isinstance(manifest["config_schema_version"], str) and manifest["config_schema_version"]
        assert manifest["config_snapshot_raw"] == "param_snapshot.raw.json"
        assert manifest["config_snapshot_effective"] == "param_snapshot.effective.json"
        names = [o["name"] for o in manifest["outputs"]]
        assert "param_snapshot.raw.json" in names
        assert "param_snapshot.effective.json" in names
        assert is_scan_complete(dest) is True

    def test_historical_records_readable(self):
        for p in (ROOT / "records" / "scans").glob("*/scanner_data_manifest.json"):
            obj = json.loads(p.read_text())
            assert isinstance(obj, dict)
            # Pre-SCAN-018A manifests may be legacy-readable without status; they must remain parseable.
            assert "manifest_version" in obj or "scan_id" in obj or "param_sha256" in obj
