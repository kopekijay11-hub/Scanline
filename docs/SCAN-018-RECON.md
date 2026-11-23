# SCAN-018 — End-to-End Backend Reliability & Reproducibility (Reconnaissance)

**Mode:** READ-ONLY reconnaissance. No implementation authorized. No repository changes made.

**Date:** 2026-11-21
**Repository:** /home/joshua/scanline
**Proposal document:** docs/SCAN-018-RECON.md (this file)

---

## 1. Executive summary

SCANLINE is a single-driver, deterministic market-condition scanner (`scanline/scan.py:run_scan`) with two modules (`level_proximity`, `session_anomalies`), a five-rule validator (R1–R5), and JSON output (`events.json` + `scanner_data_manifest.json`).

**Headline measured result:** Repeated identical scans produce byte-for-byte identical `events.json`. The manifest is byte-identical except for `execution_start` (wall-clock). So the pipeline is **byte-for-byte reproducible for event content** and **semantically reproducible** (the only manifest delta is the execution timestamp).

**Principal reliability risks (observed, not assumed):**

1. **No global event ordering.** `compute_events` sorts per (symbol, timeframe), but `scan.py` never re-sorts the aggregated `all_events`. Output is grouped by (symbol, timeframe), internally sorted, but not globally chronological (9 sort-key inversions measured in a 1381-event scan; 115 sort-key ties). Deterministic and reproducible, but not a total order — event ordering is input-order-dependent, so any future change to corpus/universal iteration order changes event order without changing event contents.

2. **Manifest omits critical integrity fields.** The manifest contains no scan identifier, no `module`, no `event_count`, no output file locations, no output hash, no validation results, and no completion status. A manifest therefore cannot be cross-checked against `events.json`, cannot vouch for completeness, and a partially written/interrupted manifest is indistinguishable from a complete one.

3. **Non-atomic, unprotected writes.** `events.json` and the manifest are written with a direct `open(path, "w")` (no temp-file + rename, no `fsync`, no file locking). A crash or concurrent scan can leave partial/corrupt files, silently overwrite prior results, and there is no running/failed/incomplete state tracking.

4. **Parameter hash is byte-based, not content-canonical.** `param_sha256 = sha256(raw file bytes)`. Two semantically identical config files with different key order/whitespace produce different hashes (measured). `param_version` is a separate field, so config contents can change without the version label changing (version/content divergence possible).

5. **Module-level mutable globals.** `run_scan` mutates package-level `EXTRACTION_START_TS`/`EXTRACTION_END_TS` (`scan.py:106,137-140`) and the manifest reads those globals (`scan.py:242-243`). Reentrant/concurrent calls and sequential calls with differing extraction windows interfere with each other.

6. **No scan identifier linking artifacts.** `events.json` and the manifest are not linked by any scan ID; the "scan identifier" is implicitly the caller-chosen output directory path, which is recorded nowhere in the artifacts.

Most failures (invalid config, missing data, duplicate bars, validator failure) are caught **before** any file write, so they leave no partial files — that is reliable behavior. The dangerous failure window is serialization/write, which is unprotected.

---

## 2. Repository baseline

| Item | Value |
|------|-------|
| Branch | `main` |
| HEAD commit | `4921d87582b358ecf360a0f80ee908eac9d9797e` |
| origin/main commit | `4921d87582b358ecf360a0f80ee908eac9d9797e` (matches HEAD) |
| HEAD subject | `SCAN-017F: enforce duplicate bar integrity` |
| Working-tree modified files | none |
| Untracked files | `docs/SCAN-016-PROPOSAL.md`, `docs/SCAN-016B-PROPOSAL.md`, `docs/SCAN-017F-DUPLICATE-IMPLEMENTATION-PROPOSAL.md` |
| Untracked proposal docs touched? | **No** — all three remain untouched/unmodified (verified via `git status --short`, showing only `??`) |
| Test baseline | `184 passed, 1 skipped` (matches expected `184 passed, 1 skipped`) |
| Python | 3.14.4 |

`git status --short` returned only the three untracked proposal documents; no tracked file is modified, staged, or deleted. The repository is clean apart from the three pre-existing, excluded proposal documents.

---

## 3. End-to-end architecture and data flow

