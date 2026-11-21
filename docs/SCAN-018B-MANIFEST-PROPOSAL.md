# SCAN-018B — Manifest Schema & Implementation Proposal

**Mode: IMPLEMENTED (SCAN-018B). Implementation authorized and complete.**

**Date:** 2026-11-21
**Repository:** /home/joshua/scanline
**Baseline commit:** `daf84a9726f2fae58b34cb422d117422ca5e5111` (HEAD == origin/main)
**Source of truth:** `scanline/scan.py` (implemented), `tests/test_scan.py` (new SCAN-018B tests), this document (updated with implementation status).

Implemented files: `scanline/scan.py`, `tests/test_scan.py`.
Historical manifests, `events.json` files, scan directories, validator, levels, sessions, schema, and config files are unmodified.

---

## 1. Executive summary

SCAN-018A established scan identity (`scan_id`), completion marker (`status == "COMPLETE"`), output inventory (`outputs` with `name`/`sha256`/`size_bytes`), atomic publication, and read-only completion verification (`is_scan_complete()`). SCAN-018B proposes a complete, versioned, backward-compatible manifest contract that extends SCAN-018A without removing or redefining any existing field.

The proposal adds a manifest schema version, execution metadata (`scan_start`, `outputs_complete_at`; `execution_start` retained with its actual meaning — see §3), execution-configuration fields already present in the `events.json` header (`module`, `scan_mode`, `param_version`, `frozen_at`, `universe`, `emission_timeframes`), a summary `event_count`, lightweight validation results (`validation_status`, optional `validation_violation_count`), and optional summary input provenance (`total_bars_extracted`).

The misleading `execution_end`/`duration_ms` pair from the earlier draft is dropped: `execution_start` is captured at manifest-preparation time (scan.py:452), so `end - start` would be a near-zero, meaningless interval. Consumers that need a duration should derive it from `scan_start` and `outputs_complete_at` when both are present.

Fields reserved for SCAN-018C (content-canonical parameter hashing, parameter snapshots, configuration provenance) are named but not defined here.

All historical manifests remain readable and unmodified. Missing modern fields in historical records are treated as legacy/incomplete under the new protocol, never as proof of historical failure.

---

### 1.1 Implementation status (final field behavior)

The contract is implemented in `scanline/scan.py` and covered by new tests in
`tests/test_scan.py`. Final behavior:

* **Writer (`run_scan`):** emits `manifest_version: "1.0.0"`; captures
  `scan_start` at `run_scan` entry (before scan-ID generation),
  `outputs_complete_at` after `events.json` is durable and hashed, and
  `execution_start` immediately before manifest dict construction with its
  existing manifest-preparation/publication meaning. Guarantees
  `scan_start <= outputs_complete_at <= execution_start` (UTC-aware).
  Populates every SCAN-018A field unchanged plus the SCAN-018B fields
  `module`, `scan_mode`, `param_version`, `frozen_at`, `universe`,
  `emission_timeframes`, `total_bars_extracted`, `event_count`,
  `validation_status` (`"valid"`), and optional `validation_violation_count`.
  No execution-specific timestamps are written into `events.json`.

* **Consumer (`is_scan_complete`):** distinguishes three categories:
  * Pre-SCAN-018A (no `manifest_version` key, missing `scan_id`/`status`/
    `outputs`): readable but returns `False`.
  * SCAN-018A (`scan_id`, `status == "COMPLETE"`, `outputs`, no
    `manifest_version` key): verified via the original SCAN-018A contract.
  * SCAN-018B v1.0.0 (`manifest_version` key present): validates the
    complete versioned contract. `scan_start` and `outputs_complete_at` are
    required for v1.0.0. Unknown major versions are rejected as
    unverifiable; compatible minor/patch versions (major == 1) are accepted;
    malformed version strings are never silently accepted; unknown optional
    fields are ignored.

* **Historical compatibility:** historical manifests, `events.json` files,
  and scan directories under `records/scans/` are unmodified. Legacy
  readability and modern completion verification are different capabilities:
  a historical manifest may be readable as JSON while `is_scan_complete()`
  returns `False` (not verifiable under the current protocol — not historical
  failure).

* **SCAN-018A-R1 protections preserved:** path-traversal rejection, absolute
  path rejection, symlink-escape rejection, scan ID/directory matching,
  output hashes, output sizes, and required `events.json`.

* **Reserved (not defined/populated):** SCAN-018C field names
  `config_hash`, `config_snapshot_uri`/`param_snapshot`, `frozen_config_ts`;
  SCAN-018E lifecycle values `RUNNING`/`FAILED`/`INTERRUPTED`.

---

## 2. Basis in the actual codebase

### 2.1 Where the manifest is generated

`scanline/scan.py::run_scan` builds and publishes `scanner_data_manifest.json` last (after `events.json`), at scan.py:453-476. The manifest is the completion marker (`status == "COMPLETE"`).

### 2.2 Current manifest fields (top level)

