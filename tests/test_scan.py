"""Hermetic end-to-end test for the scan driver (SCAN-006) plus
SCAN-018A scan identity and atomic persistence regression tests.

All persistence tests use ``tmp_path``; no historical records are touched.
Failure injection is controlled via monkeypatching; failures never damage
historical records.
"""

import calendar
import csv
import hashlib
import itertools
import json
import os
import re
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

import pytest

import scanline.scan as scan_mod
from scanline.scan import generate_scan_id, is_scan_complete, run_scan
from scanline.validator import validate_batch

ROOT = Path(__file__).resolve().parents[1]
PARAMS_PATH = ROOT / "config" / "scanner_params.level_proximity.json"

UNIVERSE = ["GOLD", "EURUSD", "USDCAD", "GER40", "USOIL"]

SCAN_ID_RE = re.compile(r"\d{8}T\d{6}\d{6}Z_[0-9a-f]{32}")


def _ts(dt):
    return calendar.timegm(dt.timetuple())


def _write_csv(path, rows):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["time", "open", "high", "low", "close", "volume"])
        for r in rows:
            w.writerow([r[0], r[1], r[2], r[3], r[4], 1.0])


def _make_corpus(root, symbols=None):
    symbols = symbols or UNIVERSE
    corpus = root / "corpus"
    corpus.mkdir()
    start = datetime(2026, 9, 7, tzinfo=timezone.utc)
    end = datetime(2026, 9, 24, tzinfo=timezone.utc)
    transition = datetime(2026, 9, 22, tzinfo=timezone.utc)
    for sym in symbols:
        rows = []
        d = start
        while d < end:
            rows.append((_ts(d), 95.0, 100.0, 90.0, 95.0))
            d += timedelta(days=1)
        _write_csv(corpus / f"{sym}_D1.csv", rows)
        for tf, step in (("H1", timedelta(hours=1)), ("H4", timedelta(hours=4))):
            rows = []
            t = start
            while t < end:
                close = 99.8 if t >= transition else 108.0
                rows.append((_ts(t), close, close + 0.5, close - 0.5, close))
                t += step
            _write_csv(corpus / f"{sym}_{tf}.csv", rows)
    return corpus


def _params_path(tmp_path):
    pdata = json.loads(PARAMS_PATH.read_text())
    pdata["frozen_at"] = "2026-09-01T00:00:00Z"
    param_path = tmp_path / "params.json"
    param_path.write_text(json.dumps(pdata))
    return param_path


# ---------------------------------------------------------------------------
# Existing end-to-end contract: byte-identical events, now also scan IDs.
# ---------------------------------------------------------------------------

def test_scan_driver_end_to_end(tmp_path):
    corpus = _make_corpus(tmp_path)
    param_path = _params_path(tmp_path)
    params_bytes = param_path.read_bytes()

    out1 = tmp_path / "out1"
    out2 = tmp_path / "out2"
    scan_id1 = run_scan(corpus, out1, param_path=param_path)
    scan_id2 = run_scan(corpus, out2, param_path=param_path)

    assert SCAN_ID_RE.fullmatch(scan_id1)
    assert SCAN_ID_RE.fullmatch(scan_id2)
    assert scan_id1 != scan_id2

    b1 = (out1 / scan_id1 / "events.json").read_bytes()
    b2 = (out2 / scan_id2 / "events.json").read_bytes()
    assert b1 == b2

    data = json.loads(b1)
    result = validate_batch(data["events"], data["header"], params_bytes)
    assert result["valid"] is True
    assert result["violations"] == []

    m1 = json.loads((out1 / scan_id1 / "scanner_data_manifest.json").read_text())
    assert m1["scan_id"] == scan_id1
    assert m1["status"] == "COMPLETE"
    assert is_scan_complete(out1 / scan_id1) is True


# ---------------------------------------------------------------------------
# SCAN-018A regression tests (isolated, tmp_path).
# ---------------------------------------------------------------------------

def test_01_successful_scan_publication(tmp_path):
    corpus = _make_corpus(tmp_path)
    param_path = _params_path(tmp_path)
    root = tmp_path / "scans"
    scan_id = run_scan(corpus, root, param_path=param_path)
    dest = root / scan_id
    assert dest.is_dir()
    events_path = dest / "events.json"
    manifest_path = dest / "scanner_data_manifest.json"
    assert events_path.is_file()
    assert manifest_path.is_file()
    manifest = json.loads(manifest_path.read_text())
    assert manifest["scan_id"] == scan_id
    assert manifest["status"] == "COMPLETE"
    assert manifest["outputs"][0]["name"] == "events.json"
    assert is_scan_complete(dest) is True
    data = json.loads(events_path.read_text())
    assert "events" in data and "header" in data


def test_02_event_serialization_failure(tmp_path):
    corpus = _make_corpus(tmp_path)
    param_path = _params_path(tmp_path)
    root = tmp_path / "scans"
    fixed_id = "20260101T000000000000Z_" + "0" * 32
    with mock.patch.object(scan_mod, "generate_scan_id", return_value=fixed_id), \
            mock.patch.object(scan_mod, "_serialize_json",
                              side_effect=TypeError("injected event serialization failure")):
        with pytest.raises(TypeError, match="injected event serialization failure"):
            run_scan(corpus, root, param_path=param_path)
    dest = root / fixed_id
    assert dest.is_dir()
    assert not (dest / "events.json").exists()
    assert not (dest / "scanner_data_manifest.json").exists()
    assert is_scan_complete(dest) is False


