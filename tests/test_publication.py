"""Tests for SCAN-018 publication manifest generation and schema descriptor pinning."""
import json
from pathlib import Path

import pytest

from scanline import publication
from scanline import schema


def _write_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj) + "\n")


def _make_fixture_scan(tmp_path: Path, *, events_obj=None, extra_files=None):
    scan_dir = tmp_path / "scanX"
    scan_dir.mkdir()
    if events_obj is None:
        events_obj = {
            "header": {
                "module": "module_1",
                "param_version": "9.9.9",
                "param_sha256": "a" * 64,
                "param_file": "p.json",
                "scan_mode": "retrospective",
                "evidence_tier": "retrospective_membership",
                "batch_start_ts": "2026-01-01T00:00:00Z",
                "batch_end_ts": "2026-01-31T00:00:00Z",
                "universe": ["AAA", "BBB"],
                "emission_timeframes": ["H1", "H4"],
                "definition_timeframe": "D1",
            },
            "events": [{"symbol": "AAA"}],
        }
    (scan_dir / "events.json").write_text(json.dumps(events_obj) + "\n")
    if extra_files:
        for name, content in extra_files.items():
            (scan_dir / name).write_text(content)
    return scan_dir


def _write_ledger(tmp_path: Path, batch_sha256: str):
    ledger = tmp_path / "ledger.jsonl"
    # minimal confirmatory line with matching batch_sha256
    line = {
        "batch_sha256": batch_sha256,
        "outcome": "inside pre-registration",
        "params_version": "9.9.9",
        "window": {"start": "2026-01-01", "end": "2026-01-31"},
        "code_commit": "deadbeef",
        "module": "module_1",
    }
    ledger.write_text(json.dumps(line) + "\n")
    return ledger


def test_publication_manifest_matches_hash(tmp_path):
    events_obj = {
        "header": {
            "module": "module_1",
            "param_version": "9.9.9",
            "param_sha256": "b" * 64,
            "param_file": "scanner_params.level_proximity-9.9.9.json",
            "scan_mode": "retrospective",
            "evidence_tier": "retrospective_membership",
            "batch_start_ts": "2026-01-01T00:00:00Z",
            "batch_end_ts": "2026-01-31T00:00:00Z",
            "universe": ["AAA", "BBB", "CCC"],
        },
        "events": [{"symbol": "AAA"}, {"symbol": "BBB"}],
    }
    scan_dir = _make_fixture_scan(tmp_path, events_obj=events_obj, extra_files={"scanner_data_manifest.json": "{}\n"})
    # compute events sha
    events_sha = publication._sha256_file(scan_dir / "events.json")
    ledger = _write_ledger(tmp_path, events_sha)

    manifest = publication.build_publication_manifest(scan_dir, ledger)
    assert manifest["manifest_version"] == "1.0.0-publication"
    assert manifest["scan_id"] == "scanX"
    assert manifest["status"] == "COMPLETE"
    assert manifest["event_count"] == 2
    assert manifest["header_summary"]["canonical_module"] == "level_proximity"
    assert manifest["header_summary"]["emitted_module"] == "module_1"
    assert manifest["header_summary"]["universe_size"] == 3
    # outputs contains events.json and manifest
    names = sorted([o["name"] for o in manifest["outputs"]])
    assert "events.json" in names
    assert "scanner_data_manifest.json" in names
    # hashes match fresh measurement
    for o in manifest["outputs"]:
        p = scan_dir / o["name"]
        assert o["sha256"] == publication._sha256_file(p)
        assert o["size"] == publication._size_file(p)


def test_publication_manifest_hash_mismatch_refuses(tmp_path):
    events_obj = {"header": {"module": "module_1"}, "events": []}
    scan_dir = _make_fixture_scan(tmp_path, events_obj=events_obj)
    ledger = _write_ledger(tmp_path, "0" * 64)  # wrong hash
    with pytest.raises(ValueError):
        publication.build_publication_manifest(scan_dir, ledger)


def test_batch_schema_descriptor_matches_code():
    root = Path(__file__).resolve().parents[1]
    desc_path = root / "records" / "schemas" / "level_proximity.batch.json"
    assert desc_path.exists()
    desc = json.loads(desc_path.read_text())
    # header fields equal code
    assert set(desc["header_fields_closed"]) == set(schema.BATCH_HEADER_FIELDS)
    assert set(desc["event_fields_closed"]) == set(schema.EVENT_FIELDS)
    assert set(desc["level_type_enum"]) == set(schema.LEVEL_TYPES)
    assert set(desc["emission_timeframes"]) == set(schema.EMISSION_TIMEFRAMES)
    assert desc["atr_basis"] == schema.ATR_BASIS
    assert desc["definition_timeframe"] == schema.DEFINITION_TIMEFRAME
    assert desc["canonical_module_name"] == "level_proximity"
    assert desc["emitted_module_alias"] == "module_1"


def test_session_anomalies_batch_schema_descriptor_matches_code():
    root = Path(__file__).resolve().parents[1]
    desc_path = root / "records" / "schemas" / "session_anomalies.batch.json"
    assert desc_path.exists()
    desc = json.loads(desc_path.read_text())
    assert set(desc["header_fields_closed"]) == set(schema.BATCH_HEADER_FIELDS)
    assert set(desc["event_fields_closed"]) == set(schema.SESSION_EVENT_FIELDS)
    assert set(desc["anomaly_type_enum"]) == set(schema.ANOMALY_TYPES)
    assert set(desc["emission_timeframes"]) == set(schema.SESSION_EMISSION_TIMEFRAMES)
    assert desc["canonical_module_name"] == "session_anomalies"