| Field | Type | Source | Status |
|-------|------|--------|--------|
| `scan_id` | str (`YYYYMMDDTHHMMSSffffffZ_<32-hex>`) | `generate_scan_id()` (scan.py:68-76) | Existing (SCAN-018A) |
| `status` | str literal `"COMPLETE"` | hardcoded literal (scan.py:455) | Existing (SCAN-018A) |
| `execution_start` | str ISO-8601 UTC | `_fmt_ts(datetime.now(timezone.utc))` (scan.py:452) | Existing — see §3 |
| `extraction_span` | object `{start, end, end_exclusive}` | globals `EXTRACTION_START_TS`/`EXTRACTION_END_TS` (scan.py:457-461) | Existing |
| `batch_window` | object `{batch_start_ts, batch_end_ts, inclusive}` | function args / module constants (scan.py:462-466) | Existing |
| `series` | array of series-entry objects | `_extract_series` per needed `(symbol, tf)` (scan.py:349-381) | Existing |
| `param_file` | str (basename) | `param_path.name` (scan.py:468) | Existing |
| `param_sha256` | str (64 lowercase hex) | `sha256(raw param file bytes)` (scan.py:469) | Existing |
| `evidence_tier` | str (`forward_asof` / `retrospective_membership`) | derived from `scan_mode` (scan.py:470) | Existing |
| `convention_documents` | array of str | `CONVENTION_DOCS` constant (scan.py:471) | Existing |
| `code_state` | object `{driver_sha256, [commit]}` | `_driver_sha256()` + `_git_head()` (scan.py:448-452, 472) | Existing |
| `outputs` | array of `{name, sha256, size_bytes}` (only `events.json`) | computed after events publish (scan.py:473-475) | Existing (SCAN-018A) |

### 2.3 Series-entry fields (elements of `series`)

| Field | Type | Source |
|-------|------|--------|
| `symbol` | str | `params["universe"]` iteration |
| `timeframe` | str | `params["emission_timeframes"]` + `"D1"` |
| `file` | str (basename) | `f"{symbol}_{tf}.csv"` |
| `sha256` | str (64 hex) | `_sha256_file(path)` |
| `size_bytes` | int | `path.stat().st_size` |
| `bars_extracted` | int | count of bars in extraction window |
| `span` | object `{first_open_ts, last_open_ts}` | first/last bar timestamp or null |

### 2.4 `events.json` header (fields absent from the manifest)

`scanline/scan.py::run_scan` builds `header` at scan.py:411-424:

| Field | Type | Source |
|-------|------|--------|
| `module` | str | `normalize_module_id(params.get("module", "level_proximity"))` |
| `scan_mode` | str | arg |
| `evidence_tier` | str | derived from `scan_mode` |
| `param_file` | str | `param_path.name` |
| `param_sha256` | str | `sha256(raw param file bytes)` |
| `param_version` | str | `params["param_version"]` |
| `frozen_at` | str ISO-8601 UTC | `params["frozen_at"]` |
| `universe` | array of str | `params["universe"]` |
| `emission_timeframes` | array of str | `params["emission_timeframes"]` |
| `definition_timeframe` | str | `params["definition_timeframe"]` |
| `batch_start_ts` | str | arg / constant |
| `batch_end_ts` | str | arg / constant |

### 2.5 Validator result shape

`scanline/validator.py::validate_batch` returns `{"valid": bool, "rule_results": {R1..R5: "pass"/"fail"}, "violations": [...]}` (scanline/validator.py:20-73). `run_scan` raises `RuntimeError` on invalid, so validation always passes when a manifest is written; the manifest can record `validation_status` as `"valid"` plus optional violation count.

### 2.6 Historical manifests

Three historical scan directories under `records/scans/`:

1. `level_proximity-2.0.0-window-2026-05-26_2026-06-24/` — `events.json` + `scanner_data_manifest.json`
2. `level_proximity-2.1.0-window-2026-07-09_2026-08-07/` — `events.json` + `scanner_data_manifest.json`
3. `level_proximity-1.1.0-window-2026-08-08_2026-09-06/` — `events.json` + `scanner_data_manifest.json`

All three contain: `execution_start`, `extraction_span`, `batch_window`, `series`, `param_file`, `param_sha256`, `evidence_tier`, `convention_documents`, `code_state` (`driver_sha256`, `commit`). None contain `scan_id`, `status`, `outputs`, or `manifest_version`. Historical manifest example (2.1.0) at `records/scans/level_proximity-2.1.0-window-2026-07-09_2026-08-07/scanner_data_manifest.json`.

The `events.json` header for that scan carries `"event_count"`-relevant data: 4624 events, `"module": "module_1"`, `"scan_mode": "retrospective"`, `"param_version": "2.1.0"`, `"frozen_at": "2026-11-20T03:09:46Z"`, `"universe"` (34 symbols), `"emission_timeframes": ["H1","H4"]`.

---

## 3. Proposed manifest schema

### 3.1 Design principles

- Additive only; do not remove or redefine existing fields.
- Do not duplicate data already authoritative elsewhere (`events.json` header holds the full param snapshot; `series` holds input provenance).
- One top-level schema version field; unknown fields ignored (forward-compatible).
- Required vs optional explicitly distinguished; no field has contradictory classifications across §3, §4, §5.
- `is_scan_complete()` remains the lightweight completion check; deep integrity (rehashing corpus, re-validating R1–R5, content-canonical param hashing) belongs to a separate audit operation / SCAN-018C.
- Reserve SCAN-018C field names without defining canonical hashing or snapshot semantics.
- Wall-clock fields differ across repeated identical scans; the manifest is not byte-reproducible on these fields. `events.json` remains byte-reproducible.

### 3.2 Full proposed manifest (annotated example)

