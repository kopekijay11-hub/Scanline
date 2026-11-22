"""Deterministic scan driver for Scanline (SCAN-006)."""

import argparse
import csv
import hashlib
import json
import os
import re
import secrets
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


def generate_scan_id() -> str:
    """Generate one unique scan ID per execution.

    Format: ``YYYYMMDDTHHMMSSffffffZ_<32-hex>`` using UTC wall clock and
    ``secrets.token_hex(16)``. Safe for directory/file names. Never embedded
    in events.json; the scan ID is publication metadata only.
    """
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return f"{ts}_{secrets.token_hex(16)}"


# Format of scan IDs produced by generate_scan_id(): UTC timestamp plus a
# 128-bit random hex suffix. Safe for directory and file names.
SCAN_ID_RE = re.compile(r"\d{8}T\d{6}\d{6}Z_[0-9a-f]{32}")
SHA256_HEX_RE = re.compile(r"[0-9a-f]{64}")
MANIFEST_NAME = "scanner_data_manifest.json"
EVENTS_NAME = "events.json"

# Manifest schema version emitted by the current writer (SCAN-018B).
MANIFEST_VERSION = "1.0.0"
MANIFEST_VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")

# Fields introduced by SCAN-018B that are not part of the SCAN-018A contract.
# A manifest carrying these fields without a ``manifest_version`` key is a
# malformed hybrid: incomplete under the versioned protocol.
_V100_ONLY_FIELDS = frozenset({
    "scan_start", "outputs_complete_at", "module", "scan_mode",
    "param_version", "frozen_at", "universe", "emission_timeframes",
    "event_count", "validation_status", "total_bars_extracted",
    "validation_violation_count",
})


def _serialize_json(obj: Any) -> bytes:
    return json.dumps(obj, indent=2).encode("utf-8") + b"\n"


def _sync_directory(path: Path) -> None:
    """Best-effort fsync of the containing directory entry after a replace."""
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    except (OSError, NotImplementedError):
        return
    try:
        os.fsync(fd)
    except (OSError, NotImplementedError):
        return
    finally:
        os.close(fd)


def _publish_bytes(dest_dir: Path, name: str, data: bytes) -> None:
    """Atomically publish ``data`` as ``dest_dir / name`` (Approach A).

    Serializes complete contents to a temp file in the same destination
    directory, flushes, fsyncs the file descriptor, then atomically renames
    via os.replace. The containing directory is synced afterward where
    supported.
    """
    tmp = dest_dir / f"{name}.tmp.{os.getpid()}"
    with open(tmp, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, dest_dir / name)
    _sync_directory(dest_dir)


def _is_valid_scan_id(value: Any) -> bool:
    """True only for well-formed SCAN-018A scan IDs."""
    return isinstance(value, str) and SCAN_ID_RE.fullmatch(value) is not None


def _is_valid_sha256(value: Any) -> bool:
    """True only for lowercase SHA-256 hex digests as emitted by the driver."""
    return isinstance(value, str) and SHA256_HEX_RE.fullmatch(value) is not None


def _is_valid_size(value: Any) -> bool:
    """True only for real (non-bool) non-negative integers."""
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _is_valid_iso_ts(value: Any) -> bool:
    """True only for non-empty ISO-8601 UTC strings parseable by _parse_ts."""
    if not isinstance(value, str) or not value:
        return False
    try:
        _parse_ts(value)
        return True
    except (ValueError, TypeError):
        return False


def _is_safe_output_name(name: Any) -> bool:
    """True only for simple relative output filenames: a single path
    component, never absolute, never a traversal, never a Windows drive or
    UNC path, and never ``.`` or ``..``.

    The current publication contract uses simple relative filenames
    (e.g. ``events.json``); nested or otherwise exotic names are rejected
    rather than resolved.
    """
    if not isinstance(name, str) or not name:
        return False
    if os.path.isabs(name):
        return False
    if re.match(r"^[a-zA-Z]:[\\/]", name) or name.startswith("\\\\"):
        return False
    if "\\" in name or "/" in name:
        return False
    if name in (".", ".."):
        return False
    return True


def _is_within_directory(path: Path, directory: Path) -> bool:
    """True if ``path`` resolves to a location inside ``directory``.

    Symlinks are followed during resolution, so a symlink that escapes the
    directory (or any other escape) yields False. Never modifies files.
    """
    try:
        path.resolve().relative_to(directory.resolve())
        return True
    except (ValueError, OSError):
        return False


