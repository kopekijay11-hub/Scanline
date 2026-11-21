# SCAN-018B — Manifest Completeness & Integrity Reconnaissance

**Mode:** READ-ONLY reconnaissance and design. No implementation authorized. No repository changes made (except this document, which is the deliverable).

**Date:** 2026-11-21
**Repository:** /home/joshua/scanline
**Baseline commit:** `daf84a9726f2fae58b34cb422d117422ca5e5111` (HEAD == origin/main)
**Test baseline:** `216 passed, 1 skipped` (confirmed via `python3 -m pytest -q`)

---

## 1. Repository baseline (confirmed)

| Item | Value |
|------|-------|
| Branch | `main` |
| HEAD commit | `daf84a9726f2fae58b34cb422d117422ca5e5111` |
| origin/main commit | `daf84a9726f2fae58b34cb422d117422ca5e5111` (matches HEAD) |
| Working-tree modified files | none |
| Untracked files | `docs/SCAN-016-PROPOSAL.md`, `docs/SCAN-016B-PROPOSAL.md`, `docs/SCAN-017F-DUPLICATE-IMPLEMENTATION-PROPOSAL.md`, `docs/SCAN-018-RECON.md` |
| Test baseline | `216 passed, 1 skipped` (matches expected) |
| Lint/typecheck tooling | none configured in `pyproject.toml` (pytest only) |
| AGENTS.md | none present |

Nothing was modified, cleaned, committed, or pushed. Historical records are untouched.

---

## 2. Objective

Investigate whether SCANLINE's manifest (`scanner_data_manifest.json`) contains sufficient information to identify, understand, verify, and reproduce a completed scan. SCAN-018A established scan identity, COMPLETE status, output filenames, output SHA-256, output byte sizes, and final manifest publication. SCAN-018B assesses completeness and long-term usefulness of that manifest and recommends a versioned manifest contract.

---

## 3. Current manifest inventory

### 3.1 Where the manifest is generated

`scanline/scan.py::run_scan` builds and publishes `scanner_data_manifest.json` **last** (after `events.json`), at scan.py:453-476. The manifest is the completion marker (`status == "COMPLETE"`).

### 3.2 Exact current manifest fields (top level)

| # | Field | Type | Source (scan.py line) | Required? | Validated by `is_scan_complete()`? | Independently verifiable? |
|---|-------|------|-----------------------|-----------|-----------------------------------|--------------------------|
| 1 | `scan_id` | str (`YYYYMMDDTHHMMSSffffffZ_<32-hex>`) | `generate_scan_id()` (68-76) | Yes | Yes — format + equals dest dir name (210-214) | Yes — equals directory name |
| 2 | `status` | str literal `"COMPLETE"` | hardcoded literal (455) | Yes | Yes — must equal `"COMPLETE"` (206) | Yes — constant |
| 3 | `execution_start` | str ISO-8601 UTC (`...Z`) | `_fmt_ts(datetime.now(timezone.utc))` (456) | Yes (always present) | No | No — wall clock, not reproducible |
| 4 | `extraction_span` | object `{start, end, end_exclusive}` | globals `EXTRACTION_START_TS`/`EXTRACTION_END_TS` (457-461) | Yes | No | Partially — recomputable from corpus CSV row ranges if corpus retained |
| 5 | `batch_window` | object `{batch_start_ts, batch_end_ts, inclusive}` | function args / module constants (462-466) | Yes | No | Partially — all events fall in window, but manifest stores no event count to cross-check |
| 6 | `series` | array of series-entry objects (see 3.3) | `_extract_series` per needed `(symbol, tf)` (349-381) | Yes | No (only `outputs` checked) | Yes — `sha256`/`size_bytes` recomputable from corpus CSV; `bars_extracted`/`span` recomputable |
| 7 | `param_file` | str (basename) | `param_path.name` (468) | Yes | No | Only if param file retained |
| 8 | `param_sha256` | str (64 lowercase hex) | `sha256(raw param file bytes)` (469) | Yes | No | Only if param file retained; byte-based, not content-canonical (SCAN-018C) |
| 9 | `evidence_tier` | str (`forward_asof` / `retrospective_membership`) | derived from `scan_mode` (470) | Yes | No | Yes — recomputable from `scan_mode` |
| 10 | `convention_documents` | array of str | `CONVENTION_DOCS` constant (471) | Yes | No | No — reference docs; may not exist / may move |
| 11 | `code_state` | object `{driver_sha256, [commit]}` | `_driver_sha256()` + `_git_head()` (448-452, 472) | `driver_sha256` yes; `commit` conditional | No | `driver_sha256` yes (rehash scan.py); `commit` yes via git |
| 12 | `outputs` | array of `{name, sha256, size_bytes}` (only `events.json`) | computed after events publish (473-475) | Yes — nonempty, `events.json` required | Yes — name/sha256/size match on disk, containment, no duplicates, events.json declared (217-253) | Yes — rehash `events.json`, `stat` size |