### 3.1 Components

- `scanline/scan.py` — `run_scan()`: CLI driver. Loads params, extracts series, dispatches to modules, filters to batch window, builds header, validates via `validate_batch`, writes `events.json` then `scanner_data_manifest.json`.
- `scanline/schema.py` — closed field sets, module IDs, aliases (`module_1` → `level_proximity`), `ATR_BASIS = "closed_bars_only"`.
- `scanline/levels.py` — `compute_events(d1_bars, emission_bars, params)`: level-proximity/band-crossing detector. Duplicate-key check, param validation, sorting, ATR/state, event emission, per-group sort.
- `scanline/sessions.py` — `compute_events(*args, **kwargs)`: session-anomaly detector (H1). Duplicate-key check, cluster config, session/intra-gap detection, per-group sort.
- `scanline/validation/duplicate.py` — `validate_unique_bar_keys()`: rejects repeated `(symbol, timeframe, open_ts)`; no silent dedup.
- `scanline/validator.py` — `validate_batch(events, header, param_file_bytes)`: runs R1–R5.
- `scanline/validation/r1..r5.py` — per-rule validators (causality, type/timeframe, batch causality, parameter binding, closed-schema).
- `scanline/validation/context.py` — `ValidationContext` (frozen dataclass).

### 3.2 Data flow (scan.py `run_scan`, lines 103–261)

1. **Configuration loading** — `param_path.read_bytes()` → `json.loads`. Default `config/scanner_params.level_proximity.json`. Module normalized via `normalize_module_id`.
2. **Parameter validation/freezing** — implicit via `_validate_params` (levels) / `validate_session_config` (sessions) and R4 at validation time. `frozen_at`, `param_version` read from params. No explicit "freeze" operation beyond reading the file; the file itself is the frozen snapshot.
3. **Market-data ingestion** — `_extract_series(corpus_path, symbol, tf)` reads `{symbol}_{tf}.csv`, filters rows to `[EXTRACTION_START_TS, EXTRACTION_END_TS)`, parses `time` as unix seconds, converts OHLC to float, sorts by `open_ts`. Returns bars + source path.
4. **Bar normalization** — bars normalized to `{symbol, timeframe, open_ts, open, high, low, close}`; sorted by `open_ts`; duplicate-key validation inside each module compute.
5. **Duplicate-bar validation** — `validate_unique_bar_keys` raises `DuplicateBarKeyError` on first repeated key (left-to-right); no dedup.
6. **Module dispatch** — per (symbol, emission tf): `compute_level_events(d1, emission, params)` or `compute_session_events(emission, params)`. D1 deduplicated across symbols via `seen_series`. Events filtered to `[batch_start_ts, batch_end_ts]` inclusive.
7. **Event generation** — see module compute functions; each module sorts its own events by a module-specific key, but **no global sort** in `scan.py`.
8. **Event validation** — `validate_batch(all_events, header, params_bytes)` → R1–R5. On failure raises `RuntimeError` before any write.
9. **Output serialization** — `json.dump({"events": ..., "header": ...}, indent=2) + "\n"` to `events.json`.
10. **Manifest generation** — `execution_start = now`, `extraction_span` (from globals), `batch_window`, `series` (per-symbol/tf file sha256, size, span, bars_extracted), `param_file`, `param_sha256`, `evidence_tier`, `convention_documents`, `code_state` (`driver_sha256`, git `commit`).
11. **Persistent storage** — direct `open(path, "w")` for both files; non-atomic; silent overwrite.

### 3.3 Header fields (closed, schema.py `BATCH_HEADER_FIELDS`)

`module, scan_mode, evidence_tier, param_file, param_sha256, param_version, frozen_at, universe, emission_timeframes, definition_timeframe, batch_start_ts, batch_end_ts`.

---

## 4. Reproducibility investigation

### 4.1 Experimental method