def _verify_identity_and_outputs(dest: Path, manifest: Dict[str, Any]) -> bool:
    """SCAN-018A identity + output-integrity checks (R1 protections).

    Assumes ``manifest`` is a dict whose ``status`` has already been checked.
    Read-only: never creates, modifies, or deletes files.
    """
    # Scan identity: present, well-formed, and matching the directory name.
    scan_id = manifest.get("scan_id")
    if not _is_valid_scan_id(scan_id):
        return False
    if dest.name != scan_id:
        return False

    # Outputs: a nonempty list; no vacuous acceptance of empty collections.
    outputs = manifest.get("outputs")
    if not isinstance(outputs, list) or not outputs:
        return False

    seen_names = set()
    for entry in outputs:
        if not isinstance(entry, dict):
            return False
        name = entry.get("name")
        if not _is_safe_output_name(name):
            return False
        if name in seen_names:
            return False
        seen_names.add(name)
        if not _is_valid_sha256(entry.get("sha256")):
            return False
        if not _is_valid_size(entry.get("size_bytes")):
            return False

    # events.json is a required declared output.
    if EVENTS_NAME not in seen_names:
        return False

    # Every declared output must exist inside the scan directory and match
    # its recorded hash and size. Symlinks escaping the directory fail the
    # containment check and are never followed as valid outputs.
    for entry in outputs:
        name = entry["name"]
        out_path = dest / name
        if not _is_within_directory(out_path, dest):
            return False
        if not out_path.is_file():
            return False
        if entry["sha256"] != _sha256_file(out_path):
            return False
        if entry["size_bytes"] != _size_file(out_path):
            return False
    return True


def _verify_v100(dest: Path, manifest: Dict[str, Any]) -> bool:
    """Validate the complete SCAN-018B v1.0.0 versioned contract.

    Required fields: manifest_version, scan_id, status, execution_start,
    scan_start, outputs_complete_at, module, scan_mode, series,
    param_file, param_sha256, param_version, frozen_at, universe,
    emission_timeframes, event_count, validation_status, evidence_tier,
    code_state.driver_sha256, outputs (nonempty, events.json declared).
    Optional: total_bars_extracted, validation_violation_count, and the
    remaining reference fields. Unknown fields are ignored.
    """
    # Required fields present (scan_start / outputs_complete_at are required
    # for new v1.0.0 manifests per the SCAN-018B binding requirement).
    required = (
        "manifest_version", "scan_id", "status", "execution_start",
        "scan_start", "outputs_complete_at", "module", "scan_mode",
        "series", "param_file", "param_sha256", "param_version",
        "frozen_at", "universe", "emission_timeframes", "event_count",
        "validation_status", "evidence_tier", "code_state", "outputs",
    )
    for field in required:
        if field not in manifest:
            return False

    if manifest.get("status") != "COMPLETE":
        return False
    # A COMPLETE manifest must not report failed validation.
    if manifest.get("validation_status") != "valid":
        return False

    # code_state.driver_sha256 is required.
    code_state = manifest.get("code_state")
    if not isinstance(code_state, dict) or not _is_valid_sha256(code_state.get("driver_sha256")):
        return False

    # Field type / presence checks.
    if not isinstance(manifest.get("module"), str) or not manifest["module"]:
        return False
    if manifest.get("scan_mode") not in ("forward", "retrospective"):
        return False
    if not isinstance(manifest.get("param_file"), str) or not manifest["param_file"]:
        return False
    if not _is_valid_sha256(manifest.get("param_sha256")):
        return False
    if not isinstance(manifest.get("param_version"), str) or not manifest["param_version"]:
        return False
    if not _is_valid_iso_ts(manifest.get("frozen_at")):
        return False
    universe = manifest.get("universe")
    if not isinstance(universe, list) or not universe or not all(isinstance(s, str) for s in universe):
        return False
    emission_timeframes = manifest.get("emission_timeframes")
    if not isinstance(emission_timeframes, list) or not emission_timeframes or not all(isinstance(s, str) for s in emission_timeframes):
        return False
    if not isinstance(manifest.get("series"), list) or not manifest["series"]:
        return False
    if not _is_valid_size(manifest.get("event_count")):
        return False
    if not isinstance(manifest.get("evidence_tier"), str) or not manifest["evidence_tier"]:
        return False
    if not _is_valid_iso_ts(manifest.get("execution_start")):
        return False

    # Optional fields, when present, must be well-typed rather than silently
    # accepted with wrong types.
    if "total_bars_extracted" in manifest and not _is_valid_size(manifest["total_bars_extracted"]):
        return False
    if "validation_violation_count" in manifest and not _is_valid_size(manifest["validation_violation_count"]):
        return False

    # Identity + output integrity (SCAN-018A-R1 preserved).
    if not _verify_identity_and_outputs(dest, manifest):
        return False

    # Timestamp ordering: scan_start <= outputs_complete_at <= execution_start.
    try:
        scan_start = _parse_ts(manifest["scan_start"])
        outputs_complete_at = _parse_ts(manifest["outputs_complete_at"])
        execution_start = _parse_ts(manifest["execution_start"])
    except (ValueError, TypeError):
        return False
    if not (scan_start <= outputs_complete_at <= execution_start):
        return False

    # Event-count and header consistency against events.json.
    events_path = dest / EVENTS_NAME
    try:
        events_data = json.loads(events_path.read_text())
    except (ValueError, OSError):
        return False
    if not isinstance(events_data, dict):
        return False
    events = events_data.get("events")
    if not isinstance(events, list):
        return False
    if manifest["event_count"] != len(events):
        return False

    header = events_data.get("header")
    if not isinstance(header, dict):
        return False
    if manifest.get("module") != header.get("module"):
        return False
    if manifest.get("scan_mode") != header.get("scan_mode"):
        return False
    if manifest.get("param_version") != header.get("param_version"):
        return False
    if manifest.get("frozen_at") != header.get("frozen_at"):
        return False
    if manifest.get("universe") != header.get("universe"):
        return False
    if manifest.get("emission_timeframes") != header.get("emission_timeframes"):
        return False

    return True


