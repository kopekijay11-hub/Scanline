# Scanline Full Re-Audit — 2026-11-22

**Mode**: read-only measurement audit. No production code, config, tests, fixtures, historical records, or corpus files modified. Only this report file added.

## Step 0 — Baseline

| Item | Value |
|---|---|
| `git status --short --branch` (at audit start) | `## test/level-proximity-2.1.0-review` + 7 untracked entries listed below |
| HEAD SHA (local, at audit start) | `d8634d8a5f739899ee19461dca9a3511ca5601ba` |
| `git ls-remote origin refs/heads/main` | `4ec723e91c1df7c06ceb18fed85caf26ddffb135 refs/heads/main` |
| Local == origin? | **No.** Local `main`/HEAD at `d8634d8`; `origin/main` at `4ec723e` (ahead by 1 commit: `4ec723e Add MIT LICENSE`). `git fetch --dry-run` confirmed. |
| Current branch (at audit start) | `test/level-proximity-2.1.0-review` |
| Python | `Python 3.14.4 (main, Aug 20 2026, 10:41:58) [GCC 15.2.0]` (`python3 --version`; `python` not on PATH) |
| pytest (resolved for clean-tree runs) | `pytest 9.1.1` via `/home/joshua/hiai/.venv/bin/pytest` (system `python3 -m pytest` unavailable; `/home/joshua/agent-eval-harness/.venv/bin/pytest` is 9.2.0, not used) |
| Platform | linux, `/home/joshua/scanline`, git repo yes |

### Working tree state (at audit start; untracked/modified only)

```
## test/level-proximity-2.1.0-review
?? docs/SCAN-016-PROPOSAL.md
?? docs/SCAN-016B-PROPOSAL.md
?? docs/SCAN-017F-DUPLICATE-IMPLEMENTATION-PROPOSAL.md
?? docs/SCAN-018-RECON.md
?? docs/SCAN-018C-CONFIG-PROVENANCE-PROPOSAL.md
?? docs/SCAN-018C-CONFIG-PROVENANCE-RECON.md
?? tests/test_level_proximity_210.py
```

No modified tracked files. The 6 known untracked docs are present and addressed in Part E. `tests/test_level_proximity_210.py` is also untracked (not in the 6-doc list); not touched.

### Resource/contention check

- `ps aux | grep seen_data_screen`: **present** — PID 511323, `joshua`, 99.8% CPU, `/home/joshua/hiai/.venv/bin/python -u research/seen_data_screen.py --family h1_validation/seen_data_family_balanced.jsonl --data-dir /home/joshua/corpus-store --charge-dir logs/charges/seen-data-clean-2026-11-21 --batch-size 25 --perm-seed 20261121 --n-perm 1000`, running since Nov21.
- `free -h` at audit start: Mem total 14Gi, used 9.5Gi, free 578Mi, shared 1.4Gi, buff/cache 5.7Gi, available 5.5Gi; Swap total 15Gi, used 3.3Gi, free 12Gi.
- Footprint policy followed: no parallel heavy processes; clean-tree pytest runs executed sequentially in detached `/tmp` worktrees; E2E scan used bounded single-symbol/window sample (EURUSD, H1, 429 bars + D1 14 bars) via temp output under `/tmp/opencode/scanline-audit-e2e`; no whole-dataset loads.

## Part A — System Inventory (from code)

### Package/module map (`scanline/`)