```json
{
  "manifest_version": "1.0.0",
  "scan_id": "20261121T013740123456Z_abcdef0123456789abcdef0123456789",
  "status": "COMPLETE",
  "scan_start": "2026-11-21T01:37:40.123456Z",
  "execution_start": "2026-11-21T01:37:45.987654Z",
  "outputs_complete_at": "2026-11-21T01:37:45.123456Z",
  "module": "level_proximity",
  "scan_mode": "forward",
  "param_file": "scanner_params.level_proximity.json",
  "param_sha256": "1181255cfb1b9529211ec3df2c9dd725748c7079775d20fc2d288673b4e6c6fb",
  "param_version": "1.0.0",
  "frozen_at": "2026-11-19T03:25:04Z",
  "universe": ["GOLD", "EURUSD", "USDCAD", "GER40", "USOIL"],
  "emission_timeframes": ["H1", "H4"],
  "series": [
    { "symbol": "GOLD", "timeframe": "D1", "file": "GOLD_D1.csv", "sha256": "...", "size_bytes": 21727, "bars_extracted": 26, "span": {"first_open_ts": "...", "last_open_ts": "..."} }
  ],
  "total_bars_extracted": 26,
  "event_count": 0,
  "validation_status": "valid",
  "validation_violation_count": 0,
  "evidence_tier": "forward_asof",
  "code_state": { "driver_sha256": "...", "commit": "..." },
  "convention_documents": ["docs/freezes/level_proximity-1.0.0.md", ...],
  "extraction_span": { "start": "...", "end": "...", "end_exclusive": true },
  "batch_window": { "batch_start_ts": "...", "batch_end_ts": "...", "inclusive": true },
  "outputs": [ { "name": "events.json", "sha256": "...", "size_bytes": 1234 } ]
}
```

Note on timestamp ordering in the example: `scan_start` (invocation) ≤ `outputs_complete_at` (outputs durable) ≤ `execution_start` (manifest preparation/publication).

### 3.3 Field layout by logical section

| Section | Field | Type | Required? | Disposition |
|---------|-------|------|-----------|-------------|
| Identity | `manifest_version` | str (`^\d+\.\d+\.\d+$`) | Yes | New — reserves schema version |
| Identity | `scan_id` | str (SCAN_ID_RE) | Yes | Existing (SCAN-018A) |
| Identity | `status` | str (`"COMPLETE"`; reserved `RUNNING`/`FAILED`/`INTERRUPTED`) | Yes | Existing (SCAN-018A) |
| Execution | `scan_start` | str ISO-8601 UTC | Yes | New — actual scan invocation time (captured at `run_scan` entry; required for v1.0.0) |
| Execution | `execution_start` | str ISO-8601 UTC | Yes | Existing — manifest-preparation/publication wall clock (corrected meaning, §3) |
| Execution | `outputs_complete_at` | str ISO-8601 UTC | Yes | New — processing/output completion (captured after `events.json` is durable; required for v1.0.0) |
| Execution | `module` | str | Yes | Minor change (from `events.json` header) |
| Execution | `scan_mode` | str (`forward`/`retrospective`) | Yes | Minor change (from arg/header) |
| Configuration | `param_file` | str | Yes | Existing |
| Configuration | `param_sha256` | str (64 hex) | Yes | Existing |
| Configuration | `param_version` | str | Yes | Minor change (from header) |
| Configuration | `frozen_at` | str ISO-8601 UTC | Yes | Minor change (from header) |
| Coverage | `universe` | array of str | Yes | Minor change (summary from header) |
| Coverage | `emission_timeframes` | array of str | Yes | Minor change (summary from header) |
| Coverage | `series` | array | Yes | Existing |
| Coverage | `total_bars_extracted` | int (>=0) | No | Minor change (sum of `series[].bars_extracted`) |
| Processing results | `event_count` | int (>=0) | Yes | New (`len(all_events)`) |
| Processing results | `validation_status` | str (`"valid"`/`"invalid"`) | Yes | Minor change (validation result) |
| Processing results | `validation_violation_count` | int (>=0) | No | New instrumentation (`len(violations)`) |
| Output integrity | `outputs` | array `{name, sha256, size_bytes}` | Yes | Existing (SCAN-018A) |
| Code state | `code_state` | object `{driver_sha256, [commit]}` | Yes (`driver_sha256`); `commit` optional | Existing |
| Reference | `convention_documents` | array of str | No | Existing; always populated by current writer but not contract-required |
| Reference | `extraction_span` | object | No | Existing; always populated by current writer but not contract-required |
| Reference | `batch_window` | object | No | Existing; always populated by current writer but not contract-required |
| Reference | `evidence_tier` | str | Yes | Existing |

"Required" means the v1.0.0 consumer contract treats absence as a contract violation for new manifests. "Optional" means absence is tolerated (notably for legacy records); the current writer still populates these fields whenever the data exists. No field is classified differently in §3.3, §4, or §5.

### 3.4 Fields reserved for SCAN-018C (do not define or populate here)

- `config_hash` — content-canonical parameter hash (SCAN-018C).
- `config_snapshot_uri` / `param_snapshot` — stored parameter snapshot (SCAN-018C).
- `frozen_config_ts` — distinct from `frozen_at` if SCAN-018C defines a freeze operation (currently `frozen_at` is a param-file content field, not an operation timestamp).

SCAN-018B may reserve field names but must not define canonical hashing or snapshot semantics.

---

## 4. Field-by-field specification

Each field below documents: exact name, data type, required/optional, source of truth, when generated, validation rules, independent verifiability, and whether new instrumentation is required. "Existing" means the field or its source already exists in `scanline/scan.py`; "New" means proposed instrumentation.

### 4.1 Identity section

**`manifest_version`**
- Type: str (`^\d+\.\d+\.\d+$`, e.g. `"1.0.0"`)
- Required: Yes
- Source of truth: module constant in `scanline/scan.py`
- Generated: at manifest publication (scan.py:453)
- Validation: matches semver-like regex; major == 1 for current contract; unknown major rejected by consumers (§5)
- Independently verifiable: Yes — compare against declared contract constant
- New instrumentation: Yes (none exists today)