### 3.3 Series-entry fields (elements of `series`)

| Field | Type | Source | Verifiable? |
|-------|------|--------|-------------|
| `symbol` | str | `params["universe"]` iteration | Yes (from corpus) |
| `timeframe` | str | `params["emission_timeframes"]` + `"D1"` | Yes |
| `file` | str (basename) | `f"{symbol}_{tf}.csv"` | Yes (path construction) |
| `sha256` | str (64 hex) | `_sha256_file(path)` | Yes (rehash corpus CSV) |
| `size_bytes` | int | `path.stat().st_size` | Yes (stat corpus CSV) |
| `bars_extracted` | int | count of bars in extraction window | Yes (re-parse corpus CSV) |
| `span` | object `{first_open_ts, last_open_ts}` | first/last bar timestamp or null | Yes (re-parse corpus CSV) |

### 3.4 Fields present but NOT in the manifest

These exist in `events.json` header (scan.py:411-424) but are absent from the manifest:
- `module` (normalized module ID)
- `scan_mode`
- `param_version`
- `frozen_at`
- `universe` (summary; present implicitly via `series`)
- `emission_timeframes` (summary; present implicitly via `series`)
- `definition_timeframe`
- `event_count` (not stored anywhere in manifest)

### 3.5 Fields entirely absent

Manifest schema version, scan start/completion timestamps, scan duration, event count, events by anomaly type, validation status, R1–R5 results, violation counts, scan warnings, total input record count.

---

## 4. Field-by-field assessment against the proposed contents (SCAN-018B §4)

### Scan identity

| Proposed field | Status | Disposition |
|----------------|--------|-------------|
| Scan ID | Already available | `scan_id` (SCAN-018A) |
| Manifest schema version | Requires new instrumentation | None exists; reserve `manifest_version` |
| Completion status | Already available | `status` (`"COMPLETE"`) |
| Scan start timestamp | Requires new instrumentation | Only `execution_start` (publication-phase wall clock); no true scan start |
| Scan completion timestamp | Requires new instrumentation | None |
| Scan duration | Requires new instrumentation | None |

### Execution configuration

| Proposed field | Status | Disposition |
|----------------|--------|-------------|
| Module | Available with minor changes | In `events.json` header, not manifest; add `module` |
| Scan mode | Available with minor changes | In header, not manifest; add `scan_mode` |
| Symbols processed | Available with minor changes | Via `series`; no summary list; add `universe` |
| Timeframes processed | Available with minor changes | Via `series`; no summary list; add `emission_timeframes` |
| Parameter version | Available with minor changes | `param_version` in header, not manifest; add it |
| Parameter hash | Already available | `param_sha256` |
| Frozen configuration timestamp | Available with minor changes | `frozen_at` in header, not manifest; add it |

### Input provenance

| Proposed field | Status | Disposition |
|----------------|--------|-------------|
| Dataset filenames | Already available | `series[].file` |
| Symbol/timeframe coverage | Already available | `series[]` entries |
| Input file sizes | Already available | `series[].size_bytes` |
| Input SHA-256 hashes | Already available | `series[].sha256` |
| Input record counts | Available with minor changes | `series[].bars_extracted` per series; no total record count |

### Processing results