| Module | Purpose (from code/docstring) | Entry points / key APIs |
|---|---|---|
| `scanline/__init__.py` | Package marker; `__version__ = "0.1.0"`. | `__version__` |
| `scanline/schema.py` | Closed-field event/batch schema definitions, module registry, alias normalization. | `normalize_module_id`, constants `EVENT_FIELDS`, `SESSION_EVENT_FIELDS`, `BATCH_HEADER_FIELDS`, `LEVEL_TYPES`, `ANOMALY_TYPES`, `MODULES`, `EVENT_FIELDS_BY_MODULE`, etc. |
| `scanline/scan.py` | Deterministic scan driver: extract corpus bars, run detectors, validate, atomically publish `events.json` + config snapshots + `scanner_data_manifest.json`. | `run_scan(...) -> scan_id`, `main(argv)`, `is_scan_complete(dest)`, `generate_scan_id()`, `MANIFEST_VERSION=1.1.0` |
| `scanline/levels.py` | Level-proximity predicate (band-crossing) for module 1; pure computation over D1+emission bars. | `compute_events(d1_bars, emission_bars, params)` |
| `scanline/sessions.py` | Session-anomaly detector for module 2 (H1-only): missing/stub/Sunday/intra-session gaps; config validation/normalization helpers. | `compute_events(*args,**kwargs)`, aliases `compute_session_events/compute_session_anomalies/detect_session_anomalies/scan_sessions`, `validate_session_config` and aliases |
| `scanline/validator.py` | As-of batch validator orchestrator; dispatches R1-R5 and returns `{valid, rule_results, violations}`. | `validate_batch(events, header, param_file_bytes)` |
| `scanline/validation/__init__.py` | Validation package marker (empty). | — |
| `scanline/validation/context.py` | Frozen validation context dataclass. | `ValidationContext` |
| `scanline/validation/r1.py` | R1 causal validation (defined_at/event_ts causality, grid membership, session cluster schedule). | `validate_r1(ctx)` |
| `scanline/validation/r2.py` | R2 type/timeframe validation (level/anomaly type and emission timeframe membership). | `validate_r2(ctx)` |
| `scanline/validation/r3.py` | R3 batch causality validation (session event_ts <= batch_end_ts; level atr_basis == closed_bars_only). | `validate_r3(ctx)` |
| `scanline/validation/r4.py` | R4 parameter binding validation (param_sha256, version binding, scan_mode/evidence_tier, forward frozen_at, session config validation). | `validate_r4(ctx)` |
| `scanline/validation/r5.py` | R5 closed-schema validation (event/header fields, module validity, evidence_tier enum, numeric/type checks). | `validate_r5(ctx)` |
| `scanline/validation/utils.py` | Shared validation helpers. | `parse_ts`, `validate_timestamp`, `check_numeric`, `get_first_event_ts`, `cluster_expected_bars`, `normalize_module`, `grid_member` |
| `scanline/validation/duplicate.py` | Duplicate bar-key integrity (SCAN-017F): rejects repeated `(symbol,timeframe,open_ts)`. | `DuplicateBarKeyError`, `validate_unique_bar_keys(bars, symbol=None, timeframe=None, source=None)` |
| `scanline/config_canon.py` | SCANLINE-config-canon-v1 strict deterministic JSON canonicalization/hash utilities. | `canonicalize`, `canonical_sha256`, `parse_json_bytes`, `canonicalize_object`, `canonical_sha256_object` |
| `scanline/config_registry.py` | Schema registry for config families/versions. | `SchemaEntry`, `register_schema`, `resolve_schema`, `ensure_allowed_fields`, errors |
| `scanline/config_load.py` | Authoritative config loading/validation/normalization; produces raw/effective/runtime config, hashes, snapshots. | `load_config(param_path, schema_version=None) -> LoadedConfig` |

### Non-package operational/code areas

| Path | Purpose (observed) | Entry points |
|---|---|---|
| `tests/` | Pytest suite; reference validator; fixtures. | `pytest -q` / `python3 -m pytest` |
| `config/` | Frozen level_proximity param files (1.0.0,1.1.0,2.0.0,2.1.0). | consumed by `scan.py` / `config_load` |
| `records/ledger/scan-ledger.jsonl` | Append-only scan ledger (8 lines observed). | data record |
| `records/scans/*` | Historical scan artifacts (3 scans). | `events.json`, `scanner_data_manifest.json` |
| `records/surveys/*` | Survey/spotcheck JSON/MD artifacts. | data/docs |
| `docs/` | Work orders, freezes, recon/proposal/contract docs, upstream note. | documentation |
| `pyproject.toml` | Package metadata, pytest config. | build/test config |

### Inventory flags

- **Docs name but not present as code modules**: README names "validator as deliverable" and Phase 0 universe/timeframes; no CLI package/module named `validator.py` as standalone command beyond `scanline.validator.validate_batch` and `scanline.scan` driver. No `volatility_expansion`, `spread_blowout`, or session anomaly config under `config/` (only level_proximity configs exist). No `.github/workflows` CI files present.
- **Code exists but not named in README**: `config_canon.py`, `config_load.py`, `config_registry.py`, `validation/duplicate.py`, manifest/provenance machinery, session anomaly detector, scan driver atomic publication, `is_scan_complete`, ledger/records layout. README is minimal/stale.