**`scan_id`**
- Type: str (`YYYYMMDDTHHMMSSffffffZ_<32-hex>`)
- Required: Yes
- Source of truth: `generate_scan_id()` (scan.py:68-76)
- Generated: once per `run_scan` execution, retained throughout
- Validation: matches `SCAN_ID_RE`; equals containing directory name (existing `is_scan_complete()` check)
- Independently verifiable: Yes — equals directory name
- New instrumentation: No (existing SCAN-018A)

**`status`**
- Type: str literal
- Required: Yes
- Source of truth: literal in `run_scan`
- Generated: at manifest publication; `"COMPLETE"` only in SCAN-018B; `RUNNING`/`FAILED`/`INTERRUPTED` reserved (SCAN-018E coordinates lifecycle persistence)
- Validation: must equal `"COMPLETE"` for complete scans; reserved values permitted syntactically
- Independently verifiable: Yes — constant
- New instrumentation: No (existing SCAN-018A)

### 4.2 Execution section

**`scan_start`**
- Type: str ISO-8601 UTC (`...Z`)
- Required: Yes (v1.0.0; binding SCAN-018B requirement)
- Source of truth: `_fmt_ts(datetime.now(timezone.utc))` captured at `run_scan` entry (before scan-ID generation)
- Generated: at scan invocation — the first wall-clock capture of `run_scan`
- Validation: non-empty ISO-8601 UTC string; <= `outputs_complete_at` and <= `execution_start`
- Independently verifiable: No — wall clock, not reproducible
- New instrumentation: Yes

**`execution_start`**
- Type: str ISO-8601 UTC (`...Z`)
- Required: Yes
- Source of truth: `_fmt_ts(datetime.now(timezone.utc))` (scan.py:452)
- Generated: immediately before manifest dict construction, **after** extraction, event processing, validation, and `events.json` publication
- Meaning: manifest-preparation/publication wall clock. **Not** scan invocation time and **not** event-processing completion time. Historical meaning preserved — the same capture point existed in SCAN-018A and earlier code, so historical `execution_start` values carry the same meaning.
- Validation: non-empty ISO-8601 UTC string
- Independently verifiable: No — wall clock, not reproducible
- New instrumentation: No (existing)

**`outputs_complete_at`**
- Type: str ISO-8601 UTC
- Required: Yes (v1.0.0; binding SCAN-018B requirement)
- Source of truth: `_fmt_ts(datetime.now(timezone.utc))` captured after `events.json` is durable and its hash/size are recorded (after scan.py:442-444)
- Generated: at processing/output completion — all declared outputs are durable before the manifest is published
- Validation: non-empty ISO-8601 UTC string; >= `scan_start` and <= `execution_start`
- Independently verifiable: No — wall clock, not reproducible
- New instrumentation: Yes

**`module`**
- Type: str
- Required: Yes
- Source of truth: `normalize_module_id(params.get("module", "level_proximity"))` (scan.py:323); already in `events.json` header (scan.py:412)
- Generated: at manifest publication
- Validation: non-empty string; must match `events.json` header `module` if both present (lightweight cross-check)
- Independently verifiable: Yes — from params file
- New instrumentation: No — minor change (copy header value into manifest)

**`scan_mode`**
- Type: str (`forward`/`retrospective`)
- Required: Yes
- Source of truth: `scan_mode` arg (scan.py:295); already in `events.json` header (scan.py:413)
- Generated: at manifest publication
- Validation: must be `"forward"` or `"retrospective"`; must match `events.json` header `scan_mode` if both present
- Independently verifiable: Yes — from function arg / params
- New instrumentation: No — minor change (copy header value into manifest)

### 4.3 Coverage section

**`universe`**
- Type: array of str
- Required: Yes
- Source of truth: `params["universe"]` (scan.py:339); already in `events.json` header (scan.py:419)
- Generated: at manifest publication
- Validation: non-empty array of strings; implicit consistency with `series` entries (symbols in `series` ⊆ universe)
- Independently verifiable: Yes — from params file
- New instrumentation: No — minor change (copy header value into manifest)

**`emission_timeframes`**
- Type: array of str
- Required: Yes
- Source of truth: `params["emission_timeframes"]` (scan.py:340); already in `events.json` header (scan.py:420)
- Generated: at manifest publication
- Validation: non-empty array of strings; implicit consistency with `series` entries
- Independently verifiable: Yes — from params file
- New instrumentation: No — minor change (copy header value into manifest)

**`series`**
- Type: array of objects
- Required: Yes
- Source of truth: `_extract_series` per needed `(symbol, tf)` (scan.py:349-381)
- Generated: during extraction phase
- Validation: non-empty; each entry has valid `symbol`, `timeframe`, `file`, `sha256`, `size_bytes`, `bars_extracted`, `span`
- Independently verifiable: Yes — re-parse corpus CSV, rehash, stat
- New instrumentation: No (existing)

**`total_bars_extracted`**
- Type: int (>=0)
- Required: No
- Source of truth: `sum(entry["bars_extracted"] for entry in series)`
- Generated: after `series` built
- Validation: non-negative integer; equals sum of `series[].bars_extracted`
- Independently verifiable: Yes — recomputable from `series`
- New instrumentation: No — derived from existing `series` (adds summary field only)

### 4.4 Configuration section

**`param_file`**
- Type: str (basename)
- Required: Yes
- Source of truth: `param_path.name` (scan.py:468); already in header (scan.py:415)
- Generated: at manifest publication
- Validation: non-empty string; matches `events.json` header `param_file` if both present
- Independently verifiable: Only if param file retained
- New instrumentation: No (existing)