def test_03_manifest_serialization_failure(tmp_path):
    corpus = _make_corpus(tmp_path)
    param_path = _params_path(tmp_path)
    root = tmp_path / "scans"
    fixed_id = "20260101T000000000000Z_" + "1" * 32
    real_serialize = scan_mod._serialize_json
    calls = {"n": 0}

    def fake_serialize(obj):
        calls["n"] += 1
        if calls["n"] == 2:
            raise TypeError("injected manifest serialization failure")
        return real_serialize(obj)

    with mock.patch.object(scan_mod, "generate_scan_id", return_value=fixed_id), \
            mock.patch.object(scan_mod, "_serialize_json", fake_serialize):
        with pytest.raises(TypeError, match="injected manifest serialization failure"):
            run_scan(corpus, root, param_path=param_path)
    dest = root / fixed_id
    assert (dest / "events.json").is_file()
    assert not (dest / "scanner_data_manifest.json").exists()
    assert is_scan_complete(dest) is False


def test_04_event_file_replacement_failure(tmp_path):
    corpus = _make_corpus(tmp_path)
    param_path = _params_path(tmp_path)
    root = tmp_path / "scans"
    fixed_id = "20260101T000000000000Z_" + "2" * 32
    real_replace = os.replace

    def fake_replace(src, dst):
        if Path(dst).name == "events.json":
            raise OSError("injected event replace failure")
        return real_replace(src, dst)

    with mock.patch.object(scan_mod, "generate_scan_id", return_value=fixed_id), \
            mock.patch.object(scan_mod.os, "replace", fake_replace):
        with pytest.raises(OSError, match="injected event replace failure"):
            run_scan(corpus, root, param_path=param_path)
    dest = root / fixed_id
    assert not (dest / "events.json").exists()
    assert not (dest / "scanner_data_manifest.json").exists()
    temps = [p for p in dest.iterdir() if ".tmp." in p.name]
    assert len(temps) >= 1
    assert is_scan_complete(dest) is False


def test_05_manifest_replacement_failure(tmp_path):
    corpus = _make_corpus(tmp_path)
    param_path = _params_path(tmp_path)
    root = tmp_path / "scans"
    fixed_id = "20260101T000000000000Z_" + "3" * 32
    real_replace = os.replace

    def fake_replace(src, dst):
        if Path(dst).name == "scanner_data_manifest.json":
            raise OSError("injected manifest replace failure")
        return real_replace(src, dst)

    with mock.patch.object(scan_mod, "generate_scan_id", return_value=fixed_id), \
            mock.patch.object(scan_mod.os, "replace", fake_replace):
        with pytest.raises(OSError, match="injected manifest replace failure"):
            run_scan(corpus, root, param_path=param_path)
    dest = root / fixed_id
    assert (dest / "events.json").is_file()
    assert not (dest / "scanner_data_manifest.json").exists()
    assert is_scan_complete(dest) is False


def test_06_existing_destination_collision(tmp_path):
    corpus = _make_corpus(tmp_path)
    param_path = _params_path(tmp_path)
    root = tmp_path / "scans"
    fixed_id = "20260101T000000000000Z_" + "4" * 32
    dest = root / fixed_id
    dest.mkdir(parents=True)
    (dest / "events.json").write_text("{\"events\": [], \"header\": {}}\n")
    manifest_payload = {"scan_id": fixed_id, "status": "COMPLETE", "outputs": []}
    (dest / "scanner_data_manifest.json").write_text(json.dumps(manifest_payload) + "\n")
    events_before = (dest / "events.json").read_bytes()
    manifest_before = (dest / "scanner_data_manifest.json").read_bytes()
    with mock.patch.object(scan_mod, "generate_scan_id", return_value=fixed_id):
        with pytest.raises(FileExistsError):
            run_scan(corpus, root, param_path=param_path)
    assert (dest / "events.json").read_bytes() == events_before
    assert (dest / "scanner_data_manifest.json").read_bytes() == manifest_before


def test_07_incomplete_destination_remains_untouched(tmp_path):
    corpus = _make_corpus(tmp_path)
    param_path = _params_path(tmp_path)
    root = tmp_path / "scans"
    fixed_id = "20260101T000000000000Z_" + "5" * 32
    dest = root / fixed_id
    dest.mkdir(parents=True)
    (dest / "events.json").write_text("{\"events\": [], \"header\": {}}\n")
    events_before = (dest / "events.json").read_bytes()
    with mock.patch.object(scan_mod, "generate_scan_id", return_value=fixed_id):
        with pytest.raises(FileExistsError):
            run_scan(corpus, root, param_path=param_path)
    assert (dest / "events.json").read_bytes() == events_before
    assert not (dest / "scanner_data_manifest.json").exists()
    assert is_scan_complete(dest) is False


def test_08_temporary_files_not_mistaken_for_output(tmp_path):
    root = tmp_path / "scans"
    fixed_id = "20260101T000000000000Z_" + "6" * 32
    dest = root / fixed_id
    dest.mkdir(parents=True)
    # Only orphaned temp files; no events.json, no manifest.
    (dest / "events.json.tmp.1234").write_bytes(b"partial")
    (dest / "scanner_data_manifest.json.tmp.1234").write_bytes(b"partial")
    assert not (dest / "events.json").exists()
    assert not (dest / "scanner_data_manifest.json").exists()
    assert is_scan_complete(dest) is False
    # A successful scan to a different ID coexists; orphans are untouched.
    corpus = _make_corpus(tmp_path)
    param_path = _params_path(tmp_path)
    other_id = run_scan(corpus, root, param_path=param_path)
    assert (root / other_id).is_dir()
    assert (dest / "events.json.tmp.1234").exists()
    assert is_scan_complete(root / other_id) is True