## Part B — Detector and Validator Census

### Event family census

| Family | Status | Evidence | Tests proving |
|---|---|---|---|
| 1. Level proximity | **IMPLEMENTED** | `scanline/levels.py:compute_events` (L160+) computes D1 prior high/low/session structure + grid_round band-crossing events; validates params (`_validate_params` L47-83); duplicate-key guard (`validate_unique_bar_keys`, L162-163); deterministic sort by `(event_ts, level_type, level_price, defined_at)` (L241). Schema: `LEVEL_TYPES`, `EVENT_FIELDS`, `EMISSION_TIMEFRAMES` in `schema.py:20-29,5-17`. Driver dispatch: `scan.py:787-796`. | `tests/test_levels.py` (38 tests collected), `tests/test_scan014.py`, `tests/test_scan015.py`, `tests/test_frozen_params_e2e.py`, `tests/test_scan.py` level-proximity paths, `tests/test_validator.py` |
| 2. Session anomalies | **IMPLEMENTED** | `scanline/sessions.py` H1-only detector: `missing_session`, `stub_session`, `sunday_anomaly`, `intra_session_gap` (`ANOMALY_TYPES` schema.py:44-49). `_core_compute` (L458+) validates config, rejects duplicate keys (L466-468), groups by UTC date, interior-date session-level anomalies, maintenance-aware intra-session gaps, deterministic sort. Driver dispatch `scan.py:777-786`. | `tests/test_sessions.py` (86 tests collected), `tests/test_scan014.py`, validator/session config tests in `tests/test_validator.py`, `tests/test_scan.py` |
| 3. Volatility expansion | **ABSENT** | No implementation, schema, config, or tests found. `grep -rn volatility|spread|blowout` over code/docs returned no detector implementation. | None |
| 4. Spread blowouts | **ABSENT** | No implementation, schema, config, or tests found. | None |
| 5. Additional detectors not on list | **NONE FOUND** | `schema.py:MODULES={'level_proximity','session_anomalies'}` (L76); `EVENT_FIELDS_BY_MODULE`/`EMISSION_TIMEFRAMES_BY_MODULE` only register these two. Scan driver branches only these two modules (`scan.py:777-796`). | N/A |

### Validator census (`scanline/validation/`)

| Rule/module | What it rejects / enforces | Evidence | Tests |
|---|---|---|---|
| `context.py` | Shared frozen `ValidationContext` container. | `context.py:1-14` | exercised by validator/rule tests |
| `utils.py` | Timestamp parse/validation, numeric checks, first-event ts, cluster expected bars lookup, module normalization, grid membership. | `utils.py:1-89` | used by R1-R5; covered by `tests/test_validator.py`, `tests/test_scan015.py` |
| `duplicate.py` (SCAN-017F) | Rejects repeated `(symbol,timeframe,open_ts)` keys before counting/state processing; identical/conflicting OHLCV both rejected; no dedup. | `duplicate.py:1-181`, enforced by `levels.py:162-163`, `sessions.py:466-468` | `tests/test_sessions.py::TestScan017FDuplicateIntegrity`, `tests/test_levels.py::TestScan017FDuplicateIntegrity`, characterization updates |
| `r1.py` | Causal checks: session defined_at<=event_ts forward; retrospective defined_at==frozen_at, expected_bars matches frozen cluster schedule, symbol in schedule; level grid_round membership; structural defined_at<=event_ts. | `r1.py:1-108` | `tests/test_validator.py`, `tests/test_scan015.py`, `tests/test_equiv_scan015.py` |
| `r2.py` | Type/timeframe membership: session anomaly_type in `ANOMALY_TYPES`, timeframe in session emission; level level_type in `LEVEL_TYPES`, timeframe in level emission. | `r2.py:1-55` | `tests/test_validator.py` |
| `r3.py` | Batch causality: session event_ts <= batch_end_ts; level atr_basis == schema `ATR_BASIS` (`closed_bars_only`). | `r3.py:1-44` | `tests/test_validator.py` |
| `r4.py` | Param binding: header param_sha256 present and matches raw bytes; header/param/event version equality; scan_mode/evidence_tier validity and consistency; forward frozen_at strictly before first event_ts; session config validation. | `r4.py:1-96` | `tests/test_validator.py`, `tests/test_equiv_scan015.py`, `tests/test_frozen_params_e2e.py` |
| `r5.py` | Closed schema: event fields exact for module, header fields exact/required, module valid, evidence_tier enum valid, numeric/type/format checks. | `r5.py:1-83` | `tests/test_validator.py`, `tests/test_scan014.py`, `tests/test_scan015.py` |
| `validator.py` | Orchestrates R1-R5, collects/sorts violations, returns `valid/rule_results/violations`. | `validator.py:20-73` | `tests/test_validator.py`, `tests/test_scan015.py`, `tests/test_equiv_scan015.py` |