- Corpus: `/home/joshua/corpus-store` (production market data; not modified).
- Param file: isolated copy at `/tmp/kilo/params_test.json` = production `scanner_params.level_proximity.json` (v1.0.0) with `frozen_at` set to `2026-09-01T00:00:00Z` (strictly before batch window, required by R4).
- Command: `python3 -m scanline.scan /home/joshua/corpus-store /tmp/kilo/scanoutN --param-file /tmp/kilo/params_test.json` (batch default `2026-09-22..2026-10-22`, extraction default `2026-09-07..2026-10-22`).
- Outputs written to isolated `/tmp/kilo/scanout1`, `scanout2`, `scanout3` — no production/historical records touched.
- Comparison: `cmp` for byte-for-byte; `json` load + field diff for manifest; sort-key inversion analysis.

### 4.2 Results

**Run 1 vs Run 2 (identical inputs/config):**

| Artifact | Byte-for-byte identical? | Difference |
|----------|--------------------------|------------|
| `events.json` | **Yes** | none |
| `scanner_data_manifest.json` | **No** | only `execution_start` wall-clock timestamp (e.g. `...30.563233Z` vs `...31.798815Z`) |

All other manifest fields identical: `param_sha256`, `series` (all file sha256/size/span), `evidence_tier`, `code_state` (`driver_sha256`, `commit`), `extraction_span`, `batch_window`.

**Conclusion:**
- **A. Byte-for-byte reproducibility:** achieved for `events.json`. Not achieved for the manifest solely because of `execution_start` (a wall-clock metadata field).
- **B. Semantic reproducibility:** achieved — event contents and per-run ordering match exactly; only the execution timestamp metadata differs.

**Run determinism of ordering:** event order is identical across runs (verified `[key(e) for e in evs1] == [key(e) for e in evs2]`), so ordering is deterministic/reproducible for fixed input.

### 4.3 Ordering analysis (measured)

`events.json` (1381 events, level_proximity v1.0.0):

- Events are **grouped by (symbol, timeframe)** in universe/emission order; within each group sorted by `(event_ts, level_type, level_price, defined_at)`.
- **No global sort** in `scan.py` — `all_events` is never re-sorted after aggregation (`scan.py` relies on per-module sorts only).
- Measured **9 adjacent sort-key inversions** (e.g. a `2026-10-21T23:00:00Z` GOLD-H1 event precedes a `2026-09-22T00:00:00Z` GOLD-H4 event). Re-sorting by the declared key yields 0 inversions, confirming the stored order is **not** the global key sort.
- **115 sort-key tie groups** (max tie size 2) — the sort key is not a total order, so ties resolve by input order (stable sort).

This is reproducible (deterministic for fixed input) but **input-order-dependent**: any change to symbol/iteration order changes event order without changing event contents — a semantic-reproducibility risk for ordering-sensitive consumers.

### 4.4 Floating-point serialization

`json.dump` default float repr. Measured `distance_atr` values carry full repr precision (e.g. `0.3873043105296886`, `0.1886826133523782`). Deterministic across runs (CPython float repr is deterministic), but precision is implementation-dependent (not cross-language/cross-version guaranteed). `level_price` may be serialized as `int` (`4375`) or `float` (`4322.58`) depending on grid step integrality — type-inconsistent serialization for numerically equal values (e.g. `4375` int vs `4375.0` would differ, though both appear as `4375` here when integral).

### 4.5 Nondeterminism sources examined

| Source | Present? | Evidence |
|--------|----------|----------|
| Randomness / nondeterministic IDs | No | No `random`, `uuid`, `secrets` usage |
| Dict/set iteration order affecting output | No | All output dicts built in fixed insertion order; `json.dump` preserves order |
| Filesystem ordering | No | `needed`/`seen_series` dedup is order-deterministic |
| Environment-dependent | Partially | `execution_start` wall clock; `code_state.commit` from `git` (empty string if not a repo) |
| Module-level mutable globals | **Yes** | `EXTRACTION_START_TS`/`EXTRACTION_END_TS` mutated by `run_scan` (reentrancy/concurrency hazard) |

---

## 5. Configuration and parameter integrity

### 5.1 Parameter loading & hashing

- `params_bytes = param_path.read_bytes()`; `param_sha256 = sha256(params_bytes)` (raw bytes, **not** canonicalized).
- Header stores `param_sha256`, `param_version`, `frozen_at`, `param_file`, `universe`, `emission_timeframes`, `definition_timeframe`.
- Manifest stores `param_file`, `param_sha256`, `evidence_tier` — but **not** `param_version` and **not** `frozen_at` (those live only in `events.json` header).