def test_09_concurrent_attempts_same_scan_id(tmp_path):
    corpus = _make_corpus(tmp_path)
    param_path = _params_path(tmp_path)
    root = tmp_path / "scans"
    fixed_id = "20260101T000000000000Z_" + "7" * 32
    results = []

    def worker():
        try:
            scan_id = run_scan(corpus, root, param_path=param_path)
            results.append(("ok", scan_id))
        except Exception as exc:  # noqa: BLE001
            results.append(("error", type(exc).__name__, str(exc)))

    with mock.patch.object(scan_mod, "generate_scan_id", return_value=fixed_id):
        t1 = threading.Thread(target=worker)
        t2 = threading.Thread(target=worker)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

    assert len(results) == 2
    ok = [r for r in results if r[0] == "ok"]
    err = [r for r in results if r[0] == "error"]
    assert len(ok) == 1
    assert len(err) == 1
    assert err[0][1] == "FileExistsError"
    dest = root / fixed_id
    assert dest.is_dir()
    assert is_scan_complete(dest) is True
    assert (dest / "events.json").is_file()


def test_10_repeated_identical_scans_different_ids_byte_identical_events(tmp_path):
    corpus = _make_corpus(tmp_path)
    param_path = _params_path(tmp_path)
    root = tmp_path / "scans"
    id1 = run_scan(corpus, root, param_path=param_path)
    id2 = run_scan(corpus, root, param_path=param_path)
    assert SCAN_ID_RE.fullmatch(id1)
    assert SCAN_ID_RE.fullmatch(id2)
    assert id1 != id2
    assert (root / id1).is_dir() and (root / id2).is_dir()
    b1 = (root / id1 / "events.json").read_bytes()
    b2 = (root / id2 / "events.json").read_bytes()
    assert b1 == b2


def test_11_manifest_output_hash_and_size_match_event_file(tmp_path):
    corpus = _make_corpus(tmp_path)
    param_path = _params_path(tmp_path)
    root = tmp_path / "scans"
    scan_id = run_scan(corpus, root, param_path=param_path)
    dest = root / scan_id
    events_path = dest / "events.json"
    manifest = json.loads((dest / "scanner_data_manifest.json").read_text())
    assert manifest["scan_id"] == scan_id
    assert manifest["status"] == "COMPLETE"
    outputs = manifest["outputs"]
    assert len(outputs) >= 1
    ev = outputs[0]
    assert ev["name"] == "events.json"
    assert ev["sha256"] == hashlib.sha256(events_path.read_bytes()).hexdigest()
    assert ev["size_bytes"] == events_path.stat().st_size
    assert is_scan_complete(dest) is True


def test_12_no_complete_manifest_means_incomplete(tmp_path):
    root = tmp_path / "scans"
    dest = root / "some_id"
    dest.mkdir(parents=True)
    assert is_scan_complete(dest) is False
    (dest / "events.json").write_bytes(b'{"events": [], "header": {}}\n')
    assert is_scan_complete(dest) is False
    (dest / "scanner_data_manifest.json").write_text(
        json.dumps({"scan_id": "some_id", "status": "RUNNING", "outputs": []}) + "\n"
    )
    assert is_scan_complete(dest) is False
    (dest / "scanner_data_manifest.json").write_text(
        json.dumps({
            "scan_id": "some_id",
            "status": "COMPLETE",
            "outputs": [{"name": "events.json", "sha256": "deadbeef", "size_bytes": 123}],
        }) + "\n"
    )
    assert is_scan_complete(dest) is False
    corpus = _make_corpus(tmp_path)
    param_path = _params_path(tmp_path)
    scan_id = run_scan(corpus, root, param_path=param_path)
    assert is_scan_complete(root / scan_id) is True


# ---------------------------------------------------------------------------
# SCAN-018A-R1 manifest verification hardening (isolated, tmp_path).
# Every test builds its own manifest and directory; nothing historical is
# touched and is_scan_complete() is exercised read-only.
# ---------------------------------------------------------------------------

_FIXED_ID = "20260101T000000000000Z_" + "0" * 32
_OTHER_ID = "20260101T000000000000Z_" + "1" * 32


def _make_scan_dir(tmp_path, name=_FIXED_ID):
    dest = tmp_path / "scans" / name
    dest.mkdir(parents=True)
    return dest


def _events_entry(content=b'{"events": [], "header": {}}\n'):
    return {
        "name": "events.json",
        "sha256": hashlib.sha256(content).hexdigest(),
        "size_bytes": len(content),
    }


def _write_manifest(dest, scan_id=None, status="COMPLETE", outputs=None, **extra):
    scan_id = scan_id or dest.name
    manifest = {"scan_id": scan_id, "status": status, "outputs": list(outputs or [])}
    manifest.update(extra)
    (dest / "scanner_data_manifest.json").write_text(json.dumps(manifest) + "\n")


def test_13_absolute_posix_output_rejected(tmp_path):
    dest = _make_scan_dir(tmp_path)
    (dest / "events.json").write_bytes(b'{"events": [], "header": {}}\n')
    entry = _events_entry()
    entry["name"] = "/etc/passwd"
    _write_manifest(dest, outputs=[entry])
    assert is_scan_complete(dest) is False


def test_14_windows_absolute_output_rejected(tmp_path):
    dest = _make_scan_dir(tmp_path)
    (dest / "events.json").write_bytes(b'{"events": [], "header": {}}\n')
    entry = _events_entry()
    entry["name"] = "C:\\Windows\\Temp\\events.json"
    _write_manifest(dest, outputs=[entry])
    assert is_scan_complete(dest) is False


def test_15_relative_parent_traversal_rejected(tmp_path):
    dest = _make_scan_dir(tmp_path)
    (dest / "events.json").write_bytes(b'{"events": [], "header": {}}\n')
    entry = _events_entry()
    entry["name"] = "../events.json"
    _write_manifest(dest, outputs=[entry])
    assert is_scan_complete(dest) is False


def test_16_symlink_escaping_scan_directory_rejected(tmp_path):
    dest = _make_scan_dir(tmp_path)
    external = tmp_path / "external.txt"
    external.write_bytes(b"outside data")
    (dest / "events.json").symlink_to(external)
    entry = {
        "name": "events.json",
        "sha256": hashlib.sha256(b"outside data").hexdigest(),
        "size_bytes": len(b"outside data"),
    }
    _write_manifest(dest, outputs=[entry])
    assert is_scan_complete(dest) is False


