"""Hermetic end-to-end test for the scan driver (SCAN-006)."""

import calendar
import csv
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scanline.scan import run_scan
from scanline.validator import validate_batch

ROOT = Path(__file__).resolve().parents[1]
PARAMS_PATH = ROOT / "config" / "scanner_params.level_proximity.json"

UNIVERSE = ["GOLD", "EURUSD", "USDCAD", "GER40", "USOIL"]


def _ts(dt):
    return calendar.timegm(dt.timetuple())


def _write_csv(path, rows):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["time", "open", "high", "low", "close", "volume"])
        for r in rows:
            w.writerow([r[0], r[1], r[2], r[3], r[4], 1.0])


def _make_corpus(root):
    corpus = root / "corpus"
    corpus.mkdir()
    start = datetime(2026, 9, 7, tzinfo=timezone.utc)
    end = datetime(2026, 9, 24, tzinfo=timezone.utc)
    transition = datetime(2026, 9, 22, tzinfo=timezone.utc)

    for sym in UNIVERSE:
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


def test_scan_driver_end_to_end(tmp_path):
    corpus = _make_corpus(tmp_path)
    # hermetic param file: frozen before the synthetic window
    import json as _json
    pdata = _json.loads(PARAMS_PATH.read_text())
    pdata["frozen_at"] = "2026-09-01T00:00:00Z"
    param_path = tmp_path / "params.json"
    param_path.write_text(_json.dumps(pdata))
    params_bytes = param_path.read_bytes()

    out1 = tmp_path / "out1"
    out2 = tmp_path / "out2"
    run_scan(corpus, out1, param_path=param_path)
    run_scan(corpus, out2, param_path=param_path)

    b1 = (out1 / "events.json").read_bytes()
    b2 = (out2 / "events.json").read_bytes()
    assert b1 == b2

    data = json.loads(b1)
    result = validate_batch(data["events"], data["header"], params_bytes)
    assert result["valid"] is True
    assert result["violations"] == []