### 5.2 Measured: hash is byte-based, not semantic

Reserializing the same config (different key order / whitespace) produces a different `param_sha256`:

| File form | sha256 (first 16 hex) |
|-----------|----------------------|
| Production file bytes | `1f921fa1e84a1a1f` |
| `json.dumps(orig)` reserialized | `d256eaa00e55f54f` |
| `json.dumps(orig, sort_keys=True, indent=2)` | `c288d455bf3eaa57` |

Same semantic contents, three different byte-level hashes. So:
- **Same bytes → stable hash:** yes (verified by repeated hashing of identical bytes).
- **Same semantic config → stable hash:** **no** — hash depends on byte formatting/key order.

### 5.3 Version vs content

`param_version` and `param_sha256` are independent. R4 (`validate_r4`) checks `param_file_version == header_version`, both derived from the same file within a single scan, so a single scan is internally consistent. However:
- Config contents can be edited while keeping `param_version` unchanged → version label and contents become inconsistent; hash changes but the version label does not reveal it.
- No field records *when* a config was last changed relative to a scan beyond `frozen_at` (which is a param-file content field, not a file mtime).
- **Missing/modified config file detection:** a missing `param_file` raises `FileNotFoundError` at `read_bytes()` (uncaught, crashes before write). A modified file is detected via `param_sha256` mismatch only if compared against a previously recorded hash; the scanner itself does not detect drift from a baseline.

### 5.4 Historical tie-in

Can a historical scan be tied to exact parameter contents? **Partially.** `events.json` header records `param_file`, `param_sha256`, `param_version`, `frozen_at` — enough to identify the param snapshot **if** the param file itself is retained. The manifest records `param_file` and `param_sha256` but not `param_version`/`frozen_at`. If the param file is later modified or deleted, the hash alone cannot reconstruct contents (hash is one-way), and there is no stored param snapshot. **Changing a config file afterward does not alter already-written historical artifacts** (artifacts are immutable once written), but it breaks the ability to re-derive/reproduce from the config alone.

---

## 6. Event and output integrity

### 6.1 Validation before serialization

Yes — `validate_batch` runs R1–R5 **before** `events.json` is written (`scan.py:223-225`). On failure, `RuntimeError` is raised and no output file is created. Invalid events cannot enter stored output via the normal path.

### 6.2 Event count vs manifest count

**Cannot be verified.** The manifest records no `event_count`. There is no manifest field to compare against `len(events)`. (events.json embeds its own header, but manifest and events.json are not cross-linked.)

### 6.3 Event ID/key collisions

Events have no explicit `id` or `event_id` field. Event identity is implicit: `(symbol, timeframe, level_type/anomaly_type, level_price, defined_at, event_ts)` etc. No uniqueness enforcement across the aggregated batch; duplicate event records are **not** distinguished from legitimate events sharing timestamps (the task explicitly says do not introduce dedup). Two events with identical fields would serialize as duplicate records with no marker.

### 6.4 Empty-event scans

Handled consistently: `events.json` contains `"events": []` with full header; manifest is still written with `series` (reflecting extracted bars, not events). Verified with an empty batch window (`2026-01-01..2026-01-02`) → exit 0, both files written, `events: []`. Manifest has no `event_count` field, so emptiness is only visible by reading `events.json`.

### 6.5 Serialization field omission/alteration

`json.dump` serializes all dict fields; R5 (closed-schema) validates no extra/missing fields before write. No silent omission in the happy path. Float repr precision noted above (implementation-dependent).

---

## 7. Manifest assessment

### 7.1 Manifest structure (measured, from `scan.py:239-257` and sample)

**Present fields:** `execution_start`, `extraction_span` (start, end, end_exclusive), `batch_window` (batch_start_ts, batch_end_ts, inclusive), `series` (per symbol/tf: symbol, timeframe, file, sha256, size_bytes, bars_extracted, span), `param_file`, `param_sha256`, `evidence_tier`, `convention_documents`, `code_state` (driver_sha256, [commit]).

**Absent fields (not recorded at all):**