def test_17_symlink_pointing_to_internal_file_accepted(tmp_path):
    dest = _make_scan_dir(tmp_path)
    data = b'{"events": [], "header": {}}\n'
    (dest / "events.json").write_bytes(data)
    (dest / "alias.json").symlink_to("events.json")
    entry = _events_entry(data)
    alias = dict(entry, name="alias.json")
    _write_manifest(dest, outputs=[entry, alias])
    assert is_scan_complete(dest) is True


def test_18_manifest_scan_id_mismatch(tmp_path):
    dest = _make_scan_dir(tmp_path)
    (dest / "events.json").write_bytes(b'{"events": [], "header": {}}\n')
    _write_manifest(dest, scan_id=_OTHER_ID, outputs=[_events_entry()])
    assert is_scan_complete(dest) is False


def test_19_missing_scan_id(tmp_path):
    dest = _make_scan_dir(tmp_path)
    (dest / "events.json").write_bytes(b'{"events": [], "header": {}}\n')
    _write_manifest(dest, scan_id=None)
    manifest = json.loads((dest / "scanner_data_manifest.json").read_text())
    del manifest["scan_id"]
    (dest / "scanner_data_manifest.json").write_text(json.dumps(manifest) + "\n")
    assert is_scan_complete(dest) is False


def test_20_invalid_scan_id(tmp_path):
    dest = _make_scan_dir(tmp_path)
    (dest / "events.json").write_bytes(b'{"events": [], "header": {}}\n')
    _write_manifest(dest, scan_id="not-a-valid-scan-id", outputs=[_events_entry()])
    assert is_scan_complete(dest) is False


def test_21_empty_outputs_list_rejected(tmp_path):
    dest = _make_scan_dir(tmp_path)
    (dest / "events.json").write_bytes(b'{"events": [], "header": {}}\n')
    _write_manifest(dest, outputs=[])
    assert is_scan_complete(dest) is False


def test_22_missing_events_json_entry_rejected(tmp_path):
    dest = _make_scan_dir(tmp_path)
    other = b'{"events": [], "header": {}}\n'
    (dest / "other.json").write_bytes(other)
    entry = {
        "name": "other.json",
        "sha256": hashlib.sha256(other).hexdigest(),
        "size_bytes": len(other),
    }
    _write_manifest(dest, outputs=[entry])
    assert is_scan_complete(dest) is False


def test_23_duplicate_output_entries_rejected(tmp_path):
    dest = _make_scan_dir(tmp_path)
    (dest / "events.json").write_bytes(b'{"events": [], "header": {}}\n')
    entry = _events_entry()
    _write_manifest(dest, outputs=[entry, dict(entry)])
    assert is_scan_complete(dest) is False


def test_24_malformed_sha256_rejected(tmp_path):
    dest = _make_scan_dir(tmp_path)
    (dest / "events.json").write_bytes(b'{"events": [], "header": {}}\n')
    entry = _events_entry()
    entry["sha256"] = "deadbeef"
    _write_manifest(dest, outputs=[entry])
    assert is_scan_complete(dest) is False


@pytest.mark.parametrize("size", [-1, "100", 3.5, True, None])
def test_25_invalid_size_fields_rejected(tmp_path, size):
    dest = _make_scan_dir(tmp_path)
    (dest / "events.json").write_bytes(b'{"events": [], "header": {}}\n')
    entry = _events_entry()
    entry["size_bytes"] = size
    _write_manifest(dest, outputs=[entry])
    assert is_scan_complete(dest) is False


def test_26_malformed_json_manifest_rejected(tmp_path):
    dest = _make_scan_dir(tmp_path)
    (dest / "events.json").write_bytes(b'{"events": [], "header": {}}\n')
    (dest / "scanner_data_manifest.json").write_text("{not valid json")
    assert is_scan_complete(dest) is False


def test_27_valid_existing_complete_manifest(tmp_path):
    dest = _make_scan_dir(tmp_path)
    data = b'{"events": [], "header": {}}\n'
    (dest / "events.json").write_bytes(data)
    _write_manifest(dest, outputs=[_events_entry(data)])
    assert is_scan_complete(dest) is True


def _dest_snapshot(dest):
    """Read-only snapshot of names, symlink targets, and file bytes."""
    snapshot = {}
    for entry in sorted(dest.iterdir(), key=lambda p: p.name):
        stat = entry.lstat()
        payload = {
            "mode": stat.st_mode,
            "mtime_ns": stat.st_mtime_ns,
            "size": stat.st_size,
        }
        if entry.is_symlink():
            payload["symlink_target"] = os.readlink(entry)
        elif entry.is_file():
            payload["bytes"] = entry.read_bytes()
        snapshot[entry.name] = payload
    return snapshot


def test_28_is_scan_complete_is_read_only(tmp_path):
    dest = _make_scan_dir(tmp_path)
    data = b'{"events": [], "header": {}}\n'
    (dest / "events.json").write_bytes(data)
    _write_manifest(dest, outputs=[_events_entry(data)])
    before = _dest_snapshot(dest)
    assert is_scan_complete(dest) is True
    assert is_scan_complete(dest) is True
    assert _dest_snapshot(dest) == before


# ---------------------------------------------------------------------------
# SCAN-018B versioned manifest contract tests (isolated, tmp_path).
# Every test builds its own scan directory; no historical records are touched
# and is_scan_complete() is exercised read-only.
# ---------------------------------------------------------------------------

_SCAN_018B_ID = "20261121T013740123456Z_abcdef0123456789abcdef0123456789"

_018b_dir_counter = itertools.count()