**`param_sha256`**
- Type: str (64 lowercase hex)
- Required: Yes
- Source of truth: `sha256(raw param file bytes)` (scan.py:469); already in header (scan.py:416)
- Generated: at manifest publication
- Validation: matches `SHA256_HEX_RE`
- Independently verifiable: Only if param file retained; byte-based, not content-canonical (SCAN-018C)
- New instrumentation: No (existing)

**`param_version`**
- Type: str
- Required: Yes
- Source of truth: `params["param_version"]` (scan.py:417 in header)
- Generated: at manifest publication
- Validation: non-empty string; matches `events.json` header `param_version` if both present
- Independently verifiable: Yes — from params file
- New instrumentation: No — minor change (copy header value into manifest)

**`frozen_at`**
- Type: str ISO-8601 UTC
- Required: Yes
- Source of truth: `params["frozen_at"]` (scan.py:418 in header)
- Generated: at manifest publication
- Validation: non-empty ISO-8601 UTC string; matches `events.json` header `frozen_at` if both present
- Independently verifiable: Yes — from params file
- New instrumentation: No — minor change (copy header value into manifest)

### 4.5 Processing results section

**`event_count`**
- Type: int (>=0)
- Required: Yes
- Source of truth: `len(all_events)` (scan.py:384-407)
- Generated: after event collection, before validation
- Validation: non-negative integer; equals number of event objects in `events.json` (lightweight check in `is_scan_complete()`)
- Independently verifiable: Yes — load `events.json`, count `events` array
- New instrumentation: Yes (stored count; computable today but not persisted)

**`validation_status`**
- Type: str (`"valid"` / `"invalid"`)
- Required: Yes
- Source of truth: `validate_batch(...)` result `["valid"]` (scanline/validator.py:69)
- Generated: after validation, before manifest write
- Validation: must be `"valid"` when a COMPLETE manifest is written (run_scan raises on invalid today); `"invalid"` reserved for future failure-recording behavior
- Independently verifiable: Partially — presence check only in `is_scan_complete()`; re-validation belongs to audit
- New instrumentation: No — derived from existing validation result (record it)

**`validation_violation_count`**
- Type: int (>=0)
- Required: No
- Source of truth: `len(result["violations"])` (scanline/validator.py:53-55)
- Generated: after validation
- Validation: non-negative integer
- Independently verifiable: Partially — re-running validation reproduces violations (audit operation)
- New instrumentation: Yes (not stored today)

### 4.6 Output integrity section (SCAN-018A contract preserved)

**`outputs`**
- Type: array of `{name, sha256, size_bytes}`
- Required: Yes
- Source of truth: computed after events publish (scan.py:473-475)
- Generated: after each output is durable
- Validation: nonempty list; valid simple relative filenames; valid SHA-256; valid non-negative integer sizes; no duplicates; `events.json` declared; each exists inside scan dir and matches hash/size (existing `is_scan_complete()`)
- Independently verifiable: Yes — rehash files, stat sizes
- New instrumentation: No (existing SCAN-018A)

### 4.7 Code state / reference sections (existing, unchanged)

**`code_state`** — object `{driver_sha256, [commit]}`; Required: Yes (`driver_sha256`); `commit` optional; Source: `_driver_sha256()` + `_git_head()`; Existing.
**`convention_documents`** — array of str; Required: No; Source: `CONVENTION_DOCS`; Existing.
**`extraction_span`** — object `{start, end, end_exclusive}`; Required: No; Source: globals; Existing.
**`batch_window`** — object `{batch_start_ts, batch_end_ts, inclusive}`; Required: No; Source: args/constants; Existing.
**`evidence_tier`** — str; Required: Yes; Source: derived from `scan_mode`; Existing.

---

## 5. Schema versioning strategy

### 5.1 Version field

Top-level `manifest_version: str`, semantic-version-like, format `^\d+\.\d+\.\d+$` (e.g. `"1.0.0"`). Declared as a module constant in `scanline/scan.py` and emitted by every writer.

### 5.2 Major-version compatibility

Major versions denote the contract generation. Changing the major version is a breaking change (field removal, redefinition, or a change to the required-field set). A consumer that understands major `1` verifies the v1.0.0 contract; a manifest whose `manifest_version` major is not understood is **rejected as incomplete** — it is not treated as a failed scan, because the consumer cannot verify an unknown contract.

### 5.3 Minor- and patch-version compatibility

Minor and patch versions are additive only: new optional fields, clarifications, or reserved names. No version increment is required when a newly optional field is added — optional fields are additive and unknown fields are ignored on read (§5.4). A version bump is required only when a field is promoted from optional to required, a field is removed or redefined, or the required-field set changes (that is a major change by §5.2). Patch changes are editorial (documentation/clarification) and receive the same compatibility treatment as minor changes.

### 5.4 Unknown-field behavior

Ignore unknown fields on read (forward compatibility). Writers must not emit fields newer than the declared `manifest_version` without bumping the version.

### 5.5 Required vs optional (v1.0.0)

Required: `manifest_version`, `scan_id`, `status`, `execution_start`, `scan_start`, `outputs_complete_at`, `module`, `scan_mode`, `series`, `param_file`, `param_sha256`, `param_version`, `frozen_at`, `universe`, `emission_timeframes`, `event_count`, `validation_status`, `evidence_tier`, `code_state.driver_sha256`, `outputs` (nonempty, `events.json` declared).

Per the SCAN-018B binding requirement, `scan_start` and `outputs_complete_at` are required for new v1.0.0 manifests (they are captured by the writer at `run_scan` entry and after `events.json` is durable, respectively).

Optional: `total_bars_extracted`, `validation_violation_count`, `code_state.commit`, `convention_documents`, `extraction_span`, `batch_window`.

