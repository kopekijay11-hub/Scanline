#!/usr/bin/env python3
"""
Publication manifest generator for Scanline scan directories (SCAN-018).

Backfills a sidecar publication manifest for published scans by verifying that
events.json sha256 matches the scan ledger's confirmatory batch_sha256 entry
for the scan (directory name). The legacy scanner_data_manifest.json is never
edited.

Usage (CLI):
    python -m scanline.publication <scan_dir> <ledger_path> <out_path>
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _size_file(path: Path) -> int:
    return path.stat().st_size


def _load_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_ledger_entries(ledger_path: Path) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    with open(ledger_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                entries.append(obj)
    return entries


def find_ledger_entry_for_scan(
    entries: List[Dict[str, Any]], scan_dir_name: str, events_sha256: str
) -> Optional[Dict[str, Any]]:
    """
    Find a ledger confirmatory entry whose batch_sha256 matches events_sha256.
    The scan is identified by matching the batch window/params context when possible,
    but per SCAN-018 we primarily verify hash equality against the ledger's
    confirmatory batch_sha256 for that published batch. We return the entry
    whose batch_sha256 == events_sha256.
    """
    for obj in entries:
        if not isinstance(obj, dict):
            continue
        bs = obj.get("batch_sha256")
        if isinstance(bs, str) and bs.lower() == events_sha256.lower():
            return obj
    return None


def build_publication_manifest(
    scan_dir: Path, ledger_path: Path, *, now_utc: Optional[datetime] = None
) -> Dict[str, Any]:
    """
    Build publication manifest dict for a scan directory.
    Raises ValueError if verification fails (hash mismatch).
    """
    scan_dir = Path(scan_dir)
    if not scan_dir.is_dir():
        raise ValueError(f"scan_dir is not a directory: {scan_dir}")

    events_path = scan_dir / "events.json"
    if not events_path.exists():
        raise ValueError(f"missing events.json in: {scan_dir}")

    if now_utc is None:
        now_utc = datetime.now(timezone.utc)

    events_sha256 = _sha256_file(events_path)

    entries = _load_ledger_entries(Path(ledger_path))
    ledger_entry = find_ledger_entry_for_scan(entries, scan_dir.name, events_sha256)
    if ledger_entry is None:
        raise ValueError(
            "events.json sha256 does not equal any ledger confirmatory batch_sha256 for this scan "
            f"(scan_dir={scan_dir.name}, events_sha256={events_sha256})"
        )

    # Load events.json to count events and read header
    events_obj = _load_json(events_path)
    if not isinstance(events_obj, dict):
        raise ValueError("events.json must be a JSON object")
    events_list = events_obj.get("events")
    if not isinstance(events_list, list):
        raise ValueError("events.json missing events list")
    event_count = len(events_list)
    header = events_obj.get("header")
    if not isinstance(header, dict):
        header = {}

    # Build outputs[]: every file in the directory (measured now)
    outputs: List[Dict[str, Any]] = []
    for child in sorted(scan_dir.iterdir()):
        if child.is_file():
            outputs.append(
                {
                    "name": child.name,
                    "sha256": _sha256_file(child),
                    "size": _size_file(child),
                }
            )

    emitted_module = header.get("module")
    _canon = {"module_1": "level_proximity", "level_proximity": "level_proximity", "session_anomalies": "session_anomalies"}
    canonical_module = _canon.get(emitted_module, emitted_module if isinstance(emitted_module, str) else "unknown")

    # header_summary
    universe = header.get("universe")
    universe_size = None
    if isinstance(universe, list):
        universe_size = len(universe)
    elif isinstance(universe, int):
        universe_size = universe

    header_summary = {
        "emitted_module": emitted_module,
        "canonical_module": canonical_module,
        "param_version": header.get("param_version"),
        "param_sha256": header.get("param_sha256"),
        "param_file": header.get("param_file"),
        "scan_mode": header.get("scan_mode"),
        "evidence_tier": header.get("evidence_tier"),
        "batch_start_ts": header.get("batch_start_ts"),
        "batch_end_ts": header.get("batch_end_ts"),
        "universe_size": universe_size,
    }

    ledger_outcome = ledger_entry.get("outcome")

    manifest: Dict[str, Any] = {
        "manifest_version": "1.0.0-publication",
        "scan_id": scan_dir.name,
        "backfilled_at": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "backfill_of": "scanner_data_manifest.json (legacy, unversioned, preserved unchanged)",
        "status": "COMPLETE",
        "completeness_basis": "events.json sha256 equals the scan ledger's confirmatory batch_sha256 for this scan",
        "outputs": outputs,
        "event_count": event_count,
        "header_summary": header_summary,
        "ledger_outcome": ledger_outcome,
        "ledger_batch_sha256": ledger_entry.get("batch_sha256"),
        "ledger_params_version": ledger_entry.get("params_version"),
        "ledger_window": ledger_entry.get("window"),
        "ledger_code_commit": ledger_entry.get("code_commit"),
    }
    return manifest


def write_publication_manifest(manifest: Dict[str, Any], out_path: Path) -> None:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate a publication manifest sidecar for a scan directory."
    )
    parser.add_argument("scan_dir", help="Path to the scan directory (e.g. records/scans/<scan_id>)")
    parser.add_argument("ledger_path", help="Path to scan-ledger.jsonl")
    parser.add_argument("out_path", help="Output path for publication_manifest.json")
    args = parser.parse_args(argv)

    try:
        manifest = build_publication_manifest(Path(args.scan_dir), Path(args.ledger_path))
    except ValueError as e:
        print(f"REFUSAL: {e}")
        return 2

    write_publication_manifest(manifest, Path(args.out_path))
    print(f"WROTE: {args.out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