def _scan_018b_v100_dir(tmp_path, mutate=None, **extra):
    """Build a valid v1.0.0 scan directory: events.json + manifest.

    ``mutate`` receives the manifest dict before it is serialized, letting
    each test corrupt a single field. ``extra`` overrides manifest fields.
    A unique scan directory is created per call so parallel field loops do
    not collide on exclusive directory creation.
    """
    name = f"20261121T013740123456Z_{next(_018b_dir_counter):032x}"
    dest = tmp_path / "scans" / name
    dest.mkdir(parents=True)

    header = {
        "module": "level_proximity",
        "scan_mode": "forward",
        "param_version": "1.0.0",
        "frozen_at": "2026-11-19T03:25:04Z",
        "universe": ["GOLD", "EURUSD"],
        "emission_timeframes": ["H1", "H4"],
    }
    events = [{"event_ts": "2026-09-07T00:00:00Z", "symbol": "GOLD"}]
    batch = {"events": events, "header": header}
    events_bytes = scan_mod._serialize_json(batch)
    (dest / "events.json").write_bytes(events_bytes)
    events_sha256 = hashlib.sha256(events_bytes).hexdigest()
    events_size = len(events_bytes)

    base = "2026-11-21T01:37:40.123456Z"
    manifest = {
        "manifest_version": "1.0.0",
        "scan_id": name,
        "status": "COMPLETE",
        "scan_start": base,
        "outputs_complete_at": base,
        "execution_start": base,
        "module": "level_proximity",
        "scan_mode": "forward",
        "param_file": "scanner_params.level_proximity.json",
        "param_sha256": hashlib.sha256(b"{}").hexdigest(),
        "param_version": "1.0.0",
        "frozen_at": "2026-11-19T03:25:04Z",
        "universe": ["GOLD", "EURUSD"],
        "emission_timeframes": ["H1", "H4"],
        "series": [
            {
                "symbol": "GOLD",
                "timeframe": "D1",
                "file": "GOLD_D1.csv",
                "sha256": hashlib.sha256(b"dummy").hexdigest(),
                "size_bytes": 5,
                "bars_extracted": 1,
                "span": {"first_open_ts": None, "last_open_ts": None},
            }
        ],
        "total_bars_extracted": 1,
        "event_count": len(events),
        "validation_status": "valid",
        "validation_violation_count": 0,
        "evidence_tier": "forward_asof",
        "code_state": {"driver_sha256": hashlib.sha256(b"driver").hexdigest()},
        "outputs": [
            {"name": "events.json", "sha256": events_sha256, "size_bytes": events_size}
        ],
    }
    manifest.update(extra)
    if mutate:
        mutate(manifest)
    (dest / "scanner_data_manifest.json").write_text(json.dumps(manifest) + "\n")
    return dest


def test_scan_018b_complete_v100_manifest(tmp_path):
    dest = _scan_018b_v100_dir(tmp_path)
    assert is_scan_complete(dest) is True


def test_scan_018b_required_fields_missing(tmp_path):
    required = [
        "manifest_version", "scan_id", "status", "execution_start",
        "scan_start", "outputs_complete_at", "module", "scan_mode",
        "series", "param_file", "param_sha256", "param_version",
        "frozen_at", "universe", "emission_timeframes", "event_count",
        "validation_status", "evidence_tier", "code_state", "outputs",
    ]
    for field in required:
        dest = _scan_018b_v100_dir(tmp_path, mutate=lambda m, f=field: m.pop(f))
        assert is_scan_complete(dest) is False, f"missing {field} should be incomplete"


@pytest.mark.parametrize("field,corrupt", [
    ("event_count", "not-an-int"),
    ("event_count", True),
    ("event_count", -1),
    ("total_bars_extracted", True),
    ("validation_violation_count", "0"),
    ("size_bytes", "100"),
    ("outputs", "not-a-list"),
    ("module", ""),
    ("scan_mode", "bogus"),
    ("universe", []),
    ("emission_timeframes", ["H1", 2]),
    ("series", "not-a-list"),
    ("code_state", "not-a-dict"),
])
def test_scan_018b_invalid_field_types(tmp_path, field, corrupt):
    def mutate(m, f=field, c=corrupt):
        if f == "size_bytes":
            m["outputs"][0]["size_bytes"] = c
        else:
            m[f] = c
    dest = _scan_018b_v100_dir(tmp_path, mutate=mutate)
    assert is_scan_complete(dest) is False, f"{field}={corrupt!r} should be incomplete"


def test_scan_018b_invalid_schema_versions(tmp_path):
    for version in ["1.0", "1.0.0.0", "v1.0.0", "abc", "", 1.0, None]:
        dest = _scan_018b_v100_dir(tmp_path, mutate=lambda m, v=version: m.__setitem__("manifest_version", v))
        assert is_scan_complete(dest) is False, f"version {version!r} should be rejected"


def test_scan_018b_unknown_major_version_rejected(tmp_path):
    dest = _scan_018b_v100_dir(tmp_path, mutate=lambda m: m.__setitem__("manifest_version", "2.0.0"))
    assert is_scan_complete(dest) is False
    # Unknown major is unverifiable, not a failed scan: still False (incomplete).
    dest = _scan_018b_v100_dir(tmp_path, mutate=lambda m: m.__setitem__("manifest_version", "9.0.0"))
    assert is_scan_complete(dest) is False


def test_scan_018b_compatible_newer_minor_version(tmp_path):
    # Compatible v1.0.x minor/patch accepted when v1.0.0 required fields present.
    dest = _scan_018b_v100_dir(tmp_path, mutate=lambda m: m.__setitem__("manifest_version", "1.0.1"))
    assert is_scan_complete(dest) is True
    # v1.1.0 requires provenance fields and snapshots; a v1.0.0-shaped manifest must not pass.
    dest = _scan_018b_v100_dir(tmp_path, mutate=lambda m: m.__setitem__("manifest_version", "1.1.0"))
    assert is_scan_complete(dest) is False