A missing optional field in a modern manifest is a data-quality signal, not automatically a failed scan (especially for legacy records).

### 5.6 Forward/backward compatibility

- Legacy (pre-SCAN-018A) manifests: no `manifest_version`, no `scan_id`/`status`/`outputs`. Readable; consumers requiring `status == "COMPLETE"` treat them as incomplete. A missing modern field must NOT be treated as proof an old scan failed.
- SCAN-018A manifests: have `scan_id`, `status == "COMPLETE"`, `outputs` with hashes and sizes; lack `manifest_version` and newer fields. Retain the original SCAN-018A verification path (§8).
- New manifests: include `manifest_version`; optional fields additive.
- Future fields: added as optional first, promoted to required only with a version bump and a migration/coexistence period.
- Unsupported future versions: a manifest whose `manifest_version` major version is not understood is rejected as incomplete (consumer cannot verify the contract); it is not treated as a failed scan.
- Historical manifests must remain readable. Do not modify or backfill historical records.

---

## 6. Manifest lifecycle

Evaluate `RUNNING`, `COMPLETE`, `FAILED`, `INTERRUPTED`. SCAN-018E will handle concurrency and recovery; SCAN-018B only reserves the vocabulary and specifies meaning.

| State | Meaning | Persisted? | Transitions |
|-------|---------|------------|-------------|
| `RUNNING` | Publication in progress | Optional (manifest written early, rewritten to COMPLETE) | → `COMPLETE` on success; → `FAILED`/`INTERRUPTED` on error |
| `COMPLETE` | All required outputs written and manifest durable | Yes — final manifest rename | Terminal; the completion marker |
| `FAILED` | Scan failed validation or serialization | Optional — written on caught exception before re-raise | Terminal |
| `INTERRUPTED` | Publication interrupted (signal/KeyboardInterrupt) | Optional — written on signal handler | Terminal |

- SCAN-018B minimum viable contract: only `COMPLETE` is persisted (manifest written once, last). Absence of a manifest, or any other status/missing status, means incomplete.
- `RUNNING`/`FAILED`/`INTERRUPTED` are reserved for SCAN-018E to avoid conflicting manifest designs.
- Incomplete scans are identified by: no manifest, manifest without `status == "COMPLETE"`, or `is_scan_complete()` returning `False`.
- The final completion marker is the manifest rename with `status == "COMPLETE"` published after all outputs are durable.
- No lifecycle changes are implemented in this milestone.

---

## 7. Completion verification

### 7.1 Basic completion verification — `is_scan_complete()`

`is_scan_complete(dest)` should check (preserving all existing SCAN-018A-R1 protections):

1. Manifest exists, parses as JSON, is an object.
2. `manifest_version` present and parseable (lightweight; major version understood).
3. `status == "COMPLETE"`.
4. Scan identity: `scan_id` valid SCAN_ID_RE and equals containing directory name.
5. Required fields present (per §5.5).
6. Output inventory: `outputs` nonempty; valid names/hashes/sizes; no duplicates; `events.json` declared.
7. Output hashes and sizes match on disk (existing rehash + stat).
8. `event_count` == `len(events)` in `events.json` (cheap; requires `event_count` field).
9. Lightweight cross-field consistency: `module`/`scan_mode`/`param_version`/`frozen_at` match `events.json` header (presence/type checks only).

Preserve all SCAN-018A-R1 path-traversal and symlink protections (`_is_safe_output_name`, `_is_within_directory`, scan_id/dir-name match, no vacuous empty `outputs`, `events.json` required). Read-only: never creates, modifies, or deletes files.

### 7.2 Deeper integrity audit (separate operation, NOT `is_scan_complete()`)

- Recompute input `series[].sha256`/`size_bytes` from corpus.
- Recompute `param_sha256` against retained param file.
- Content-canonical parameter hash verification (SCAN-018C).
- Full R1–R5 re-validation of `events.json`.
- Recompute `event_count` and `events_by_type` from scratch.
- Re-derive `param_version`/`frozen_at` consistency against params file.

Rationale: `is_scan_complete()` is a fast, read-only consumer gate. A deep audit re-reads the corpus and re-runs validation — appropriate for a separate audit command, not for every consumer read.

---

## 8. Historical compatibility

### 8.1 Two legacy categories

**Category A — Pre-SCAN-018A historical manifests.**
- Missing `scan_id`.
- Missing `status`.
- Missing `outputs`.
- Missing `manifest_version`.
- The three directories under `records/scans/` (§2.6) fall in this category.
- Remain readable as JSON but cannot be verified as complete under the new protocol. `is_scan_complete()` returns `False` (no `status == "COMPLETE"`, no `scan_id`, no `outputs`). That means "cannot be verified under the new completion protocol," **not** "the historical scan failed."

**Category B — SCAN-018A manifests.**
- Have `scan_id` (valid SCAN_ID_RE, equals containing directory name).
- Have `status == "COMPLETE"`.
- Have `outputs` with `name`/`sha256`/`size_bytes` (`events.json` declared and verified).
- Lack `manifest_version` and the newer SCAN-018B fields.
- Produced by the current writer (post-SCAN-018A, pre-SCAN-018B).
- Recommendation: retain their original SCAN-018A verification path — verify via `status == "COMPLETE"` + scan identity + output inventory + hash/size checks, **without** requiring `manifest_version`. They are verifiable as complete under SCAN-018A and incomplete under the v1.0.0 contract (which requires `manifest_version`).

### 8.2 New SCAN-018B manifests

Must satisfy the complete versioned contract (§5.5): `manifest_version` plus every required field. Optional fields are additive.

### 8.3 Rules