| Required per SCAN-018 §6 | Present in manifest? |
|---|---|
| Scan identifier | No |
| Module | No |
| Symbol/timeframe coverage | Partial (via `series`, no summary) |
| Parameter version | **No** |
| Parameter hash | Yes (`param_sha256`) |
| Frozen config timestamp | **No** |
| Input dataset information | Partial (`series` file hashes/sizes/spans) |
| Scan execution timestamp | Yes (`execution_start`) |
| Event count | **No** |
| Output file locations | **No** |
| Output hashes / integrity | **No** |
| Validation results | **No** |
| Scan completion status | **No** |

### 7.2 Manifest can describe a scan that did not finish

- Manifest is written **after** `events.json`. If `events.json` writes successfully but the manifest write is interrupted (or the process crashes between), a partial/empty manifest exists with no completion status to flag it.
- There is no `status`/`completion_status` field and no separate "success" marker. A manifest file's presence is the only success signal, and a truncated manifest is indistinguishable from a valid one without re-parsing and cross-checking (which the manifest cannot support anyway, lacking event count/output hash).
- A manifest is **never** written on validation failure (validation precedes writes), so failed scans leave no manifest — but they also leave no explicit "failed" record.

### 7.3 Guaranteed vs optional

Guaranteed (always present on successful scan): `execution_start`, `extraction_span`, `batch_window`, `series`, `param_file`, `param_sha256`, `evidence_tier`, `convention_documents`, `code_state.driver_sha256`. `code_state.commit` present only if `git rev-parse HEAD` succeeds.

Optional/absent: everything in the "Absent" table above; `commit` conditional on git availability.

---

## 8. Storage and persistence assessment

### 8.1 Directory & file naming

- Output directory is caller-supplied (`output_dir` CLI arg), created with `mkdir(parents=True, exist_ok=True)`.
- Files: `events.json`, `scanner_data_manifest.json` — fixed names, no scan ID in filename.
- No scan identifier recorded anywhere in artifacts; scan "identity" is implicitly the output directory path.

### 8.2 Write behavior (non-atomic)

Both files written via direct `open(path, "w")` + `json.dump` + `f.write("\n")`. No temp file, no `os.replace`/`rename`, no `fsync`, no file locking.

Risks (all applicable):
- **Partial file creation:** crash mid-write leaves truncated JSON.
- **Existing-file overwrite:** silent overwrite; no guard against clobbering a prior scan's output.
- **Concurrent scans:** two scans writing the same output directory interleave/corrupt; no locking.
- **Atomicity not assumed, and not present:** ordinary successful writes hide the lack of atomicity.

### 8.3 Scan state distinguishability

SCANLINE **cannot** distinguish these states from artifacts alone:
- Running scans: no in-progress marker.
- Successfully completed scans: manifest presence (but no completion status field).
- Failed scans: no artifact at all (validation failure → no write; crash → partial artifact).
- Incomplete/interrupted scans: indistinguishable from completed (partial manifest looks like a manifest).

### 8.4 Historical preservation

Historical scans preserved only by using distinct output directories (the `records/scans/<name>/` layout is convention, not enforced by the driver). No registry, no ledger writes from the driver, no protection against overwriting a directory reused for a new scan.

---

## 9. Failure handling and recovery

| Failure stage | Exception raised? | Partial files remain? | Manifest written? | Incomplete mistaken for success? | Safe recovery? |
|---|---|---|---|---|---|
| Invalid config file (missing) | `FileNotFoundError` (uncaught) | No | No | No | Yes (rerun) |
| Invalid config content | `RuntimeError` (validation) | No | No | No | Yes |
| Missing dataset CSV | `FileNotFoundError` (uncaught, during extraction, before writes) | No | No | No | Yes |
| Malformed CSV record | `ValueError` (uncaught, `int`/`float` parse) | No | No | No | Yes |
| Duplicate market bars | `DuplicateBarKeyError` (ValueError, in module compute, before writes) | No | No | No | Yes |
| Detector exception | Propagates uncaught | No | No | No | Yes |
| Validator failure | `RuntimeError` | No | No | No | Yes |
| Serialization error | `TypeError`/`ValueError` from `json.dump` | **Yes** (partial `events.json`) | **No** (manifest not yet written) | No | Yes (rerun) |
| Filesystem write failure | `OSError` | **Yes** (possible partial) | **No** / partial | **Yes** (partial manifest possible) | Manual cleanup needed |
| Process interruption | (signal) | **Yes** (partial events.json and/or partial manifest) | **Possible partial** | **Yes** | Manual cleanup needed |