### SCAN-017F / 018A / 018B / 018C-I1-I3

- **SCAN-017F duplicate-bar integrity**: Implemented in `scanline/validation/duplicate.py` as single authoritative `validate_unique_bar_keys` raising `DuplicateBarKeyError(ValueError)`. Rejects repeated `(symbol,timeframe,open_ts)` after canonicalizing symbol/timeframe/UTC timestamp; first-duplicate left-to-right; no OHLCV in error. Enforced before sorting/counting/state in `sessions._core_compute` (`sessions.py:466-468`) and before processing in `levels.compute_events` for D1 and emission bars (`levels.py:162-163`). `scan.py` unchanged and covered by detector dispatch. Tests: session/level `TestScan017FDuplicateIntegrity` classes.
- **SCAN-018A persistence/manifest hardening**: Implemented in `scanline/scan.py`. `run_scan` creates `<output_dir>/<scan_id>/` with exclusive `os.mkdir` (L818-819), publishes `events.json`, `param_snapshot.raw.json`, `param_snapshot.effective.json` via temp+flush+fsync+`os.replace` (`_publish_bytes` L111-129), then publishes `scanner_data_manifest.json` last (L882-884). Failure removes COMPLETE manifest if published and syncs dir, preserving non-manifest artifacts for diagnosis (L885-899). `is_scan_complete` is read-only, verifies scan_id format/match, outputs nonempty/no-dupes/simple-safe paths/no symlink escape, hashes/sizes, `events.json` required, and category A/B/C manifest handling (L341-430). Tests in `tests/test_scan.py` (83 tests collected).
- **SCAN-018B manifest contract**: Implemented in `scan.py` as versioned manifest v1.0.0/v1.1.0 verification (`_verify_v100`, `_verify_v110`, `MANIFEST_VERSION_RE`, L218-430). Writer emits `manifest_version="1.1.0"` and SCAN-018B fields: scan_start, outputs_complete_at, module, scan_mode, param/param_sha256/param_version/frozen_at, universe, emission_timeframes, event_count, validation_status, evidence_tier, code_state, series, total_bars_extracted, validation_violation_count, etc. (L842-881). `is_scan_complete` accepts legacy SCAN-018A COMPLETE manifests (no manifest_version) via identity+outputs, rejects malformed hybrids, rejects unknown major, accepts minor 0/1. Tests in `tests/test_scan.py`.
- **SCAN-018C I1-I3 (config provenance)**: I1 canonicalization in `config_canon.py` implements `SCANLINE-config-canon-v1` (strict UTF-8, token-preserving decimal parsing, duplicate-key rejection, sorted keys, compact JSON, no trailing newline, numeric bounds/normalization, no float parsing). I2 authoritative loader in `config_load.py` reads raw bytes once, parses/validates/normalizes via schema registry (`config_registry.py`), produces `LoadedConfig` with raw/effective/runtime config, `param_sha256`, `config_hash`, canonicalization metadata, raw/effective snapshot bytes. I3 integrated in `scan.py`: `run_scan` uses `load_config` (L677-681), stores `param_sha256`/`config_hash` metadata in header/manifest, publishes raw and effective snapshots as outputs, and `_verify_v110` enforces snapshot/hash/output consistency. Tests: `tests/test_config_canon.py` (46), `tests/test_config_load.py` (26), `tests/test_scan_018c_i3.py` (10).