def test_scan_018b_event_count_mismatch(tmp_path):
    dest = _scan_018b_v100_dir(tmp_path, mutate=lambda m: m.__setitem__("event_count", 999))
    assert is_scan_complete(dest) is False


def test_scan_018b_header_manifest_mismatch(tmp_path):
    for field in ["module", "scan_mode", "param_version", "frozen_at", "universe", "emission_timeframes"]:
        dest = _scan_018b_v100_dir(
            tmp_path,
            mutate=lambda m, f=field: m.__setitem__(f, "mismatched-value"),
        )
        assert is_scan_complete(dest) is False, f"{field} mismatch should be incomplete"


def test_scan_018b_validation_status_consistency(tmp_path):
    dest = _scan_018b_v100_dir(
        tmp_path,
        mutate=lambda m: m.__setitem__("validation_status", "invalid"),
    )
    assert is_scan_complete(dest) is False
    # A COMPLETE manifest must not report failed validation.
    dest = _scan_018b_v100_dir(
        tmp_path,
        mutate=lambda m: (m.__setitem__("validation_status", "valid"), m.__setitem__("status", "FAILED")),
    )
    assert is_scan_complete(dest) is False


def test_scan_018b_both_legacy_categories(tmp_path):
    # Category A — pre-SCAN-018A: no scan_id/status/outputs/manifest_version →
    # readable but not verifiable as complete.
    dest = _make_scan_dir(tmp_path)
    (dest / "events.json").write_bytes(b'{"events": [], "header": {}}\n')
    (dest / "scanner_data_manifest.json").write_text(
        json.dumps({"execution_start": "2026-01-01T00:00:00Z"}) + "\n"
    )
    assert is_scan_complete(dest) is False

    # Category B — SCAN-018A: scan_id, status COMPLETE, outputs, no
    # manifest_version → verified via the original SCAN-018A contract.
    dest = _make_scan_dir(tmp_path, name="20260101T000000000000Z_" + "9" * 32)
    data = b'{"events": [], "header": {}}\n'
    (dest / "events.json").write_bytes(data)
    _write_manifest(dest, outputs=[_events_entry(data)])  # no manifest_version
    assert is_scan_complete(dest) is True


def test_scan_018b_missing_scan_start(tmp_path):
    dest = _scan_018b_v100_dir(tmp_path, mutate=lambda m: m.pop("scan_start"))
    assert is_scan_complete(dest) is False


def test_scan_018b_missing_outputs_complete_at(tmp_path):
    dest = _scan_018b_v100_dir(tmp_path, mutate=lambda m: m.pop("outputs_complete_at"))
    assert is_scan_complete(dest) is False


def test_scan_018b_timestamp_ordering(tmp_path):
    # scan_start > outputs_complete_at → rejected.
    dest = _scan_018b_v100_dir(
        tmp_path,
        mutate=lambda m: m.__setitem__("scan_start", "2026-11-21T01:37:45Z"),
    )
    assert is_scan_complete(dest) is False
    # outputs_complete_at > execution_start → rejected.
    dest = _scan_018b_v100_dir(
        tmp_path,
        mutate=lambda m: m.__setitem__("outputs_complete_at", "2026-11-21T01:37:50Z"),
    )
    assert is_scan_complete(dest) is False
    # Equal timestamps (all captured at the same moment) are accepted.
    dest = _scan_018b_v100_dir(tmp_path)
    assert is_scan_complete(dest) is True


def test_scan_018b_output_integrity_verification(tmp_path):
    # Hash mismatch between manifest and on-disk events.json → rejected.
    dest = _scan_018b_v100_dir(
        tmp_path,
        mutate=lambda m: m["outputs"][0].__setitem__("sha256", "0" * 64),
    )
    assert is_scan_complete(dest) is False
    # Size mismatch → rejected.
    dest = _scan_018b_v100_dir(
        tmp_path,
        mutate=lambda m: m["outputs"][0].__setitem__("size_bytes", 999999),
    )
    assert is_scan_complete(dest) is False


def test_scan_018b_path_protections_preserved(tmp_path):
    # SCAN-018A-R1 protections still apply to v1.0.0 manifests.
    dest = _scan_018b_v100_dir(tmp_path)
    manifest = json.loads((dest / "scanner_data_manifest.json").read_text())
    manifest["outputs"][0]["name"] = "/etc/passwd"
    (dest / "scanner_data_manifest.json").write_text(json.dumps(manifest) + "\n")
    assert is_scan_complete(dest) is False

# ---------------------------------------------------------------------------
# SCAN-018C-I3 v1.1.0 dual snapshot + provenance tests
# ---------------------------------------------------------------------------

RAW_SNAPSHOT = "param_snapshot.raw.json"
EFFECTIVE_SNAPSHOT = "param_snapshot.effective.json"