- Historical records remain readable; `is_scan_complete()` returns `False` for both legacy categories without treating either as a failed scan.
- No migration, no backfill, no modification of historical records.
- Category B keeps its SCAN-018A path; new manifests are gated by the full v1.0.0 contract.
- Optional fields missing from legacy records are tolerated; required modern fields absent ⇒ legacy/incomplete under the new protocol, not failed.

---

## 9. SCAN-018C dependencies

SCAN-018B may reserve manifest fields for SCAN-018C without implementing canonical hashing or snapshots:

- `config_hash` — content-canonical parameter hash (replaces/complements raw-bytes `param_sha256`).
- `config_snapshot_uri` / `param_snapshot` — stored parameter snapshot.
- `frozen_config_ts` — freeze operation timestamp (distinct from `frozen_at`, which is a param-file content field).

Responsibility split:

**SCAN-018B:** manifest structure, field definitions, validation contract, output and result metadata.
**SCAN-018C:** canonical parameter hashing, parameter snapshots, parameter-version/content binding, historical configuration provenance.

The existing `param_sha256` (raw-bytes) remains in v1.0.0; SCAN-018C may add a canonical hash alongside it.

---

## 10. Test strategy

Proposed regression tests (do not add yet). All use `tmp_path`; no historical records touched.

1. Valid new manifest — complete manifest with all required fields passes schema validation / `is_scan_complete()`.
2. Missing required fields — manifest missing any required field (§5.5) is rejected.
3. Invalid field types — wrong types (e.g. `size_bytes` as string, `outputs` as string, `duration_ms`/`validation_violation_count`/`total_bars_extracted` as bool) rejected.
4. Unsupported manifest versions — unknown major `manifest_version` handled gracefully (rejected as incomplete); absent version treated as legacy.
5. Event count consistency — `event_count` matches `len(events)` in `events.json`.
6. Output inventory consistency — `outputs` matches files on disk (name/sha256/size).
7. Validation information — `validation_status`/`validation_violation_count` consistent with validator output.
8. Legacy category A (pre-SCAN-018A) — historical-shaped manifest (no `scan_id`/`status`/`outputs`/`manifest_version`) is readable; `is_scan_complete()` returns `False` without treating it as a failed scan.
9. Legacy category B (SCAN-018A) — manifest with `scan_id`, `status == "COMPLETE"`, `outputs` with hashes/sizes but no `manifest_version` verifies via the SCAN-018A path and is incomplete under v1.0.0.
10. Incomplete scan states — `RUNNING`/`FAILED`/`INTERRUPTED`/absent manifests treated as incomplete; `COMPLETE` required.
11. Manifest/event-header consistency — `module`/`scan_mode`/`param_version`/`frozen_at` match `events.json` header.
12. Corrupted output references — missing/truncated output file, hash mismatch, size mismatch, traversal/symlink escape all rejected (SCAN-018A-R1 preserved).
13. Timestamp ordering — `scan_start` ≤ `outputs_complete_at` ≤ `execution_start` when all three are present.

---

## 11. Implementation sequence

Break into small, independently testable changes.

1. Approve the manifest contract and schema-versioning strategy (this document). Coordinate with SCAN-018C on reserved field names (`config_hash`, `param_version`, `frozen_at`).
2. Instrument `run_scan` timestamps (scan.py): capture `scan_start` at function entry (before scan-ID generation), capture `outputs_complete_at` after `events.json` is durable and hashed (after scan.py:442-444), keep `execution_start` at scan.py:452 immediately before manifest dict construction with its corrected meaning (manifest-preparation/publication wall clock).
3. Add `manifest_version` constant and emit it in the manifest dict (`run_scan`, scan.py:453-476).
4. Add SCAN-018B fields to `run_scan` manifest construction: `module`, `scan_mode`, `param_version`, `frozen_at`, `universe`, `emission_timeframes`, `event_count`, `validation_status`, optional `scan_start`, `outputs_complete_at`, `total_bars_extracted`, `validation_violation_count`.
5. Extend `is_scan_complete()` with `manifest_version` presence/parse, `event_count` consistency, and validation-status presence checks (lightweight; no corpus rehash). Preserve SCAN-018A-R1 protections and the SCAN-018A verification path for category-B legacy manifests.
6. Add tests §10 cases 1–13 using `tmp_path`.
7. Run `python3 -m pytest -q`; verify baseline plus new tests pass.
8. Document the contract in `scanline/scan.py` docstring and cross-reference `docs/SCAN-017-CONTRACT-DECISIONS.md`.
9. Request implementation approval before step 2 if not already granted.

### 11.1 Dependencies

- SCAN-018A (scan ID, `status`, `outputs`, `is_scan_complete()`) — in place.
- SCAN-018C coordination — reserved field names only; no implementation dependency.
- SCAN-018E — lifecycle persistence (`RUNNING`/`FAILED`/`INTERRUPTED`); not implemented here.

### 11.2 Compatibility risks

- Consumer gate tightens legacy out: `is_scan_complete()` returning `False` for historical manifests is correct under the new protocol but must not be interpreted as historical failure. Documentation must state this.
- Byte-hash vs content-hash divergence: `param_sha256` is raw-bytes; SCAN-018C canonical hashing could introduce a second hash without invalidating the existing one.
- `run_scan` return value: already changed from `None` to `scan_id` in SCAN-018A; no in-repo caller uses the return.
- Output location: SCAN-018A writes into `<output_dir>/<scan_id>/`; callers locate artifacts via returned `scan_id`. Manifest contract must not assume flat layout.
- Wall-clock non-reproducibility: `scan_start`/`execution_start`/`outputs_complete_at` differ across repeated identical scans; manifest is not byte-reproducible on these fields. `events.json` remains byte-reproducible.
- No lint/typecheck tooling: `pyproject.toml` configures pytest only; no ruff/mypy/black to run as pre-commit gates.

