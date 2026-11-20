"""Deterministic scan driver for Scanline (SCAN-006)."""

import argparse
import csv
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

from scanline.levels import compute_events as compute_level_events
from scanline.sessions import compute_events as compute_session_events
from scanline.validator import validate_batch
from scanline.schema import normalize_module_id

BATCH_START_TS = "2026-09-22T00:00:00Z"
BATCH_END_TS = "2026-10-22T00:00:00Z"
EXTRACTION_START_TS = "2026-09-07T00:00:00Z"
EXTRACTION_END_TS = "2026-10-22T00:00:00Z"

CONVENTION_DOCS = [
    "docs/freezes/level_proximity-1.0.0.md",
    "docs/freezes/level_proximity-1.0.0-addendum-1.md",
    "docs/freezes/level_proximity-1.0.0-addendum-2.md",
    "docs/freezes/level_proximity-1.1.0.md",
    "records/surveys/widening-survey-2026-11-19.json",
]


def _parse_ts(ts_str: str) -> datetime:
    if ts_str.endswith("Z"):
        ts_str = ts_str[:-1] + "+00:00"
    dt = datetime.fromisoformat(ts_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _fmt_ts(dt: datetime) -> str:
    dt = dt.astimezone(timezone.utc)
    s = dt.isoformat()
    if s.endswith("+00:00"):
        s = s[:-6] + "Z"
    return s


def _iso_from_unix(ts: int) -> str:
    return _fmt_ts(datetime.fromtimestamp(ts, tz=timezone.utc))


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _size_file(path: Path) -> int:
    return path.stat().st_size


def _extract_series(corpus_path: Path, symbol: str, tf: str) -> Tuple[List[Dict[str, Any]], Path]:
    path = corpus_path / f"{symbol}_{tf}.csv"
    start_dt = _parse_ts(EXTRACTION_START_TS)
    end_dt = _parse_ts(EXTRACTION_END_TS)
    bars: List[Dict[str, Any]] = []
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ts = int(row["time"])
            dt = datetime.fromtimestamp(ts, tz=timezone.utc)
            if start_dt <= dt < end_dt:
                bars.append({
                    "symbol": symbol,
                    "timeframe": tf,
                    "open_ts": _iso_from_unix(ts),
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                })
    bars.sort(key=lambda b: b["open_ts"])
    return bars, path


def _git_head(repo_root: Path) -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=str(repo_root), stderr=subprocess.DEVNULL, text=True
        )
        return out.strip()
    except Exception:
        return ""


def _driver_sha256() -> str:
    return _sha256_file(Path(__file__).resolve())