def _scan_018c_v110_dir(tmp_path, mutate=None, **extra):
    name = f"20261121T013740123456Z_{next(_018b_dir_counter):032x}"
    dest = tmp_path / "scans" / name
    dest.mkdir(parents=True)

    header = {
        "module": "level_proximity",
        "scan_mode": "forward",
        "param_version": "1.0.0",
        "frozen_at": "2026-11-19T03:25:04Z",
        "universe": ["GOLD", "EURUSD"],
        "emission_timeframes": ["H1", "H4"],
    }
    events = [{"event_ts": "2026-09-07T00:00:00Z", "symbol": "GOLD"}]
    batch = {"events": events, "header": header}
    events_bytes = scan_mod._serialize_json(batch)
    raw_bytes = b'{"module":"level_proximity","param_version":"1.0.0"}\n'
    effective_bytes = b'{"module":"level_proximity","param_version":"1.0.0"}'
    (dest / "events.json").write_bytes(events_bytes)
    (dest / RAW_SNAPSHOT).write_bytes(raw_bytes)
    (dest / EFFECTIVE_SNAPSHOT).write_bytes(effective_bytes)

    base = "2026-11-21T01:37:40.123456Z"
    manifest = {
        "manifest_version": "1.1.0",
        "scan_id": name,
        "status": "COMPLETE",
        "scan_start": base,
        "outputs_complete_at": base,
        "execution_start": base,
        "module": "level_proximity",
        "scan_mode": "forward",
        "param_file": "scanner_params.level_proximity.json",
        "param_sha256": hashlib.sha256(raw_bytes).hexdigest(),
        "param_version": "1.0.0",
        "frozen_at": "2026-11-19T03:25:04Z",
        "config_hash": hashlib.sha256(effective_bytes).hexdigest(),
        "config_hash_algorithm": "sha256",
        "config_canonicalization_version": "SCANLINE-config-canon-v1",
        "config_hash_subject": "effective_validated_config",
        "config_schema_version": "1",
        "config_snapshot_raw": RAW_SNAPSHOT,
        "config_snapshot_effective": EFFECTIVE_SNAPSHOT,
        "universe": ["GOLD", "EURUSD"],
        "emission_timeframes": ["H1", "H4"],
        "series": [
            {
                "symbol": "GOLD",
                "timeframe": "D1",
                "file": "GOLD_D1.csv",
                "sha256": hashlib.sha256(b"dummy").hexdigest(),
                "size_bytes": 5,
                "bars_extracted": 1,
                "span": {"first_open_ts": None, "last_open_ts": None},
            }
        ],
        "total_bars_extracted": 1,
        "event_count": len(events),
        "validation_status": "valid",
        "validation_violation_count": 0,
        "evidence_tier": "forward_asof",
        "code_state": {"driver_sha256": hashlib.sha256(b"driver").hexdigest()},
        "outputs": [
            {"name": "events.json", "sha256": hashlib.sha256(events_bytes).hexdigest(), "size_bytes": len(events_bytes)},
            {"name": RAW_SNAPSHOT, "sha256": hashlib.sha256(raw_bytes).hexdigest(), "size_bytes": len(raw_bytes)},
            {"name": EFFECTIVE_SNAPSHOT, "sha256": hashlib.sha256(effective_bytes).hexdigest(), "size_bytes": len(effective_bytes)},
        ],
    }
    manifest.update(extra)
    if mutate:
        mutate(manifest)
    (dest / "scanner_data_manifest.json").write_text(json.dumps(manifest) + "\n")
    return dest


def test_scan_018c_v110_complete_manifest(tmp_path):
    dest = _scan_018c_v110_dir(tmp_path)
    assert is_scan_complete(dest) is True


@pytest.mark.parametrize("field", [
    "config_hash", "config_hash_algorithm", "config_canonicalization_version",
    "config_hash_subject", "config_schema_version", "config_snapshot_raw", "config_snapshot_effective",
])
def test_scan_018c_v110_missing_required_provenance_fields(tmp_path, field):
    dest = _scan_018c_v110_dir(tmp_path, mutate=lambda m, f=field: m.pop(f))
    assert is_scan_complete(dest) is False


def test_scan_018c_v110_malformed_provenance_fields(tmp_path):
    cases = [
        ("config_hash", "not-a-hash"),
        ("config_hash_algorithm", "md5"),
        ("config_canonicalization_version", "bad"),
        ("config_hash_subject", "wrong"),
        ("config_schema_version", None),
        ("config_schema_version", ""),
        ("config_snapshot_raw", "other.json"),
        ("config_snapshot_effective", "other.json"),
    ]
    for field, value in cases:
        dest = _scan_018c_v110_dir(tmp_path, mutate=lambda m, f=field, v=value: m.__setitem__(f, v))
        assert is_scan_complete(dest) is False, (field, value)


def test_scan_018c_v110_snapshot_missing_fails(tmp_path):
    dest = _scan_018c_v110_dir(tmp_path)
    (dest / RAW_SNAPSHOT).unlink()
    assert is_scan_complete(dest) is False
    dest = _scan_018c_v110_dir(tmp_path)
    (dest / EFFECTIVE_SNAPSHOT).unlink()
    assert is_scan_complete(dest) is False


def test_scan_018c_v110_snapshot_hash_mismatch_fails(tmp_path):
    dest = _scan_018c_v110_dir(tmp_path)
    (dest / RAW_SNAPSHOT).write_bytes(b"tampered")
    assert is_scan_complete(dest) is False
    dest = _scan_018c_v110_dir(tmp_path)
    (dest / EFFECTIVE_SNAPSHOT).write_bytes(b"tampered")
    assert is_scan_complete(dest) is False


def test_scan_018c_v110_size_mismatch_fails(tmp_path):
    dest = _scan_018c_v110_dir(tmp_path, mutate=lambda m: m["outputs"][1].__setitem__("size_bytes", 999))
    assert is_scan_complete(dest) is False
    dest = _scan_018c_v110_dir(tmp_path, mutate=lambda m: m["outputs"][2].__setitem__("size_bytes", 999))
    assert is_scan_complete(dest) is False


def test_scan_018c_v110_duplicate_or_missing_output_entry_fails(tmp_path):
    def dup(m):
        m["outputs"].append(dict(m["outputs"][1]))
    dest = _scan_018c_v110_dir(tmp_path, mutate=dup)
    assert is_scan_complete(dest) is False

    def missing(m):
        m["outputs"] = [o for o in m["outputs"] if o["name"] != RAW_SNAPSHOT]
    dest = _scan_018c_v110_dir(tmp_path, mutate=missing)
    assert is_scan_complete(dest) is False


def test_scan_018c_v110_traversal_and_absolute_path_rejected(tmp_path):
    dest = _scan_018c_v110_dir(tmp_path, mutate=lambda m: m["outputs"][1].__setitem__("name", "../escape.json"))
    assert is_scan_complete(dest) is False
    dest = _scan_018c_v110_dir(tmp_path, mutate=lambda m: m.__setitem__("config_snapshot_raw", "/tmp/x"))
    assert is_scan_complete(dest) is False