| Proposed field | Status | Disposition |
|----------------|--------|-------------|
| Events generated | Available with minor changes | `len(events)` computable; not stored; add `event_count` |
| Events by anomaly type | Requires new instrumentation | Not computed/stored |
| Validation status | Available with minor changes | Validation must pass to write manifest; not recorded; add `validation_status` |
| R1–R5 results where applicable | Requires new instrumentation | `validate_batch` returns violations but not stored |
| Validation violation counts | Requires new instrumentation | Not stored |
| Scan warnings | Requires new instrumentation | No warning mechanism exists |

### Output integrity

| Proposed field | Status | Disposition |
|----------------|--------|-------------|
| Output filename | Already available | `outputs[].name` |
| Output size | Already available | `outputs[].size_bytes` |
| Output SHA-256 | Already available | `outputs[].sha256` |
| Event count | Requires new instrumentation | Not stored; add `event_count` |
| Completion status | Already available | `status` |

**Summary:** SCAN-018A already provides scan ID, completion status, output inventory/hashes/sizes. The largest gaps are manifest schema version, timestamps/duration, `module`/`scan_mode`/`param_version`/`frozen_at` in the manifest, `event_count`, and validation results. None of these require elaborate new machinery — most are "available with minor changes." Events-by-anomaly-type, R1–R5 detail, violation counts, and warnings require new instrumentation and are better deferred.

---

## 5. Proposed manifest contract

### 5.1 Design principles

- Additive only; do not remove or redefine existing fields.
- Do not duplicate data already authoritative elsewhere (`events.json` header holds the full param snapshot; `series` holds input provenance).
- One top-level schema version field; unknown fields ignored (forward-compatible).
- Required vs optional explicitly distinguished.
- `is_scan_complete()` remains the lightweight completion check; deep integrity (rehashing corpus, re-validating R1–R5, content-canonical param hashing) belongs to a separate audit operation / SCAN-018C.

### 5.2 Recommended field contract