**Key point:** All input/validation failures are caught before any write (reliable). The unreliability is concentrated in the write/serialize phase, which is non-atomic and unprotected. A subsequent scan can recover safely **only if** it uses a fresh output directory or the operator manually removes partial files — there is no automated cleanup or state tracking.

---

## 10. Historical reproducibility

### 10.1 What is retained

- `events.json` header: full param snapshot (`param_file`, `param_sha256`, `param_version`, `frozen_at`, `universe`, `emission_timeframes`, `definition_timeframe`, `batch_*`, `module`, `scan_mode`, `evidence_tier`).
- Manifest: `param_file`, `param_sha256`, `code_state` (`driver_sha256`, `commit`), `extraction_span`, `batch_window`, `series` (input dataset hashes/sizes/spans).
- `records/ledger/scan-ledger.jsonl`: append-only ledger keyed by (corpus hashes, window, symbol set, module, params hash, code commit, scan_mode) with `batch_sha256`/`outcome` for confirmatory scans.

### 10.2 What is missing

- **No scan identifier** linking manifest ↔ events.json ↔ ledger line.
- Manifest lacks `param_version`, `frozen_at`, `module`, `event_count`, output hash, completion status.
- **No stored param snapshot** — only a hash (one-way); contents not recoverable from the artifact.
- **No code archive** — `driver_sha256` + `commit` identify the code, but the actual code revision is not bundled; reproducing requires checking out that commit.
- Scan settings (`batch_*`, extraction) are in manifest/events, so re-run settings are recoverable.

### 10.3 Three scenarios distinguished

1. **Re-running with current code:** possible; `driver_sha256`/`commit` in the new manifest will differ from the historical record, signaling code drift. Events may or may not be byte-identical depending on whether logic changed.
2. **Reproducing the original historical result:** requires original input data (recoverable via corpus hashes), original param file (NOT stored — only hash), original code revision (commit recorded), and scan settings (recorded). The param file contents are the gap.
3. **Proving a stored historical result has not changed:** byte-compare stored `events.json` against a fresh re-run — feasible only if logic and inputs are unchanged; `events.json` is byte-reproducible (measured). But there is no stored output hash in the manifest to verify integrity without re-running.

### 10.4 Minimum provenance for reliable reconstruction

- Scan ID (globally unique, recorded in manifest, events.json, and output path).
- Stored param snapshot (or content-addressed param store keyed by `param_sha256`).
- `param_version` and `frozen_at` in the manifest.
- `module` in the manifest.
- `event_count` + output file hash(es) in the manifest.
- Completion status field.
- `code_state` commit + driver_sha256 (already present).
- Output file locations.

---

## 11. Existing test coverage and gaps

Test baseline: `184 passed, 1 skipped`. Test files: `test_scan.py`, `test_scan014.py`, `test_scan015.py`, `test_frozen_params_e2e.py`, `test_levels.py`, `test_sessions.py`, `test_validator.py`, `test_equiv_scan015.py`, plus `tests/reference_validator.py` and fixtures.

| Coverage area | Status | Evidence |
|---|---|---|
| Repeated identical scans | Existing, sufficient (for events) | `test_scan.py` runs twice, asserts `events.json` bytes equal |
| Manifest consistency | Missing | No test asserts manifest field completeness, event-count match, or output-hash integrity |
| Config hash stability | Existing but incomplete | `test_r4_hash_mismatch` (hash mismatch detected) but no test for byte-vs-semantic hash sensitivity or stable-hash across identical bytes |
| Event serialization consistency | Existing | R5 extra/missing field tests (`test_equiv_scan015`, `test_validator`) |
| Empty-event scans | Existing but incomplete | `test_equiv_scan015.test_empty_events` (validator-level); no E2E empty-scan driver test |
| Partial failures | Missing | No tests for serialization/write/interruption leaving partial files |
| Interrupted writes | Missing | No tests |
| Existing-file collisions | Missing | No tests |
| Concurrent execution | Missing | No tests |
| Historical output preservation | Missing | No tests |
| Recovery from incomplete scans | Missing | No tests |

