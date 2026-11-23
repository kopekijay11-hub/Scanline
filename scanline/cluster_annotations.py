"""Cluster annotation generator for session_anomalies batches (SCAN-021).

Derived publication artifact: recomputable from events.json + rule version.
Never mutates events.json. Refuses if batch events.json hash differs from
publication manifest.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

from scanline.prereg import cluster_key_for_event

RULE_VERSION = "scan021-cluster-v1"


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _events_hash_from_publication_manifest(scan_dir: Path) -> Optional[str]:
    pm = scan_dir / "publication_manifest.json"
    if not pm.is_file():
        return None
    obj = _load_json(pm)
    if not isinstance(obj, dict):
        return None
    outputs = obj.get("outputs")
    if isinstance(outputs, list):
        for o in outputs:
            if isinstance(o, dict) and o.get("name") == "events.json":
                sha = o.get("sha256")
                if isinstance(sha, str):
                    return sha
    # fallback to ledger_batch_sha256
    lbs = obj.get("ledger_batch_sha256")
    if isinstance(lbs, str):
        return lbs
    return None


def _events_hash_from_scanner_manifest(scan_dir: Path) -> Optional[str]:
    sm = scan_dir / "scanner_data_manifest.json"
    if not sm.is_file():
        return None
    obj = _load_json(sm)
    if not isinstance(obj, dict):
        return None
    outputs = obj.get("outputs")
    if isinstance(outputs, list):
        for o in outputs:
            if isinstance(o, dict) and o.get("name") == "events.json":
                sha = o.get("sha256")
                if isinstance(sha, str):
                    return sha
    return None


def verify_events_hash(scan_dir: Path) -> str:
    """Return events.json sha256 if it matches publication/scanner manifest.

    Raises ValueError on mismatch or missing manifest/hash.
    """
    scan_dir = Path(scan_dir)
    events_path = scan_dir / "events.json"
    if not events_path.is_file():
        raise ValueError(f"missing events.json: {events_path}")
    actual = _sha256_file(events_path)
    expected = _events_hash_from_publication_manifest(scan_dir)
    source = "publication_manifest.json"
    if expected is None:
        expected = _events_hash_from_scanner_manifest(scan_dir)
        source = "scanner_data_manifest.json"
    if expected is None:
        raise ValueError(f"no events.json hash found in manifests for {scan_dir}")
    if actual.lower() != expected.lower():
        raise ValueError(
            f"events.json hash mismatch vs {source}: actual={actual} expected={expected}"
        )
    return actual


def build_cluster_annotations(scan_dir: Path) -> Dict[str, Any]:
    """Build cluster_annotations.json content for a scan directory.

    Refuses if events.json hash differs from publication manifest.
    """
    scan_dir = Path(scan_dir)
    events_sha = verify_events_hash(scan_dir)
    events_obj = _load_json(scan_dir / "events.json")
    if not isinstance(events_obj, dict):
        raise ValueError("events.json must be object")
    events = events_obj.get("events")
    if not isinstance(events, list):
        raise ValueError("events.json missing events list")

    # group clusters
    clusters: Dict[Tuple[str, ...], List[int]] = {}
    for idx, e in enumerate(events):
        if not isinstance(e, dict):
            raise ValueError(f"event {idx} not dict")
        key = cluster_key_for_event(e)
        clusters.setdefault(tuple(key), []).append(idx)

    # stable cluster ids by sorted key
    sorted_keys = sorted(clusters.keys())
    key_to_id = {k: f"C{i+1:04d}" for i, k in enumerate(sorted_keys)}

    annotations: List[Dict[str, Any]] = []
    for idx, e in enumerate(events):
        key = tuple(cluster_key_for_event(e))
        member_indices = clusters[key]
        symbols = []
        for mi in member_indices:
            s = events[mi].get("symbol")
            if isinstance(s, str):
                symbols.append(s)
        # venue concentration: simple share of top symbol? better: share of most common venue/group unknown here.
        # Keep it simple and transparent: unique_symbols, cluster_size; venue_concentration as symbol concentration.
        uniq = sorted(set(symbols))
        top_count = max((symbols.count(s) for s in uniq), default=0)
        venue_concentration = {
            "unique_symbols": len(uniq),
            "top_symbol_share": (top_count / len(symbols)) if symbols else 0.0,
        }
        annotations.append({
            "event_index": idx,
            "cluster_id": key_to_id[key],
            "cluster_key": list(key),
            "cluster_size": len(member_indices),
            "venue_concentration": venue_concentration,
        })

    cluster_summaries = []
    for k in sorted_keys:
        members = clusters[k]
        symbols = [events[i].get("symbol") for i in members if isinstance(events[i], dict)]
        cluster_summaries.append({
            "cluster_id": key_to_id[k],
            "cluster_key": list(k),
            "anomaly_type": k[0],
            "cluster_size": len(members),
            "symbols": sorted(set(s for s in symbols if isinstance(s, str))),
        })

    manifest = {
        "artifact": "cluster_annotations",
        "rule_version": RULE_VERSION,
        "scan_id": scan_dir.name,
        "events_sha256": events_sha,
        "event_count": len(events),
        "cluster_count": len(clusters),
        "clusters": cluster_summaries,
        "annotations": annotations,
    }
    return manifest


def write_cluster_annotations(scan_dir: Path, out_path: Optional[Path] = None) -> Path:
    scan_dir = Path(scan_dir)
    manifest = build_cluster_annotations(scan_dir)
    if out_path is None:
        out_path = scan_dir / "cluster_annotations.json"
    out_path = Path(out_path)
    out_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return out_path