## Part C — Test Suite (clean-tree, committed tip)

### Clean-tree execution

- **Local evidence of record** (hosted CI not rerunnable; minutes exhausted until 2026-12-01, per work order). 
- Detached clean worktrees used (no working-tree contamination):
  - `/tmp/opencode/scanline-audit-clean` at `d8634d8` (local main/HEAD at audit start).
  - `/tmp/opencode/scanline-audit-4ec` at `4ec723e` (`origin/main`).

### Commands / verdicts

Command: `cd /tmp/opencode/scanline-audit-clean && /home/joshua/hiai/.venv/bin/pytest -q` (pytest 9.1.1, Python 3.14.4, pyproject `testpaths=["tests"]`)

```text
============================= test session starts ==============================
platform linux -- Python 3.14.4, pytest-9.1.1, pluggy-1.7.0
rootdir: /tmp/opencode/scanline-audit-clean
configfile: pyproject.toml
testpaths: tests
plugins: appmap-4.0.0, anyio-4.16.0, cov-7.1.0
collected 349 items
...
======================= 348 passed, 1 skipped in 59.26s ========================
```

Command: `cd /tmp/opencode/scanline-audit-4ec && /home/joshua/hiai/.venv/bin/pytest -q`

```text
================== 348 passed, 1 skipped in 62.11s (0:01:02) ===================
```

| Run | Tree | Collected | Passed | Failed | Skipped |
|---|---:|---:|---:|---:|---:|
| clean local HEAD | `d8634d8` | 349 | 348 | 0 | 1 |
| clean origin/main | `4ec723e` | 349 | 348 | 0 | 1 |

**Tip red?** No. No failing tests observed.

## Part D — End-to-End Proof on Real Data

Bounded sample (coexisting with seen-data screen): corpus `/home/joshua/corpus-store`, symbol `EURUSD`, emission `H1`, definition `D1`, extraction `2026-07-15T00:00:00Z`–`2026-08-08T00:00:00Z` (end exclusive), batch `2026-08-01T00:00:00Z`–`2026-08-08T00:00:00Z`, scan_mode `retrospective`, param file = temp `level_proximity` param v2.1.0 with EURUSD grid 0.01. Driver: clean `d8634d8` worktree via `PYTHONPATH=/tmp/opencode/scanline-audit-clean`.

| Metric | Value |
|---|---|
| Bars in | `EURUSD D1: 14 bars (EURUSD_D1.csv)`, `EURUSD H1: 429 bars (EURUSD_H1.csv)` |
| Events out | `17` total; by family/level_type: `{'d1_prior_high': 6, 'd1_session_structure': 9, 'grid_round': 1, 'd1_prior_low': 1}` |
| Validation | `status=valid`, `validation_violation_count=0` |
| Runtime | not benchmarked as perf claim; two sequential bounded runs completed successfully (timestamps in scan IDs ~0.38s apart) |

### Determinism

Two identical runs to separate output roots produced identical `events.json` bytes:

- scan1 `20261122T054528023201Z_f66cd7f0d0d06244e506fe0b6d008ead`, events sha256 `e28260c7db3d4030f0fb6a34ad954a3f09ddf8ecf80eb7ba497e6805156a48db`
- scan2 `20261122T054528402370Z_ab3beddf56fdac56bf529d04ba13bbce`, events sha256 `e28260c7db3d4030f0fb6a34ad954a3f09ddf8ecf80eb7ba497e6805156a48db`
- **Byte-identical: YES**. Manifest hashes differ as expected (scan_id/execution timestamps): `d97cb752f0866d16b01448aeaf3c01b7d5e139dc57a82be3c883e29fef6cba80` vs `0c4264aa807409f2fef9a70f38dc85e0c44e2477972fee5fb3a7f99669090fa2`.

### Provenance manifest (SCAN-018C I3)