### 11.3 Expected changed files (future implementation only)

| File | Likely change |
|------|---------------|
| `scanline/scan.py` | Timestamp instrumentation (`scan_start`, `outputs_complete_at`, corrected `execution_start`); add `manifest_version` + new fields to manifest dict (`run_scan`, ~scan.py:453-476); extend `is_scan_complete()` with version/event-count/validation checks; preserve SCAN-018A-R1 protections and SCAN-018A legacy path |
| `tests/test_scan.py` | New tests for manifest schema, missing fields, type validation, event-count consistency, output-inventory consistency, version handling, legacy compatibility (categories A and B), corrupted outputs, timestamp ordering |
| `docs/SCAN-018B-MANIFEST-PROPOSAL.md` | This document (proposal deliverable) |
| `docs/SCAN-017-CONTRACT-DECISIONS.md` | Optional cross-reference |

**Files NOT to change (per restrictions):** `scanline/validator.py`, `scanline/levels.py`, `scanline/sessions.py`, `scanline/schema.py`, `scanline/validation/*`, `config/*`, `records/*`, corpus datasets, and the SCAN-016/017/018 proposal/recon documents. No source, test, config, or historical-record modification is authorized in this proposal phase.

---

## 12. Risks and unresolved decisions

### 12.1 Risks

- **Semantic drift of `param_version`/`frozen_at`:** these are currently param-file content fields, not operation timestamps. SCAN-018C may redefine `frozen_at` as a freeze-operation timestamp, creating ambiguity. SCAN-018B documents that v1.0.0 `frozen_at` == param-file content field and reserves `frozen_config_ts` for SCAN-018C.
- **`validation_status` always `"valid"`:** since `run_scan` raises on invalid, every COMPLETE manifest records `"valid"`. The field is still valuable as a forward-compatible record, but its discriminative power is limited until failure-recording behavior (SCAN-018E) exists.
- **Wall-clock fields break byte-reproducibility of the manifest:** acceptable and documented; `events.json` determinism is preserved.
- **`execution_start` misinterpretation risk:** consumers may mistake `execution_start` for scan start or event-processing completion. §4.2 documents its actual meaning (manifest-preparation/publication wall clock) and the new `scan_start`/`outputs_complete_at` fields carry the other two moments.

### 12.2 Unresolved decisions (require implementation approval / coordination)

- Exact names of the new timestamp fields (`scan_start`, `outputs_complete_at`) — proposed here; confirm at implementation.
- Whether `evidence_tier` should be required given it is derivable from `scan_mode` (proposal: required, existing field).
- Whether `code_state.commit` stays optional when git is unavailable (proposal: optional, `driver_sha256` required).
- Exact reserved field names for SCAN-018C (`config_hash` vs `param_hash`, `param_snapshot` vs `config_snapshot_uri`).
- Whether `events_by_type` is deferred entirely to SCAN-018C/audit (proposal: defer).

---

## 13. Deliverable

Created: `docs/SCAN-018B-MANIFEST-PROPOSAL.md` (this document).

Summary of recommendations:

1. Adopt the versioned manifest contract in §3–§5: add `manifest_version` ("1.0.0"), keep all SCAN-018A fields, add execution metadata (`scan_start`, `outputs_complete_at`; `execution_start` retained with corrected manifest-preparation meaning), execution-config (`module`, `scan_mode`, `param_version`, `frozen_at`, `universe`, `emission_timeframes`), coverage summary (`total_bars_extracted`), and processing-result (`event_count`, `validation_status`, optional `validation_violation_count`) fields. Drop the misleading `execution_end`/`duration_ms` pair.
2. Correct required/optional field matrix (§3.3, §4, §5.5) with no contradictory classifications; required set = `manifest_version`, `scan_id`, `status`, `execution_start`, `module`, `scan_mode`, `series`, `param_file`, `param_sha256`, `param_version`, `frozen_at`, `universe`, `emission_timeframes`, `event_count`, `validation_status`, `evidence_tier`, `code_state.driver_sha256`, `outputs`.
3. Preserve the SCAN-018A output-integrity contract (`outputs` with `name`/`sha256`/`size_bytes`) and all path-traversal/symlink protections unchanged.
4. Two-tier historical compatibility (§8): Category A (pre-SCAN-018A, missing `scan_id`/`status`/`outputs`/`manifest_version`) readable but unverifiable; Category B (SCAN-018A, has `scan_id`/`status`/`outputs`, lacks `manifest_version`) retains its SCAN-018A verification path. Never modify historical records.
5. Reserve SCAN-018C field names (`config_hash`, `config_snapshot_uri`/`param_snapshot`, `frozen_config_ts`) without defining canonical hashing or snapshot semantics.
6. Keep `is_scan_complete()` lightweight: version/required-fields/identity/status/output-inventory/hashes/sizes + cheap `event_count` and header-consistency checks. Defer corpus rehash and full R1–R5 re-validation to a separate integrity-audit operation.
7. Versioning (§5): format `^\d+\.\d+\.\d+$`; major = breaking (unknown majors rejected as incomplete); minor/patch additive (new optional fields never require a version increment); absent version = legacy.
8. Implement only after explicit approval; coordinate with SCAN-018C on reserved fields and SCAN-018E on lifecycle persistence before adding `RUNNING`/`FAILED`/`INTERRUPTED` writes.

No implementation is performed or authorized by this document. Await explicit implementation approval.
