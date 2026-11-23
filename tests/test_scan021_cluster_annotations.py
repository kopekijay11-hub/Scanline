import json
from pathlib import Path
import shutil
import pytest

from scanline.cluster_annotations import build_cluster_annotations, verify_events_hash, RULE_VERSION


SCAN19 = Path("records/scans/20261123T021148750070Z_72046b8e81b86046bcef1aa65486ee26")


def test_scan019_cluster_counts_match_review():
    m = build_cluster_annotations(SCAN19)
    # review §2 window A exact counts
    by_type = {}
    for c in m["clusters"]:
        t = c["anomaly_type"]
        by_type.setdefault(t, {"events": 0, "clusters": 0})
        by_type[t]["clusters"] += 1
        by_type[t]["events"] += c["cluster_size"]
    assert by_type["intra_session_gap"] == {"events": 288, "clusters": 18}
    assert by_type["missing_session"] == {"events": 6, "clusters": 1}
    assert by_type["stub_session"] == {"events": 4, "clusters": 2}
    assert by_type["sunday_anomaly"] == {"events": 28, "clusters": 4}
    assert m["event_count"] == 326
    assert m["rule_version"] == RULE_VERSION


def test_refuses_on_events_hash_mismatch(tmp_path):
    dst = tmp_path / SCAN19.name
    shutil.copytree(SCAN19, dst)
    # mutate events.json but leave manifests
    p = dst / "events.json"
    obj = json.loads(p.read_text())
    obj["events"][0]["symbol"] = "MUTATED"
    p.write_text(json.dumps(obj))
    with pytest.raises(ValueError, match="hash mismatch"):
        build_cluster_annotations(dst)


def test_annotations_cover_all_events():
    m = build_cluster_annotations(SCAN19)
    assert len(m["annotations"]) == m["event_count"]
    idxs = [a["event_index"] for a in m["annotations"]]
    assert idxs == list(range(m["event_count"]))
    for a in m["annotations"]:
        assert a["cluster_size"] >= 1
        assert a["cluster_id"].startswith("C")
        assert isinstance(a["cluster_key"], list)