Manifest fields observed: `manifest_version=1.1.0`, `status=COMPLETE`, `module=level_proximity`, `scan_mode=retrospective`, `param_version=2.1.0`, `param_sha256=866cce7f394b3a3487f523165467eb4984818f1bf2b3f162451d776244b64bd0`, `config_hash=790150c3ed7a23023358b7f8f3183140e25d3f72c416b29d87d1fd10a88dec56`, `config_hash_algorithm=sha256`, `config_canonicalization_version=SCANLINE-config-canon-v1`, `config_hash_subject=effective_validated_config`, `config_schema_version=1`, `config_snapshot_raw=param_snapshot.raw.json`, `config_snapshot_effective=param_snapshot.effective.json`, outputs include `events.json`, raw/effective snapshots. 

Checks: `raw_sha_matches=True`, `effective_sha_matches=True`, `is_scan_complete=True`. The manifest records the config actually loaded/validated by `load_config` and the snapshot bytes match recorded hashes — **SCAN-018C I3 promise verified on this sample**.

## Part E — Docs-vs-Code Drift

| Claim (doc/source) | Reality (Parts A-D) | Verdict |
|---|---|---|
| `README.md`: "standalone deterministic market-condition scanner; validator is the deliverable; modules are its evidence; offline research feed, never live-decision input" | Matches code posture (`scan.py` driver, `validator.py`, deterministic event ordering, no live trading hooks observed). | **MATCH** |
| `README.md` Phase 0 universe `GOLD, EURUSD, USDCAD, GER40, USOIL`; emission `H1,H4`; definition `D1` | Matches `config/scanner_params.level_proximity.json` v1.0.0. Other configs extend universe (33 symbols in v2.0.0/v2.1.0). README understates current config set. | **DRIFT (partial/stale)** |
| `README.md`: "Documentation: brief filed in project books, copy pending" | Many docs exist under `docs/`; README not updated. | **DRIFT** |
| `README.md`: no mention of session anomalies, config provenance, manifest v1.1.0, duplicate integrity | Implemented in code/tests. | **DRIFT** |
| `docs/SCAN-015-CLOSURE-SCAN-016-RECON.md`: SCAN-015 closure, 152 passed + 1 skipped at time, validator decomposition | Validator decomposition present (`scanline/validation/*`, thin `validator.py`); current suite is 348 passed + 1 skipped on clean tip (growth since closure). | **MATCH (historical), DRIFT (test-count stale)** |
| `docs/SCAN-017-CONTRACT-DECISIONS.md`: mixed-symbol/timeframe rejection, duplicate Policy B rejected by shared helper; characterization vs contract | Implemented as documented: `validate_unique_bar_keys` in sessions/levels; mixed-symbol/timeframe checks in sessions. | **MATCH** |
| `docs/SCAN-017E-DUPLICATE-POLICY.md`: Policy B implemented in SCAN-017F | `scanline/validation/duplicate.py`, enforcement in levels/sessions, tests present. | **MATCH** |
| `docs/SCAN-018A-PERSISTENCE-DESIGN.md`: atomic publication, scan_id, COMPLETE manifest, is_scan_complete, R1 hardening | Implemented in `scan.py`; tests in `test_scan.py`. | **MATCH** |
| `docs/SCAN-018B-MANIFEST-PROPOSAL.md`: v1.0.0 versioned manifest contract, legacy categories | Implemented (`_verify_v100`, manifest_version handling, category A/B/C). Current writer emits v1.1.0 per 018C. | **MATCH (with 018C extension)** |
| `docs/SCAN-018-RECON.md`: identified gaps; proposed 018A/B/C | 018A/B/C I1-I3 implemented on main; recon is historical plan. | **MATCH (historical plan, largely landed)** |
| "Four event families" in mission/Scanline definition: level proximity, session anomalies, volatility expansion, spread blowouts | Only level proximity and session anomalies implemented. | **DRIFT / NOT MET for 2 families** |
| Hosted CI rerunnable | Work order states minutes exhausted until 2026-12-01; no `.github/workflows` in repo. Local clean-tree run is evidence of record. | **MATCH (constraint confirmed)** |

### Untracked docs (required)