Classification per §12: repeated scans = **Existing and sufficient**; manifest consistency = **Missing and required**; config hash stability = **Existing but incomplete**; empty scans = **Existing but incomplete**; all failure/persistence/concurrency areas = **Missing and required**.

---

## 12. Classified findings

**A. Verified reliable behavior**
- Repeated identical scans produce byte-for-byte identical `events.json` (measured, 2 runs).
- Event contents deterministic and reproducible (measured).
- All input/validation failures (invalid config, missing data, malformed CSV, duplicate bars, detector exceptions, validator failure) occur before any file write — no partial files (code inspection).
- R1–R5 validate events before serialization; `RuntimeError` aborts before write.
- Duplicate bars rejected with no silent dedup (`validate_unique_bar_keys`).
- R4 detects `param_sha256` mismatch and version mismatch within a scan.
- Empty scans produce `events: []` + manifest, exit 0 (measured).

**B. Potential implementation defect (fixable without changing contract)**
1. No global event sort — ordering grouped by (symbol, timeframe), not chronological (measured inversions).
2. Manifest missing integrity fields: event count, output locations, output hash, validation results, completion status, scan ID, module, param_version, frozen_at.
3. Non-atomic, unprotected writes (direct `open("w")`, no temp+rename, no fsync, no locking).
4. Silent overwrite of existing output files; no running/failed/incomplete state tracking.
5. `param_sha256` byte-based, not content-canonical — semantically identical configs hash differently.
6. `param_version` decoupled from hash — version/content divergence possible.
7. Module-level mutable `EXTRACTION_START_TS`/`EXTRACTION_END_TS` — reentrancy/concurrency hazard.
8. No scan identifier linking `events.json`, manifest, and output directory.
9. Manifest can be partially written and indistinguishable from complete (no completion status).

**C. Contract / architecture decision (requires approval before changing)**
- Whether to add a scan ID / global unique identifier.
- Whether to make writes atomic (temp+rename) and add fsync.
- Whether manifest should include `event_count` and output hash.
- Whether to introduce a scan registry / ledger write from the driver.
- Whether `param_version` should be content-bound (e.g., hash-in-version) or remain independent.
- Whether event ordering should be a guaranteed total order (currently implementation-detail grouping).
- Whether to store a param snapshot for historical reconstruction.

**D. Insufficient evidence**
- Cross-version/cross-language float repr stability (not tested here; CPython-only measured).
- Behavior under genuine concurrent execution (not experimented — would require controlled concurrency test; identified as gap).
- Exact impact of removing/adding `execution_start` from manifest on downstream consumers.

---

## 13. Concrete examples and experimental evidence

**Example 1 — Byte-for-byte reproducibility (measured):**
```
$ cmp /tmp/kilo/scanout1/events.json /tmp/kilo/scanout2/events.json   # identical
$ cmp /tmp/kilo/scanout1/scanner_data_manifest.json /tmp/kilo/scanout2/scanner_data_manifest.json   # differs
# diff shows only:
#   "execution_start": "2026-11-21T01:14:30.563233Z"
# vs
#   "execution_start": "2026-11-21T01:14:31.798815Z"
```

**Example 2 — Param hash byte-sensitivity (measured):**
Same config, three serializations → three distinct `param_sha256` prefixes: `1f921fa1...` / `d256eaa0...` / `c288d455...`.

**Example 3 — Non-global event ordering (measured):**
1381 events; 9 adjacent sort-key inversions; 115 tie groups. E.g. a GOLD-H1 event at `2026-10-21T23:00:00Z` precedes a GOLD-H4 event at `2026-09-22T00:00:00Z` because all H1 events are emitted before all H4 events per symbol.

**Example 4 — Manifest missing fields (measured):**
Manifest keys: `execution_start, extraction_span, batch_window, series, param_file, param_sha256, evidence_tier, convention_documents, code_state`. No `event_count`, no `module`, no `param_version`, no `frozen_at`, no output hash, no completion status, no scan ID.

