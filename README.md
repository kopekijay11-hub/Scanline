# Scanline

A deterministic market-condition event scanner emitting as-of-validated event streams as an offline research feed — never a live-decision input.

## Status

| Module | Status | Evidence |
|---|---|---|
| `level_proximity` | CONFIRMED (params `2.1.0`, freeze `docs/freezes/level_proximity-2.1.0.md`) | Three published confirmatory scans in `records/ledger/scan-ledger.jsonl` / `records/scans/index.jsonl`: `level_proximity-1.1.0-window-2026-08-08_2026-09-06` (616 events, `batch_sha256=9d89edb4c35b6f24786fc4b406e943cb1c26ba9424c5b1e1a5f1091b6c45d0d9`, outcome `inside pre-registration`), `level_proximity-2.0.0-window-2026-05-26_2026-06-24` (9,060 events, `batch_sha256=a370317f129b5a6f4d8e22622d8d18b404e93013ebb08ff2ffc77c1234f9610d`, outcome `breach: grid_H1,grid_H4`), `level_proximity-2.1.0-window-2026-07-09_2026-08-07` (4,624 events, `batch_sha256=3b9e4f1d75370ff3736c5e2c084491f781508a9a764235c67e836dd79a6a34b0`, outcome `inside pre-registration`). |
| `session_anomalies` | CONFIRMED (params `1.1.0`, freeze `docs/freezes/session_anomalies-1.1.0.md`) | Calibration `1.0.0` published and falsified on two of four types (`missing_session`, `stub_session`; ceilings operative) with Juneteenth set named (`records/scans/20261123T021148750070Z_72046b8e81b86046bcef1aa65486ee26`, 326 events, `batch_sha256=0da7c17cbb3539c047edc96ec29945690b8dbec1809e12f57fa5f9e5ac40370f`, `records/ledger/scan-ledger.jsonl`). Confirmatory `1.1.0` scan `20261123T081126751440Z_852b86b3fcc1134079fa71923e07d342`: 164 events / 44 clusters; all four types within pre-registered cluster ceilings (`reports/scan022/SCAN-022-prereg.md`, `reports/scan022/SCAN-022-session_anomalies-1.1.0-confirmatory.md`, `batch_sha256=db813c330ca35cb2595ac3eddd8e4691ff182869295b0ddb7cbf76b3787d0499`). |
| `volatility_expansion` | DESIGNED, NOT BUILT | Blocked on a research choice owned by a separate project. |
| `spread_blowouts` | DESIGNED, NOT BUILT | Requires bid/ask data the bar corpus does not contain. |

## How a scan earns trust here

- **Parameters frozen before the run.** Param files live in `config/` with `frozen_at` and recorded sha256 values; freeze records live in `docs/freezes/`, and scan manifests/snapshots record the param identity used (`records/scans/*/scanner_data_manifest.json`, `param_snapshot.raw.json`).
- **Expectations pre-registered before the confirmatory window is touched.** Confirmatory ceilings/conditions are written before the held-out scan is run (e.g., `docs/freezes/level_proximity-2.1.0.md`, `reports/scan022/SCAN-022-prereg.md`).
- **Confirmation only on held-out windows.** Confirmatory scans run on windows not used for tuning; outcomes are recorded in `records/ledger/scan-ledger.jsonl`.
- **Every published batch carries a completeness chain.** Each scan directory contains `events.json` and manifest/sidecar artifacts; `publication_manifest.json` records output hashes, and `records/scans/index.jsonl` and `records/ledger/scan-ledger.jsonl` record the published batch/hash/status. A reader can recompute `sha256(events.json)` and compare it to the manifest and ledger.
- **A falsified calibration is published, not buried.** The `session_anomalies` 1.0.0 calibration breach is recorded with named breach types in `records/ledger/scan-ledger.jsonl` and `records/scans/index.jsonl`.

## Quickstart

Run from the repo root, on a committed tree.

```bash
python3 -m pytest -q
```

Verify a published batch hash matches its publication manifest and ledger entry:

```bash
python3 - <<'PY'
import json, hashlib
from pathlib import Path

scan = Path('records/scans/20261123T081126751440Z_852b86b3fcc1134079fa71923e07d342')
pub = json.loads((scan/'publication_manifest.json').read_text())
events = scan/'events.json'
events_sha = hashlib.sha256(events.read_bytes()).hexdigest()
manifest_sha = next(o['sha256'] for o in pub['outputs'] if o['name']=='events.json')
ledger = [json.loads(l) for l in Path('records/ledger/scan-ledger.jsonl').read_text().splitlines() if l.strip()]
entry = next(l for l in ledger if l.get('batch_sha256') == manifest_sha)
print('hash_match_manifest', events_sha == manifest_sha)
print('ledger_status', entry['status'])
print('ledger_outcome', entry['outcome'])
PY
```

## Layout

- `scanline/` — scanner, validators, config loading, publication, and clustering code.
- `config/` — frozen scanner param files and calendar inputs.
- `records/` — schemas, append-only scan ledger, scan index, and published scan artifacts.
- `docs/freezes/` — parameter freeze records and pre-registrations.
- `reports/` — scan/job reports and calibration/prereg evidence.

## License

Copyright © 2026 Joshua Normandin. All Rights Reserved.