def test_scan_018c_v110_symlink_escape_rejected(tmp_path):
    dest = _scan_018c_v110_dir(tmp_path)
    outside = tmp_path / "outside.json"
    outside.write_bytes(b"{}")
    (dest / RAW_SNAPSHOT).unlink()
    (dest / RAW_SNAPSHOT).symlink_to(outside)
    manifest = json.loads((dest / "scanner_data_manifest.json").read_text())
    for o in manifest["outputs"]:
        if o["name"] == RAW_SNAPSHOT:
            b = outside.read_bytes()
            o["sha256"] = hashlib.sha256(b).hexdigest()
            o["size_bytes"] = len(b)
    manifest["param_sha256"] = hashlib.sha256(outside.read_bytes()).hexdigest()
    (dest / "scanner_data_manifest.json").write_text(json.dumps(manifest) + "\n")
    assert is_scan_complete(dest) is False


def test_scan_018c_v110_unsupported_version_fails(tmp_path):
    dest = _scan_018c_v110_dir(tmp_path, mutate=lambda m: m.__setitem__("manifest_version", "2.0.0"))
    assert is_scan_complete(dest) is False


def test_scan_018c_historical_v100_still_accepted(tmp_path):
    dest = _scan_018b_v100_dir(tmp_path)
    assert is_scan_complete(dest) is True


def test_scan_018c_real_scan_dual_snapshots_and_hashes(tmp_path):
    corpus = _make_corpus(tmp_path)
    param_path = _params_path(tmp_path)
    out = tmp_path / "out"
    scan_id = run_scan(corpus, out, param_path=param_path)
    dest = out / scan_id

    manifest = json.loads((dest / "scanner_data_manifest.json").read_text())
    assert manifest["manifest_version"] == "1.1.0"

    raw_bytes = param_path.read_bytes()
    raw_snap = (dest / RAW_SNAPSHOT).read_bytes()
    eff_snap = (dest / EFFECTIVE_SNAPSHOT).read_bytes()
    assert raw_snap == raw_bytes
    assert hashlib.sha256(raw_snap).hexdigest() == manifest["param_sha256"]
    assert hashlib.sha256(eff_snap).hexdigest() == manifest["config_hash"]
    assert eff_snap == eff_snap.rstrip(b"\n") or not eff_snap.endswith(b"\n")
    assert not eff_snap.endswith(b"\n")

    output_names = [o["name"] for o in manifest["outputs"]]
    assert output_names.count("events.json") == 1
    assert output_names.count(RAW_SNAPSHOT) == 1
    assert output_names.count(EFFECTIVE_SNAPSHOT) == 1

    by_name = {o["name"]: o for o in manifest["outputs"]}
    for name in ["events.json", RAW_SNAPSHOT, EFFECTIVE_SNAPSHOT]:
        p = dest / name
        assert by_name[name]["sha256"] == hashlib.sha256(p.read_bytes()).hexdigest()
        assert by_name[name]["size_bytes"] == p.stat().st_size

    assert is_scan_complete(dest) is True


def _atomic_failure_case(tmp_path, monkeypatch, fail_stage):
    corpus = _make_corpus(tmp_path)
    param_path = _params_path(tmp_path)
    root = tmp_path / f"scans_{fail_stage}"
    fixed_id = "20260101T000000000000Z_" + f"{abs(hash(fail_stage)) % (16**32):032x}"[:32]
    real_publish = scan_mod._publish_bytes
    real_sha = scan_mod.hashlib.sha256

    def fake_publish(dest_dir, name, data):
        if fail_stage == "events_write" and name == "events.json":
            raise OSError("injected events write failure")
        if fail_stage == "raw_snapshot_write" and name == RAW_SNAPSHOT:
            raise OSError("injected raw snapshot write failure")
        if fail_stage == "effective_snapshot_write" and name == EFFECTIVE_SNAPSHOT:
            raise OSError("injected effective snapshot write failure")
        if fail_stage == "manifest_publish" and name == "scanner_data_manifest.json":
            raise OSError("injected manifest publish failure")
        return real_publish(dest_dir, name, data)

    def fake_sha(data=b""):
        if fail_stage == "hash_size_preparation":
            # Fail during output inventory hash/size preparation after snapshots published.
            # Trigger when hashing raw snapshot bytes object used in inventory.
            if data == (root / fixed_id / RAW_SNAPSHOT).read_bytes() if (root / fixed_id / RAW_SNAPSHOT).exists() else None:
                raise RuntimeError("injected hash preparation failure")
        return real_sha(data)

    monkeypatch.setattr(scan_mod, "generate_scan_id", lambda: fixed_id)
    monkeypatch.setattr(scan_mod, "_publish_bytes", fake_publish)
    if fail_stage == "hash_size_preparation":
        monkeypatch.setattr(scan_mod.hashlib, "sha256", fake_sha)

    with pytest.raises(Exception):
        run_scan(corpus, root, param_path=param_path)
    dest = root / fixed_id
    assert is_scan_complete(dest) is False
    return dest


@pytest.mark.parametrize("stage", [
    "events_write", "raw_snapshot_write", "effective_snapshot_write", "hash_size_preparation", "manifest_publish",
])
def test_scan_018c_atomic_publication_failures_no_complete_scan(tmp_path, monkeypatch, stage):
    dest = _atomic_failure_case(tmp_path, monkeypatch, stage)
    # no COMPLETE manifest may be present
    manifest = dest / "scanner_data_manifest.json"
    if manifest.exists():
        obj = json.loads(manifest.read_text())
        assert obj.get("status") != "COMPLETE" or is_scan_complete(dest) is False
    assert is_scan_complete(dest) is False