def run_scan(corpus_path: Path, output_dir: Path, param_path=None, scan_mode: str = "forward",
              batch_start_ts: str = None, batch_end_ts: str = None,
              extraction_start_ts: str = None, extraction_end_ts: str = None) -> None:
    global EXTRACTION_START_TS, EXTRACTION_END_TS
    corpus_path = Path(corpus_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    repo_root = Path(__file__).resolve().parents[1]
    if param_path is None:
        param_path = repo_root / "config" / "scanner_params.level_proximity.json"
    param_path = Path(param_path)
    params_bytes = param_path.read_bytes()
    params = json.loads(params_bytes)
    module = normalize_module_id(params.get("module", "level_proximity"))

    if scan_mode not in ("forward", "retrospective"):
        raise ValueError(f"invalid scan_mode {scan_mode}")
    if batch_start_ts is None:
        batch_start_ts = BATCH_START_TS
    if batch_end_ts is None:
        batch_end_ts = BATCH_END_TS
    if extraction_start_ts is None:
        extraction_start_ts = EXTRACTION_START_TS
    if extraction_end_ts is None:
        extraction_end_ts = EXTRACTION_END_TS

    batch_start_dt = _parse_ts(batch_start_ts)
    batch_end_dt = _parse_ts(batch_end_ts)

    universe = params["universe"]
    emission_timeframes = params["emission_timeframes"]

    # allow extraction window override
    _prev_ext_start = EXTRACTION_START_TS
    _prev_ext_end = EXTRACTION_END_TS
    EXTRACTION_START_TS = extraction_start_ts
    EXTRACTION_END_TS = extraction_end_ts

    # Extract all needed series and build manifest.
    series_manifest: List[Dict[str, Any]] = []
    extracted: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}

    needed: List[Tuple[str, str]] = []
    for symbol in universe:
        if module != "session_anomalies":
            needed.append((symbol, "D1"))
        for tf in emission_timeframes:
            needed.append((symbol, tf))

    seen_series = set()
    for symbol, tf in needed:
        if (symbol, tf) in seen_series:
            continue
        seen_series.add((symbol, tf))
        bars, path = _extract_series(corpus_path, symbol, tf)
        extracted[(symbol, tf)] = bars
        if bars:
            span = {
                "first_open_ts": bars[0]["open_ts"],
                "last_open_ts": bars[-1]["open_ts"],
            }
        else:
            span = {"first_open_ts": None, "last_open_ts": None}
        series_manifest.append({
            "symbol": symbol,
            "timeframe": tf,
            "file": path.name,
            "sha256": _sha256_file(path),
            "size_bytes": _size_file(path),
            "bars_extracted": len(bars),
            "span": span,
        })

    # Run predicate per symbol and emission timeframe.
    all_events: List[Dict[str, Any]] = []
    if module == "session_anomalies":
        for symbol in universe:
            for tf in emission_timeframes:
                em_bars = extracted[(symbol, tf)]
                # tag bars with symbol if missing
                for b in em_bars:
                    if isinstance(b, dict) and "symbol" not in b:
                        b["symbol"] = symbol
                events = compute_session_events(em_bars, params)
                for e in events:
                    ets = _parse_ts(e["event_ts"])
                    if batch_start_dt <= ets <= batch_end_dt:
                        all_events.append(e)
    else:
        for symbol in universe:
            d1_bars = extracted[(symbol, "D1")]
            for tf in emission_timeframes:
                em_bars = extracted[(symbol, tf)]
                events = compute_level_events(d1_bars, em_bars, params)
                for e in events:
                    ets = _parse_ts(e["event_ts"])
                    if batch_start_dt <= ets <= batch_end_dt:
                        all_events.append(e)

    evidence_tier = "forward_asof" if scan_mode == "forward" else "retrospective_membership"

    header = {
        "module": module,
        "scan_mode": scan_mode,
        "evidence_tier": evidence_tier,
        "param_file": param_path.name,
        "param_sha256": hashlib.sha256(params_bytes).hexdigest(),
        "param_version": params["param_version"],
        "frozen_at": params["frozen_at"],
        "universe": list(params["universe"]),
        "emission_timeframes": list(params["emission_timeframes"]),
        "definition_timeframe": params["definition_timeframe"],
        "batch_start_ts": batch_start_ts,
        "batch_end_ts": batch_end_ts,
    }

    batch = {"events": all_events, "header": header}

    # Validate.
    result = validate_batch(all_events, header, params_bytes)
    if not result["valid"]:
        raise RuntimeError(f"scan validation failed: {result['violations']}")

    # Write events.json.
    events_path = output_dir / "events.json"
    with open(events_path, "w") as f:
        json.dump(batch, f, indent=2)
        f.write("\n")

    # Write manifest.
    head = _git_head(repo_root)
    code_state: Dict[str, Any] = {"driver_sha256": _driver_sha256()}
    if head:
        code_state["commit"] = head
    execution_start = _fmt_ts(datetime.now(timezone.utc))
    manifest = {
        "execution_start": execution_start,
        "extraction_span": {
            "start": EXTRACTION_START_TS,
            "end": EXTRACTION_END_TS,
            "end_exclusive": True,
        },
        "batch_window": {
            "batch_start_ts": batch_start_ts,
            "batch_end_ts": batch_end_ts,
            "inclusive": True,
        },
        "series": series_manifest,
        "param_file": param_path.name,
        "param_sha256": hashlib.sha256(params_bytes).hexdigest(),
        "evidence_tier": evidence_tier,
        "convention_documents": list(CONVENTION_DOCS),
        "code_state": code_state,
    }
    manifest_path = output_dir / "scanner_data_manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Scanline scan driver")
    parser.add_argument("corpus_path", help="path to corpus directory")
    parser.add_argument("output_dir", help="output directory")
    parser.add_argument("--scan-mode", choices=["forward", "retrospective"], default="forward")
    parser.add_argument("--batch-start", default=None)
    parser.add_argument("--batch-end", default=None)
    parser.add_argument("--extraction-start", default=None)
    parser.add_argument("--extraction-end", default=None)
    parser.add_argument("--param-file", default=None)
    args = parser.parse_args(argv)
    run_scan(
        Path(args.corpus_path),
        Path(args.output_dir),
        param_path=Path(args.param_file) if args.param_file else None,
        scan_mode=args.scan_mode,
        batch_start_ts=args.batch_start,
        batch_end_ts=args.batch_end,
        extraction_start_ts=args.extraction_start,
        extraction_end_ts=args.extraction_end,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