| File | Size (bytes) | One-line summary | Landed on main under another name / unlanded? |
|---|---:|---|---|
| `docs/SCAN-016-PROPOSAL.md` | 7668 | Proposal for session detection next work; reviews SCAN-015 closure, classifies behavioral changes, proposes incremental refactor/bugfix plan. | **Substance partially landed/superseded** by SCAN-016/017 implementation history and contract docs; file itself untracked/unlanded. |
| `docs/SCAN-016B-PROPOSAL.md` | 16058 | Maintenance-window date-correctness proposal (local-vs-UTC maintenance window mapping). | **Substance landed** in session maintenance handling (`_maintenance_utc_interval`/config normalization in `sessions.py`, `config_load.py`) and tests; proposal file untracked. |
| `docs/SCAN-017F-DUPLICATE-IMPLEMENTATION-PROPOSAL.md` | 18112 | Policy B duplicate-bar rejection implementation proposal. | **Substance landed** as `scanline/validation/duplicate.py`, enforcement in detectors, tests, and `SCAN-017E-DUPLICATE-POLICY.md`; proposal file untracked. |
| `docs/SCAN-018-RECON.md` | 34898 | End-to-end backend reliability/reproducibility reconnaissance, identified persistence/provenance gaps and 018A/B/C plan. | **Substance largely landed** through 018A/B/C I1-I3; recon file untracked. |
| `docs/SCAN-018C-CONFIG-PROVENANCE-PROPOSAL.md` | 108728 | Detailed SCAN-018C config provenance/canonical hashing/snapshot proposal. | **Substance largely landed** for I1-I3 (`config_canon.py`, `config_load.py`, `config_registry.py`, scan manifest/snapshots); proposal file untracked. |
| `docs/SCAN-018C-CONFIG-PROVENANCE-RECON.md` | 24226 | SCAN-018C reconnaissance of raw hash vs canonical hash, version integrity, snapshot options. | **Substance largely landed** by 018C implementation; recon file untracked. |

## Part F — Definition-of-Done Scorecard

| Criterion | Score | Evidence |
|---|---|---|
| Deterministic scanner | **MET** | `scan.py` deterministic sort/processing; duplicate-key rejection before state; E2E identical input produced byte-identical `events.json` (`e28260c7db3d4030f0fb6a34ad954a3f09ddf8ecf80eb7ba497e6805156a48db`). Clean suite green. |
| Level proximity family | **MET** | `levels.py:compute_events`, schema/driver integration, tests in `test_levels.py`, `test_scan014.py`, `test_scan.py`, validator rules. |
| Session anomalies family | **MET** | `sessions.py` missing/stub/sunday/intra-session gaps, schema/driver integration, tests in `test_sessions.py`, `test_scan014.py`. |
| Volatility expansion family | **NOT MET** | No code/schema/tests found. |
| Spread blowouts family | **NOT MET** | No code/schema/tests found. |
| H1/H4 emission, D1 definition | **MET (for implemented families/configs)** | `schema.py` EMISSION_TIMEFRAMES H1/H4, SESSION H1; DEFINITION_TIMEFRAME D1; configs use H1/H4 emission, D1 definition; `levels.py` uses D1 bars + emission bars. |
| Validated as-of event stream | **MET (for implemented batch contract)** | `validate_batch` R1-R5 before publish; driver raises on validation failure; manifests record validation_status/count; E2E valid. |
| Persistence + manifest + provenance hardening | **MET (implemented scope)** | SCAN-018A atomic publish/scan_id/COMPLETE/is_scan_complete; SCAN-018B versioned manifest; SCAN-018C I1-I3 raw+effective snapshots, config_hash/canon metadata, load_config boundary. Historical pre-018A manifests remain unverifiable by modern completion contract (expected). |
| Hosted CI evidence | **NOT DETERMINED / constrained** | CI minutes exhausted until 2026-12-01; no workflow files. Local clean-tree pytest runs are evidence of record. |

### What remains before Scanline is DONE (dependency order)