**Example 5 — Empty scan (measured):**
Batch `2026-01-01..2026-01-02` → exit 0, `events.json` = `{"events": [], "header": {...}}`, manifest written with `series` reflecting extracted bars. Manifest has no event-count field to signal emptiness.

---

## 14. Recommended remediation sequence

Order matters: hardening writes and adding identity first, since later correctness checks depend on trustworthy artifacts.

1. **Add a scan identifier** (UUID or content-derived) recorded in manifest, `events.json` header, and derived into the output directory name. Links artifacts and enables duplicate/conflicting-record detection.
2. **Make writes atomic** — write to a temp file in the same directory, then `os.replace` (rename) to the final name; add `fsync`. Prevents partial/corrupt files on crash.
3. **Add completion status + event count + output hash** to the manifest, so a manifest can vouch for its own output and a partial/interrupted manifest is detectable.
4. **Add existing-file protection** — fail or refuse to overwrite a non-empty output directory unless explicitly forced (prevents silent clobbering of historical records).
5. **Content-canonicalize the parameter hash** (or store a param snapshot) so semantically identical configs hash identically; consider binding `param_version` to contents.
6. **Add `param_version`, `frozen_at`, `module` to the manifest** for unambiguous historical tie-in.
7. **Remove or isolate the module-level `EXTRACTION_START_TS`/`EXTRACTION_END_TS` globals** — pass as parameters only; fixes reentrancy/concurrency hazard.
8. **Guarantee global event ordering** (total sort) or document it as non-chronological grouping — a contract decision (C).
9. **Add tests** for manifest consistency, interrupted writes, existing-file collisions, concurrency, empty scans, config hash stability, historical preservation, recovery (after implementation).

Items 1–4 address the most severe risks (corrupt/overwritten output, indistinguishable partial success, unlinked artifacts) and should be done before any behavior change to event generation or validation.

---

## 15. Dependencies and risks

- **Dependencies:** standard library only (`csv`, `hashlib`, `json`, `argparse`, `subprocess`, `pathlib`, `datetime`). No third-party runtime deps; `pytest` for dev.
- **Risk of changing event ordering:** downstream consumers may rely on current (grouped) order; making it globally chronological is a contract change (C) requiring approval.
- **Risk of atomic-write change:** minimal (internal write mechanics), but must preserve `indent=2` JSON format and trailing newline to keep byte-format stable.
- **Risk of config hash canonicalization:** changes `param_sha256` values for all existing records; breaks hash linkage to historical manifests unless a migration/dual-hash period is allowed. Contract decision (C).
- **Concurrency:** not currently supported; adding file locking is optional and out of scope for the first pass.
- **Historical records:** must not be modified or overwritten during remediation (per restrictions); all experiments used isolated `/tmp/kilo` dirs.

---

## 16. Exact files likely to change during future implementation

| File | Likely change |
|---|---|
| `scanline/scan.py` | Add scan ID; atomic write helper (temp+rename+fsync); completion status/event_count/output_hash in manifest; add `param_version`, `frozen_at`, `module` to manifest; remove global `EXTRACTION_START_TS/END_TS` mutation; global event sort (contract decision); existing-file overwrite guard |
| `scanline/schema.py` | Possibly extend `BATCH_HEADER_FIELDS`/manifest field set; possibly content-hash helpers |
| `scanline/validator.py` / `r4.py` | Possibly bind `param_version` to hash (contract decision) |
| Tests (`tests/`) | New tests for manifest consistency, interrupted writes, collisions, concurrency, empty scans, hash stability, recovery (to be added only after approval) |

**Files NOT to change (per restrictions):** production source not yet approved, tests, configuration, corpus datasets, historical scan records, and the three SCAN-016/017 proposal documents.

---

**Verification commands used (read-only, isolated temp dirs only):**
```
git status --short; git branch --show-current; git rev-parse HEAD; git rev-parse origin/main
python3 -m pytest  # -> 184 passed, 1 skipped
python3 -m scanline.scan /home/joshua/corpus-store /tmp/kilo/scanoutN --param-file /tmp/kilo/params_test.json
cmp /tmp/kilo/scanout1/events.json /tmp/kilo/scanout2/events.json
```
No repository files were modified, committed, or pushed.