| Section | Field | Type | Required? | Source | Disposition |
|---------|-------|------|-----------|--------|-------------|
| Scan identity | `manifest_version` | str (semver-like, e.g. `"1.0.0"`) | Yes | constant | New — reserves schema version |
| | `scan_id` | str (SCAN_ID_RE) | Yes | `generate_scan_id()` | Existing (SCAN-018A) |
| | `status` | str (`"COMPLETE"`; reserved `RUNNING`/`FAILED`/`INTERRUPTED`) | Yes | literal | Existing |
| | `execution_start` | str ISO-8601 UTC | Yes | wall clock | Existing |
| | `execution_end` | str ISO-8601 UTC | No | wall clock at manifest publish | New |
| | `scan_duration_ms` | int (>=0) | No | `end - start` | New |
| Execution config | `module` | str | Yes | `normalize_module_id(...)` | Minor change (from header) |
| | `scan_mode` | str (`forward`/`retrospective`) | Yes | arg | Minor change (from header) |
| | `param_file` | str | Yes | `param_path.name` | Existing |
| | `param_sha256` | str (64 hex) | Yes | `sha256(raw bytes)` | Existing |
| | `param_version` | str | Yes | `params["param_version"]` | Minor change (from header) |
| | `frozen_at` | str ISO-8601 UTC | Yes | `params["frozen_at"]` | Minor change (from header) |
| | `universe` | array of str | Yes | `params["universe"]` | Minor change (summary) |
| | `emission_timeframes` | array of str | Yes | `params["emission_timeframes"]` | Minor change (summary) |
| | `batch_start_ts`, `batch_end_ts` | str | Yes | args / constants | Already via `batch_window` (keep; don't duplicate) |
| Input provenance | `series` | array | Yes | `_extract_series` | Existing |
| | `total_bars_extracted` | int (>=0) | No | sum of `series[].bars_extracted` | Minor change |
| Processing results | `event_count` | int (>=0) | Yes | `len(all_events)` | New |
| | `validation_status` | str (`"valid"`/`"invalid"`) | Yes | `validate_batch` result | Minor change |
| | `validation_violation_count` | int (>=0) | No | `len(result["violations"])` | New instrumentation |
| | `events_by_type` | object `{type: count}` | No | new instrumentation | Defer / SCAN-018C |
| Output integrity | `outputs` | array `{name, sha256, size_bytes}` | Yes | computed at publish | Existing |
| Code state | `code_state` | object `{driver_sha256, [commit]}` | Yes (`driver_sha256`) | `_driver_sha256()`/`_git_head()` | Existing |
| Reference | `convention_documents` | array of str | Yes | `CONVENTION_DOCS` | Existing |
| | `extraction_span` | object | Yes | globals | Existing |
| | `batch_window` | object | Yes | args/constants | Existing |
| | `evidence_tier` | str | Yes | derived from `scan_mode` | Existing |

### 5.3 Fields to reserve (SCAN-018C dependency, do not implement)

- `config_hash` — content-canonical parameter hash (SCAN-018C).
- `config_snapshot_uri` / `param_snapshot` — stored parameter snapshot (SCAN-018C).
- `frozen_config_ts` — distinct from `frozen_at` if SCAN-018C defines a freeze operation (currently `frozen_at` is a param-file content field, not an operation timestamp).

SCAN-018B may reserve field names but must not define canonical hashing or snapshot semantics.

---

## 6. Schema versioning strategy

### 6.1 Is a manifest schema version needed?

Yes. Historical manifests (pre-SCAN-018A) lack `scan_id`, `status`, `outputs`. Any future field addition (e.g. `event_count`, `module`, `param_version`) must be distinguishable from legacy manifests so consumers do not misread a legacy record as a modern complete scan.

### 6.2 Version format

Top-level `manifest_version: str`, semantic-version-like (e.g. `"1.0.0"`). Bump on backward-incompatible or semantically meaningful additions. Current in-repo manifests (all versions, pre- and post-SCAN-018A) carry no version field → treat absent as legacy/pre-1.0.0.

### 6.3 Required vs optional

Required: `manifest_version`, `scan_id`, `status`, `execution_start`, `series`, `param_file`, `param_sha256`, `evidence_tier`, `code_state.driver_sha256`, `outputs` (nonempty, `events.json` declared).
Optional: `execution_end`, `scan_duration_ms`, `module`, `scan_mode`, `param_version`, `frozen_at`, `universe`, `emission_timeframes`, `total_bars_extracted`, `event_count`, `validation_status`, `validation_violation_count`, `code_state.commit`, `convention_documents`, `extraction_span`, `batch_window`.

A missing optional field in a modern manifest is a data-quality signal, not automatically a failed scan (especially for legacy records).

### 6.4 Unknown-field behavior

Ignore unknown fields on read (forward compatibility). Writers must not emit fields newer than the declared `manifest_version` without bumping the version.

### 6.5 Forward/backward compatibility

- Legacy (pre-SCAN-018A) manifests: no `manifest_version`, no `scan_id`/`status`/`outputs`. Readable; consumers requiring `status == "COMPLETE"` treat them as incomplete (SCAN-018A position). A missing modern field must NOT be treated as proof an old scan failed.
- New manifests: include `manifest_version`; optional fields additive.
- Future fields: added as optional first, promoted to required only with a version bump and a migration/coexistence period.

---

## 7. Completion verification (`is_scan_complete()`)

### 7.1 What it verifies today (scan.py:172-254)

- Manifest exists, parses as JSON, is an object.
- `status == "COMPLETE"`.
- `scan_id`: valid SCAN_ID_RE format and equals the containing directory name.
- `outputs`: nonempty list; valid simple relative filenames; valid SHA-256; valid non-negative integer `size_bytes`; no duplicates; `events.json` declared.
- Path-traversal/symlink protection: `_is_safe_output_name` rejects absolute, `..`, Windows drive/UNC, nested, `.`/`..`; `_is_within_directory` rejects escaping symlinks (symlinks followed during resolution).
- Every declared output exists as a regular file inside the scan dir and matches recorded `sha256` and `size_bytes`.
- Read-only: never creates, modifies, or deletes files.

### 7.2 What it should eventually verify (SCAN-018B)

| Check | Belongs in `is_scan_complete()`? | Notes |
|-------|----------------------------------|-------|
| Manifest schema validity (`manifest_version` parse, required fields present) | Yes (lightweight) | Type/presence checks only; no corpus rehash |
| Scan identity | Yes | Already done |
| Completion status | Yes | Already done |
| Output inventory | Yes | Already done |
| Output hashes and sizes | Yes | Already done |
| Event count consistency (`event_count` == `len(events)`) | Yes — requires `event_count` field | Cheap: load events.json, count |
| Consistency between manifest and events | Yes — lightweight cross-field checks | e.g. `module`/`scan_mode` match events.json header |
| Validation completion | Yes — requires `validation_status` field | Presence check only; not re-validation |

### 7.3 Deeper integrity-audit (separate operation, NOT `is_scan_complete()`)

- Recompute input `series[].sha256`/`size_bytes` from corpus.
- Recompute `param_sha256` against retained param file.
- Content-canonical parameter hash verification (SCAN-018C).
- Full R1–R5 re-validation of `events.json`.
- Recompute `event_count` and `events_by_type` from scratch.
- Re-derive `param_version`/`frozen_at` consistency.

Rationale: `is_scan_complete()` is a fast, read-only consumer gate. A deep audit re-reads the corpus and re-runs validation — appropriate for a separate audit command, not for every consumer read.

### 7.4 Protections to preserve

All SCAN-018A-R1 path-traversal and symlink protections (`_is_safe_output_name`, `_is_within_directory`, scan_id/dir-name match, no vacuous empty `outputs`, `events.json` required) must be retained unchanged.

---

## 8. Historical compatibility

### 8.1 Existing historical scan directories

Three historical scan directories under `records/scans/`:

1. `level_proximity-2.0.0-window-2026-05-26_2026-06-24/` — `events.json` + `scanner_data_manifest.json`
2. `level_proximity-2.1.0-window-2026-07-09_2026-08-07/` — `events.json` + `scanner_data_manifest.json`
3. `level_proximity-1.1.0-window-2026-08-08_2026-09-06/` — `events.json` + `scanner_data_manifest.json`

### 8.2 Fields historical manifests contain

All three contain: `execution_start`, `extraction_span`, `batch_window`, `series`, `param_file`, `param_sha256`, `evidence_tier`, `convention_documents`, `code_state` (`driver_sha256`, `commit`).

### 8.3 Fields historical manifests are missing

`scan_id`, `status`, `outputs`, `manifest_version` (and any SCAN-018B additions: `module`, `param_version`, `frozen_at`, `event_count`, etc.).

### 8.4 Readability

Historical records remain readable as JSON. `is_scan_complete()` returns `False` for them (no `status == "COMPLETE"`, no `scan_id`, no `outputs`). That means "cannot be verified under the new completion protocol," NOT "the historical scan failed."

### 8.5 Coexistence strategy

- Legacy manifests (no `manifest_version`, no `scan_id`/`status`/`outputs`) coexist with new manifests.
- Consumers gate on `status == "COMPLETE"` + `is_scan_complete()`; legacy records fall out of that gate gracefully.
- No migration, no backfill, no modification of historical records (per restrictions and SCAN-018A position).
- Optional fields missing from legacy records are tolerated; required modern fields absent ⇒ legacy/incomplete under the new protocol, not failed.

---

## 9. Relationship with SCAN-018C

Keep configuration provenance and content hashing conceptually separate.

SCAN-018B may reserve manifest fields for:
- Configuration hash (`config_hash` / content-canonical `param_sha256` replacement).
- Parameter version (`param_version`).
- Frozen configuration timestamp (`frozen_at` / freeze operation timestamp).

SCAN-018C owns:
- Detailed canonical parameter hashing (content-canonical, not raw-bytes).
- Parameter snapshot design and storage.
- Formal definition of `frozen_at` as an operation timestamp vs. a param-file content field.

SCAN-018B identifies the dependency (manifest needs a place for config hash/version/frozen timestamp) without implementing canonical hashing or snapshots prematurely. The existing `param_sha256` (raw-bytes) remains; SCAN-018C may add a canonical hash alongside it.

---

## 10. Required tests (proposed; do not add yet)

1. Complete manifest schema — valid manifest with all required fields passes `is_scan_complete()` / schema validation.
2. Missing required fields — manifest missing a required field is rejected.
3. Invalid field types — wrong types (e.g. `size_bytes` as string, `outputs` as string) rejected.
4. Event count consistency — `event_count` matches `len(events)` in `events.json`.
5. Output inventory consistency — `outputs` matches files on disk (name/sha256/size).
6. Validation result consistency — `validation_status` / violation count matches validator output.
7. Manifest schema-version handling — absent version treated as legacy; unknown version handled gracefully.
8. Legacy manifest compatibility — historical manifests readable; `is_scan_complete()` returns `False` without treating as failed scan.
9. Corrupted or incomplete output references — missing/truncated output file, hash mismatch, size mismatch, traversal/symlink escape all rejected (SCAN-018A-R1 preserved).
10. Historical scan readability — all three historical `records/scans/*` manifests parse and `events.json` loads.

---

## 11. Compatibility risks

- **Consumer gate tightens legacy out:** `is_scan_complete()` returning `False` for historical manifests is correct under the new protocol but must not be interpreted as historical failure. Documentation must state this.
- **Byte-hash vs content-hash divergence:** `param_sha256` is raw-bytes; semantically identical configs hash differently (measured in SCAN-018-RECON §5.2). SCAN-018C canonical hashing could introduce a second hash without invalidating the existing one.
- **`run_scan` return value:** already changed from `None` to `scan_id` in SCAN-018A; no in-repo caller uses the return.
- **Output location:** SCAN-018A writes into `<output_dir>/<scan_id>/`; callers locate artifacts via returned `scan_id`. Manifest contract must not assume flat layout.
- **Wall-clock non-reproducibility:** `execution_start` (and any added `execution_end`/`scan_duration_ms`) differ across repeated identical scans; manifest is not byte-reproducible on these fields. `events.json` remains byte-reproducible (SCAN-018A preserved).
- **No lint/typecheck tooling:** `pyproject.toml` configures pytest only; no ruff/mypy/black to run as pre-commit gates.

---

## 12. Implementation sequence

1. Approve the manifest contract and schema-versioning strategy (this document).
2. Coordinate with SCAN-018C on reserved field names (`config_hash`, `param_version`, `frozen_at`) so SCAN-018B does not preempt canonical hashing semantics.
3. Add `manifest_version` and SCAN-018B "minor change" fields (`module`, `scan_mode`, `param_version`, `frozen_at`, `universe`, `emission_timeframes`, `event_count`, `validation_status`, optional `execution_end`/`scan_duration_ms`/`total_bars_extracted`) to `run_scan` manifest construction.
4. Add `event_count` consistency and `validation_status` checks to `is_scan_complete()` (lightweight, no corpus rehash).
5. Add tests §10 cases 1–10 using `tmp_path`; no historical records touched.
6. Run `python3 -m pytest -q`; verify `216 passed, 1 skipped` baseline plus new tests.
7. Document the contract in `scanline/scan.py` docstring and cross-reference `docs/SCAN-017-CONTRACT-DECISIONS.md`.
8. Request implementation approval before step 3 if not already granted.

---

## 13. Exact files likely to change

| File | Likely change |
|------|---------------|
| `scanline/scan.py` | Add manifest_version + new fields to manifest dict (`run_scan`, ~scan.py:453-476); extend `is_scan_complete()` with event-count and validation-status checks; preserve SCAN-018A-R1 protections |
| `tests/test_scan.py` | New tests for manifest schema, missing fields, type validation, event-count consistency, output-inventory consistency, version handling, legacy compatibility, corrupted outputs |
| `docs/SCAN-018B-MANIFEST-RECON.md` | This document (recon deliverable) |
| `docs/SCAN-017-CONTRACT-DECISIONS.md` | Optional cross-reference |

**Files NOT to change (per restrictions):** `scanline/validator.py`, `scanline/levels.py`, `scanline/sessions.py`, `scanline/schema.py`, `scanline/validation/*`, `config/*`, `records/*`, corpus datasets, and the three SCAN-016/017/018 proposal documents. No source, test, config, or historical-record modification is authorized in this reconnaissance phase.

---

## 14. Deliverable status

This document is the completed SCAN-018B reconnaissance report. No implementation has been performed. Awaiting explicit approval before any source, test, or manifest change.