def is_scan_complete(dest: Path) -> bool:
    """Consumer rule: a scan is complete iff it holds a durable manifest with
    ``status == "COMPLETE"`` and every listed output exists on disk with
    matching sha256 and size_bytes. A scan without a valid COMPLETE manifest
    is incomplete.

    Three manifest categories are distinguished:

    * Pre-SCAN-018A (no ``manifest_version``, missing ``scan_id``/``status``/
      ``outputs``): readable but not verifiable as complete → ``False``.
    * SCAN-018A (``scan_id``, ``status == "COMPLETE"``, ``outputs``, no
      ``manifest_version``): verified via the original SCAN-018A contract.
    * SCAN-018B v1.0.0 (``manifest_version`` present): verified against the
      complete versioned contract; unknown major versions are rejected as
      unverifiable, compatible minor/patch versions are accepted.

    Hardened verification (SCAN-018A-R1):

    * Path validation: output names must be simple relative filenames.
      Absolute paths, ``..`` traversal, Windows drive/UNC paths, and any
      name that escapes the scan directory after resolution (including via
      symlinks) are rejected. External files are never treated as valid
      scan outputs.
    * Scan identity: the manifest must carry a ``scan_id`` that is a valid
      string, matches the SCAN-018A identifier format, and equals the name
      of the containing scan directory. Mismatches are rejected.
    * Outputs: ``outputs`` must be a nonempty list. Every entry needs a
      valid filename, a valid SHA-256, and a valid non-negative integer
      ``size_bytes``. Duplicate names are rejected and ``events.json``
      must be declared. Every listed output must exist inside the scan
      directory and match its recorded hash and size. Malformed manifests
      return False; empty output collections are never accepted
      (no vacuous truth).

    The function is read-only: it never creates, modifies, or deletes
    files.

    Legacy readability and modern completion verification are different
    capabilities: a historical manifest may be readable as JSON while still
    returning ``False`` from ``is_scan_complete()``. That means it cannot be
    verified under the current completion protocol, not that the historical
    scan failed.
    """
    manifest_path = dest / MANIFEST_NAME
    if not manifest_path.is_file():
        return False
    try:
        manifest = json.loads(manifest_path.read_text())
    except (ValueError, OSError):
        return False
    if not isinstance(manifest, dict):
        return False

    # The ``manifest_version`` key is the version discriminant. A manifest
    # that lacks the key entirely is a legacy manifest (Category A: pre
    # SCAN-018A; Category B: SCAN-018A). A manifest that carries the key but
    # with an unparseable or unknown-major value is a versioned manifest that
    # cannot be verified (rejected as incomplete, not treated as failed).
    if "manifest_version" not in manifest:
        # Legacy manifests without a schema version key. A manifest carrying
        # v1.0.0-only fields but no version is a malformed hybrid: incomplete
        # under the versioned protocol.
        if any(field in manifest for field in _V100_ONLY_FIELDS):
            return False
        # Pre-SCAN-018A manifests lack status/scan_id/outputs → not
        # verifiable. SCAN-018A manifests carry status == "COMPLETE" → the
        # original SCAN-018A contract (Category B).
        if manifest.get("status") != "COMPLETE":
            return False
        return _verify_identity_and_outputs(dest, manifest)

    manifest_version = manifest["manifest_version"]

    # Category C: versioned manifests. Strict major.minor.patch parsing;
    # malformed version strings are never silently accepted.
    if not isinstance(manifest_version, str):
        return False
    match = MANIFEST_VERSION_RE.fullmatch(manifest_version)
    if not match:
        return False
    major = int(match.group(1))
    # Unknown major versions are rejected as unverifiable (not a failed scan).
    if major != 1:
        return False
    # Compatible minor/patch (major == 1): validate the complete v1.0.0 contract.
    return _verify_v100(dest, manifest)


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
              extraction_start_ts: str = None, extraction_end_ts: str = None) -> str:
    """Run one deterministic scan and publish its outputs atomically.

    Generates one scan ID per execution, creates the destination directory
    ``<output_dir>/<scan_id>`` with exclusive ownership, publishes
    ``events.json`` first and ``scanner_data_manifest.json`` last via
    temp-file + flush + fsync + os.replace, and returns the scan ID.

    The manifest's ``status == "COMPLETE"`` is the completion marker: a scan
    without a valid COMPLETE manifest is incomplete. Historical directories
    are never overwritten or deleted.
    """
    global EXTRACTION_START_TS, EXTRACTION_END_TS
    corpus_path = Path(corpus_path)
    output_dir = Path(output_dir)

    # Scan invocation timestamp: first wall-clock capture of run_scan entry,
    # captured before scan-ID generation.
    scan_start = _fmt_ts(datetime.now(timezone.utc))

    # One scan ID per execution, retained throughout the execution.
    scan_id = generate_scan_id()
    dest = output_dir / scan_id

    repo_root = Path(__file__).resolve().parents[1]
    if param_path is None:
        param_path = repo_root / "config" / "scanner_params.level_proximity.json"
    param_path = Path(param_path)
    from scanline.config_load import load_config
    loaded = load_config(param_path)
    params_bytes = loaded.raw_bytes
    params = loaded.runtime_config
    module = loaded.module

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
        "param_file": loaded.param_file,
        "param_sha256": loaded.param_sha256,
        "param_version": loaded.param_version,
        "frozen_at": loaded.frozen_at,
        "universe": list(params["universe"]),
        "emission_timeframes": list(params["emission_timeframes"]),
        "definition_timeframe": params.get("definition_timeframe", "D1"),
        "batch_start_ts": batch_start_ts,
        "batch_end_ts": batch_end_ts,
    }

    batch = {"events": all_events, "header": header}

    # Validate before any destination write; validation failures leave no
    # artifacts behind (preserves existing behavior).
    result = validate_batch(all_events, header, params_bytes)
    if not result["valid"]:
        raise RuntimeError(f"scan validation failed: {result['violations']}")

    # Exclusive scan-directory creation: no exist_ok. os.mkdir raises
    # FileExistsError if the destination already exists; nothing is
    # overwritten, deleted, or resumed.
    output_dir.mkdir(parents=True, exist_ok=True)
    os.mkdir(dest)

    # Publish events.json first.
    events_bytes = _serialize_json(batch)
    _publish_bytes(dest, "events.json", events_bytes)
    events_sha256 = hashlib.sha256(events_bytes).hexdigest()
    events_size = len(events_bytes)

    # All required outputs are durable; record output-completion timestamp.
    outputs_complete_at = _fmt_ts(datetime.now(timezone.utc))

    # Publish manifest last: the completion marker, only after the event
    # output is durable and verified.
    head = _git_head(repo_root)
    code_state: Dict[str, Any] = {"driver_sha256": _driver_sha256()}
    if head:
        code_state["commit"] = head
    execution_start = _fmt_ts(datetime.now(timezone.utc))
    manifest = {
        "manifest_version": MANIFEST_VERSION,
        "scan_id": scan_id,
        "status": "COMPLETE",
        "scan_start": scan_start,
        "execution_start": execution_start,
        "outputs_complete_at": outputs_complete_at,
        "module": module,
        "scan_mode": scan_mode,
        "param_file": loaded.param_file,
        "param_sha256": loaded.param_sha256,
        "param_version": loaded.param_version,
        "frozen_at": loaded.frozen_at,
        "universe": list(params["universe"]),
        "emission_timeframes": list(params["emission_timeframes"]),
        "series": series_manifest,
        "total_bars_extracted": sum(entry["bars_extracted"] for entry in series_manifest),
        "event_count": len(all_events),
        "validation_status": "valid",
        "validation_violation_count": len(result["violations"]),
        "evidence_tier": evidence_tier,
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
        "convention_documents": list(CONVENTION_DOCS),
        "code_state": code_state,
        "outputs": [
            {"name": "events.json", "sha256": events_sha256, "size_bytes": events_size}
        ],
    }
    manifest_bytes = _serialize_json(manifest)
    _publish_bytes(dest, "scanner_data_manifest.json", manifest_bytes)

    _sync_directory(dest)
    return scan_id


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
    scan_id = run_scan(
        Path(args.corpus_path),
        Path(args.output_dir),
        param_path=Path(args.param_file) if args.param_file else None,
        scan_mode=args.scan_mode,
        batch_start_ts=args.batch_start,
        batch_end_ts=args.batch_end,
        extraction_start_ts=args.extraction_start,
        extraction_end_ts=args.extraction_end,
    )
    print(f"Scan {scan_id} complete: {Path(args.output_dir) / scan_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