1. **Resolve origin/local divergence without history rewrite** — fast-forward local `main` to `origin/main` (`4ec723e`) or otherwise reconcile so committed audit/report work can be pushed ff-only; no force/rebase/drop. (Blocks clean delivery.)
2. **Define/approve missing event-family contracts** — volatility expansion and spread blowouts: schema, param/config, detector semantics, validator rules, evidence tier behavior. (Blocks implementation.)
3. **Implement volatility expansion detector + tests** — module code, config schema/registry entries, driver dispatch, closed schema fields, deterministic ordering, fixtures/goldens.
4. **Implement spread blowout detector + tests** — same integration surface as above.
5. **Update public docs to match reality** — README and top-level docs should reflect implemented families, config surface, manifest/provenance, and explicit non-implemented families; resolve status of untracked SCAN proposal/recon docs (land, archive, or delete intentionally).
6. **Restore/rerun hosted CI when minutes available** — add/confirm workflow and capture hosted green run; until then keep local clean-tree evidence labeled.
7. **Decide disposition of untracked working-tree artifacts** — 6 untracked docs and `tests/test_level_proximity_210.py`; do not silently discard; either commit intentionally through normal reviewed flow or remove by explicit decision.

## Machine-Readable Results

```json
{
  "audit_date": "2026-11-22",
  "baseline": {
    "git_status_short_branch_at_start": "## test/level-proximity-2.1.0-review",
    "head_sha_at_start": "d8634d8a5f739899ee19461dca9a3511ca5601ba",
    "origin_main_ls_remote": "4ec723e91c1df7c06ceb18fed85caf26ddffb135",
    "local_equals_origin_main": false,
    "branch_at_start": "test/level-proximity-2.1.0-review"
  },
  "tool_versions": {
    "python3": "Python 3.14.4",
    "pytest": "pytest 9.1.1 (/home/joshua/hiai/.venv/bin/pytest)"
  },
  "suite": {
    "evidence_type": "local_clean_tree",
    "runs": [
      {
        "tree": "d8634d8a5f739899ee19461dca9a3511ca5601ba",
        "collected": 349,
        "passed": 348,
        "failed": 0,
        "skipped": 1,
        "verdict": "======================= 348 passed, 1 skipped in 59.26s ========================"
      },
      {
        "tree": "4ec723e91c1df7c06ceb18fed85caf26ddffb135",
        "collected": 349,
        "passed": 348,
        "failed": 0,
        "skipped": 1,
        "verdict": "================== 348 passed, 1 skipped in 62.11s (0:01:02) ==================="
      }
    ]
  },
  "family_census": {
    "level_proximity": "IMPLEMENTED",
    "session_anomalies": "IMPLEMENTED",
    "volatility_expansion": "ABSENT",
    "spread_blowouts": "ABSENT",
    "additional_families_found": []
  },
  "e2e": {
    "corpus": "/home/joshua/corpus-store",
    "symbol": "EURUSD",
    "timeframes": ["D1", "H1"],
    "extraction_start": "2026-07-15T00:00:00Z",
    "extraction_end_exclusive": "2026-08-08T00:00:00Z",
    "batch_start": "2026-08-01T00:00:00Z",
    "batch_end": "2026-08-08T00:00:00Z",
    "bars_in": {"EURUSD_D1": 14, "EURUSD_H1": 429},
    "events_out_total": 17,
    "events_out_by_family": {
      "d1_prior_high": 6,
      "d1_session_structure": 9,
      "grid_round": 1,
      "d1_prior_low": 1
    },
    "validation_status": "valid",
    "validation_violation_count": 0,
    "determinism": {
      "byte_identical_events_json": true,
      "events_sha256_run1": "e28260c7db3d4030f0fb6a34ad954a3f09ddf8ecf80eb7ba497e6805156a48db",
      "events_sha256_run2": "e28260c7db3d4030f0fb6a34ad954a3f09ddf8ecf80eb7ba497e6805156a48db"
    },
    "provenance": {
      "manifest_version": "1.1.0",
      "status": "COMPLETE",
      "raw_sha_matches": true,
      "effective_sha_matches": true,
      "is_scan_complete": true
    }
  },
  "scorecard": {
    "deterministic_scanner": "MET",
    "level_proximity": "MET",
    "session_anomalies": "MET",
    "volatility_expansion": "NOT_MET",
    "spread_blowouts": "NOT_MET",
    "h1_h4_emission_d1_definition": "MET",
    "validated_asof_event_stream": "MET",
    "persistence_manifest_provenance_hardening": "MET",
    "hosted_ci_evidence": "NOT_DETERMINED"
  },
  "remaining_work_count": 7
}
```
