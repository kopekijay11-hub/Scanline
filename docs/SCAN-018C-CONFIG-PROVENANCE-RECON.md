# SCAN-018C — Configuration Provenance & Content Hash Reconnaissance

**Mode:** READ-ONLY reconnaissance. No implementation authorized. No repository files modified except this report.

**Date:** 2026-11-21  
**Repository:** `/home/joshua/scanline`  
**Baseline commit:** `ef1f73b2f3412c15b1662f4024ad56976ab0cce8` (`main`, matches `origin/main`)  
**Working tree:** clean except pre-existing untracked proposal/docs: `docs/SCAN-016-PROPOSAL.md`, `docs/SCAN-016B-PROPOSAL.md`, `docs/SCAN-017F-DUPLICATE-IMPLEMENTATION-PROPOSAL.md`, `docs/SCAN-018-RECON.md`  
**Expected test baseline:** `243 passed, 1 skipped` (not executed in this recon; `pyproject.toml` declares pytest; prior SCAN-018B baseline recorded in docs as 216 passed, 1 skipped)

---

## 1. Current parameter pipeline

Traced end-to-end from CLI to persisted artifacts.

| Step | Current behavior | Code reference |
|------|------------------|----------------|
| 1. Configuration file selection | `run_scan` accepts `param_path`; default is `repo_root/config/scanner_params.level_proximity.json`. CLI `--param-file` overrides. | `scanline/scan.py:520-523,705-723` |
| 2. Raw file loading | `params_bytes = param_path.read_bytes()`; raw bytes preserved. | `scanline/scan.py:524` |
| 3. JSON parsing | `params = json.loads(params_bytes)`. No canonicalization. | `scanline/scan.py:525` |
| 4. Schema/param validation (pre-scan) | Module normalized via `normalize_module_id`. Scan mode checked. Module-specific runtime/config validation happens in module compute/config paths (`_validate_params` in levels, `validate_session_config` in sessions) and in R4 for session anomalies. No standalone config schema validator before scan besides parse + runtime checks. | `scanline/scan.py:526-529`, `scanline/levels.py:47-83`, `scanline/sessions.py:114-220,479-520`, `scanline/validation/r4.py:89-93` |
| 5. Parameter normalization | Only module ID alias normalization at boundary (`module_1` -> `level_proximity`); param content not canonicalized. | `scanline/schema.py:98-109`, `scanline/scan.py:526` |
| 6. Parameter freezing | No freeze operation in scanner. `frozen_at` and `param_version` are read from param file and treated as authoritative metadata. R4 enforces `frozen_at` strictly before first event for forward scans. | `scanline/scan.py:620-621`, `scanline/validation/r4.py:67-87` |
| 7. Hash calculation | Raw-byte SHA-256: `hashlib.sha256(params_bytes).hexdigest()`. Same value written to header and manifest. | `scanline/scan.py:619,669` |
| 8. Header generation | `events.json` header includes `module, scan_mode, evidence_tier, param_file, param_sha256, param_version, frozen_at, universe, emission_timeframes, definition_timeframe, batch_start_ts, batch_end_ts`. | `scanline/scan.py:614-627`, `scanline/schema.py:54-67` |
| 9. Manifest generation | Manifest v1.0.0 includes `param_file, param_sha256, param_version, frozen_at` plus execution/coverage/integrity fields; `outputs` includes `events.json` hash/size; manifest published last as COMPLETE marker. | `scanline/scan.py:659-698`, `scanline/scan.py:368-453` |
| 10. Historical scan association | Historical scans store manifest + events header param metadata and code state; no stored param snapshot; no config_hash field. Historical manifest `param_sha256`/header hash currently do **not** match current bytes of same-named config files in `config/`. | `records/scans/*/scanner_data_manifest.json`, `records/scans/*/events.json`, observed hash comparison below |

### Observed current artifacts

- Config files: `config/scanner_params.level_proximity.json` (v1.0.0), `-1.1.0.json`, `-2.0.0.json`, `-2.1.0.json`.
- Historical scan dirs: `records/scans/level_proximity-1.1.0-window-2026-08-08_2026-09-06`, `...2.0.0-window-2026-05-26_2026-06-24`, `...2.1.0-window-2026-07-09_2026-08-07`.
- Current config byte hashes differ from historical recorded hashes for same-named files:
  - 1.1.0 recorded `53a99a5f...`, current `dc0a2315...`
  - 2.0.0 recorded `a11ff2b9...`, current `247dcc38...`
  - 2.1.0 recorded `1181255c...`, current `d18dfb5a...`
  This is a provenance gap/risk signal: historical scans cannot be byte-verified against current config files.

### Validation binding (R4)

`validate_batch` passes raw `param_file_bytes` to R4; R4 computes `sha256(param_bytes)` and compares to header `param_sha256`, checks `param_version` equality (header vs param file), checks event `param_version` equals header, checks scan_mode/evidence_tier consistency, and enforces forward `frozen_at < first_event_ts`. No canonical config hash, no snapshot integrity, no config schema version.  
Refs: `scanline/validator.py:20-73`, `scanline/validation/r4.py:11-93`, `scanline/validation/context.py`.

---

## 2. Raw versus canonical hashing

### Current `param_sha256` (raw-byte hash)

- **Definition today:** SHA-256 over raw parameter file bytes exactly as read. Computed in scanner and re-checked by R4. Stored in `events.json` header and `scanner_data_manifest.json`.
- **Stability:** Stable for identical bytes; sensitive to any byte change (whitespace, key order, formatting, BOM, line endings, comments impossible in JSON, etc.).
- **Evidence:** `tests/fixtures/frozen_params.json` and `tests/fixtures/frozen_params_noncanonical.json` are semantically equal (`json` objects equal) but have different raw SHA-256 values (`0ca0696e...` vs `2ebf8931...`). `tests/fixtures/byte_hash_variant.json` binds to the noncanonical file hash.
- **Historical impact:** Changing a config file in place breaks byte-hash linkage; observed for all three historical versioned config files.

### Proposed canonical config hash

A canonical hash should represent parsed configuration *content* under a strict canonicalization spec, not file formatting. It must be additive and must not replace/redefine `param_sha256`.

| Dimension | Raw `param_sha256` | Canonical `config_hash` (proposed) |
|-----------|---------------------|-------------------------------------|
| Input | raw file bytes | canonical serialized form of parsed config |
| Formatting/whitespace | sensitive | insensitive (by design) |
| JSON object key order | sensitive | insensitive if keys sorted canonically |
| Unicode escapes / normalization | byte-sensitive; semantic equivalence after parse may differ by bytes | must define Unicode normalization/encoding explicitly |
| Numeric representation | byte-sensitive (`1.0` vs `1`) | must define numeric canonical form; risky for floats |
| Boolean/null | byte-sensitive only as formatting | semantically stable |
| Array ordering | preserved in bytes; semantically meaningful | must preserve array order (arrays are ordered) |
| Nested objects | byte-sensitive key order | recursively canonicalized |
| Defaults/alias normalization | not applied | must be explicit: either hash raw parsed content or normalized content; do not silently apply |
| Unknown/deprecated fields | included in bytes | include/exclude by explicit spec; safest: include all parsed fields present |
| Version labels / `frozen_at` | included if present in bytes | include unless explicitly excluded; exclusion creates provenance ambiguity |

### Canonicalization specification (recommended, not implemented)

**Recommendation:** define a *strict, versioned canonicalization spec* before adding `config_hash`. Start conservative: canonicalize representation, not semantics.

1. **Parse** JSON as UTF-8 text. Reject invalid JSON / non-object top-level for scanner params.
2. **No semantic mutation by default.** Do not inject defaults, do not resolve aliases, do not coerce types, do not drop unknown fields. Hash the content as parsed, except representation canonicalization.
3. **Object keys:** recursively sort object keys lexicographically by Unicode codepoint (or UTF-8 byte order of JSON-escaped key string) — pick one and document it; Python `json.dumps(sort_keys=True)` gives lexicographic key sort.
4. **Arrays:** preserve order exactly. Do not sort.
5. **Strings:** preserve exact Unicode string values after JSON parsing; serialize using UTF-8 JSON with `ensure_ascii=False` and a fixed escaping policy. Define Unicode normalization: recommend **no normalization** initially (hash exact decoded codepoints as parsed) to avoid changing meaning; document NFC/NFKC as future consideration only with explicit migration.
6. **Numbers:** highest-risk area. Do not hash Python float repr. Serialize numbers from a canonical parsed representation:
   - Integers (JSON ints, no exponent/fraction): canonical decimal string without leading `+`, no leading zeros except `0`.
   - Non-integer numbers: preserve semantic value but define a single format. Best practice: use JSON decimal representation produced by a decimal-aware parser/formatter, or reject non-canonical numeric tokens in frozen configs. Avoid `float` round-trip. For existing configs, consider hashing the original JSON number token only if tokenization is part of canonical form — but that conflicts with formatting-insensitive goal. **Recommendation:** require frozen config numeric style lint/canonical formatting, or define canonical decimal serialization via `decimal.Decimal` parsed from source token; add tests for `1`, `1.0`, `1e2`.
7. **Booleans/null:** `true/false/null`.
8. **Serialization:** `json.dumps(canonical_obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)` *only after* numeric policy is settled. Because current Python `json` reserializes numbers via float formatting in some cases, do **not** use plain `json.dumps` on `json.loads` floats for canonical hash without a numeric-preserving strategy.
9. **Hash algorithm:** SHA-256 over UTF-8 bytes of canonical serialized string. Prefix/version the domain if needed (e.g., `scanline-config-canonical-v1\0...`) to prevent ambiguity; if used, document as part of `config_hash` definition.
10. **`config_hash` identity:** include `manifest_version`-adjacent schema/version indicator for canonicalization, e.g. `config_canonicalization_version` or fold into `config_hash` object; simplest is a manifest field `config_hash_algo`/`config_canonical_version` or a self-describing string.

### Include/exclude recommendation

| Field | Include in canonical hash? | Rationale |
|------|-----------------------------|-----------|
| `module` | Include | changes execution semantics |
| `param_version` | Include | version label is part of declared config identity; excluding allows silent mismatch |
| `frozen_at` | Include (default) | freeze timestamp is provenance metadata; excluding can make different freeze events hash-identically. If treated as operational metadata, define separately. Prefer include. |
| `universe` | Include | affects scan coverage |
| `emission_timeframes` | Include | affects scan coverage/output |
| `definition_timeframe` | Include | semantic |
| `level_types` / `anomaly_types` config | Include | semantic |
| `atr_window`, `atr_basis`, bands, grid steps, crossing semantics, session tolerances etc. | Include | semantic |
| unknown/deprecated fields | Include by default | avoid silent semantic drift; alternatively reject unknown fields in validation |
| comments | N/A (JSON) | none |

**Key recommendation:** Do not exclude `frozen_at`/`param_version` from canonical hash unless SCANLINE defines a separate "semantic parameter hash" and a separate "provenance hash". Two hashes with unclear names would be worse than one clear contract.

---

## 3. Parameter version integrity

### Findings

- `param_version` is a param-file field copied into header/events/manifest. R4 requires header version == param file version and event version == header version. It does **not** check that version is unique, monotonic, or content-derived.
- `param_sha256` binds raw bytes; two different byte representations of semantically identical content produce different hashes but may carry same `param_version`.
- Different contents can share a version if a file is edited without bumping `param_version`; hash will change, but no explicit "version/content mismatch" rule exists beyond hash equality checks against the supplied bytes.
- Identical semantic content can carry different versions (possible by file authoring). Also identical content with different formatting has different raw hash.
- Config changes can occur without version increment. Current repo shows historical config names with same `param_version` but current bytes/hashes different from historical recorded hashes.
- Historical parameter files are not stored inside scan directories. Manifests/events record `param_file` basename only, not a resolvable snapshot path. Reconstructing historical exact bytes requires external retention.

### Mismatch detection recommendations

- Keep raw-byte `param_sha256` as immutable record of exact bytes used.
- Add canonical `config_hash` + `config_canonicalization_version` (or equivalent) for semantic equivalence detection.
- Add `config_snapshot` (raw, and optionally normalized) inside scan dir; verify hash against snapshot at completion/audit.
- Add validation rule/audit check: if two scans claim same `param_version` + `module` + semantic config identity but different `config_hash`, flag provenance inconsistency; if same version but different content, flag version-content mismatch.
- Do not auto-bump or infer version policy. Document existing convention from config filenames/history (`scanner_params.level_proximity-X.Y.Z.json`, `param_version` field).

---

## 4. Configuration snapshots

### Option A — Exact raw parameter file per scan

- **Pros:** maximal byte-for-byte reproducibility; verifies existing `param_sha256`; simple; preserves unknown formatting/comments-no (JSON none) but preserves exact bytes; supports forensic audit.  
- **Cons:** duplicates small files; path/name management; snapshot may include irrelevant formatting differences.  
- **Cost:** tiny (config files ~1-4KB).  
- **Recovery:** excellent if retained.

### Option B — Normalized/canonical snapshot only

- **Pros:** stable diffs; easier semantic comparison.  
- **Cons:** cannot verify legacy/raw-byte hash without original bytes; canonicalization bugs become provenance bugs; may lose numeric token formatting if not carefully designed.  
- **Recovery:** good for semantics, weak for exact-byte audit.

### Option C — Both raw and normalized snapshots

- **Pros:** best auditability and semantic comparison; raw verifies `param_sha256`; normalized verifies `config_hash`.  
- **Cons:** slightly more complexity/storage; needs clear naming and integrity fields.

### Recommendation (smallest reliable)

**Recommend Option A now, with Option C-ready schema.** Store exact raw param bytes as `config_snapshot.json` (or original basename copy) inside each scan directory and record its name/hash/size in manifest outputs or a dedicated manifest field. This gives reliable historical recovery and verifies existing `param_sha256` with minimal design risk. Defer normalized snapshot until canonicalization spec is finalized; when added, Option C becomes straightforward.

Do not implement snapshots yet.

---

## 5. Manifest integration

### Existing fields (preserve meaning)

- `param_file`: basename of param file used.
- `param_sha256`: SHA-256 of raw parameter file bytes (existing meaning must remain unchanged).
- `param_version`: param file `param_version` value.
- `frozen_at`: param file `frozen_at` value.

### Proposed additions

| Field | Type | Required? | Definition | Notes |
|------|------|-----------|------------|-------|
| `config_hash` | string | optional in transition; required in future schema bump | SHA-256 (or specified algo) of canonicalized config content per SCAN-018C canonicalization spec | Must not replace `param_sha256`; include algo/canon version metadata |
| `config_hash_algo` | string | optional | e.g. `sha256` | avoid ambiguity |
| `config_canonical_version` | string | optional | canonicalization spec version, e.g. `1.0.0` | required if `config_hash` present |
| `config_snapshot` | string or object | optional | relative filename/path inside scan dir for raw config snapshot; or object `{name, sha256, size_bytes, kind}` | raw snapshot recommended first |
| `config_snapshot_sha256` | string | optional | raw snapshot SHA-256; should equal `param_sha256` when raw snapshot is exact bytes | can be omitted if snapshot included in outputs |
| `config_schema_version` | string/int | optional | schema/version of config structure, if/when defined | only if SCANLINE defines config schema versioning; do not overload with manifest version |

### Placement/contract

- Add fields at top-level manifest alongside existing param fields for discoverability.
- If snapshot is a file in scan dir, include it in `outputs` inventory for integrity verification (same as `events.json`), or add a dedicated `inputs`/`snapshots` section with same hash/size contract. Prefer `outputs` only if semantics are clear; otherwise add `snapshots`/`artifacts` with explicit verification rules in a future schema bump.
- `is_scan_complete()` currently verifies declared `outputs` and required fields; adding required snapshot/output checks would be a contract change. Keep additive/optional first.

### Manifest version impact

SCAN-018B manifest is `1.0.0` with strict required-field validation for v1.0.0 and compatible minor/patch handling. Adding optional fields (`config_hash`, snapshot metadata) can be a **minor** manifest schema bump (`1.1.0`) if validation ignores unknown optional fields and required set unchanged. Making them required, or changing completion semantics, requires careful minor/major planning; prefer minor bump + optional fields, then promote later.

---

## 6. Historical provenance

### What can be reconstructed today

- **From events header:** module, scan mode, evidence tier, param_file basename, raw `param_sha256`, `param_version`, `frozen_at`, universe/timeframes/definition/batch window. Useful for identity.
- **From manifest:** extraction/batch window, series file hashes/sizes/spans, raw `param_sha256`, param_file basename, code_state driver sha256/commit, evidence tier, outputs hash/size for `events.json`.
- **From git:** code state commit may help, but config bytes at commit may differ from scan-used bytes.

### Gaps / risks

- No stored config snapshot in scan dirs; cannot prove exact config contents when config file changes or is missing.
- Historical recorded `param_sha256` values do not match current same-named files in `config/` (all three historical scans observed). Raw-byte provenance is therefore broken against current workspace config files.
- No canonical hash; cannot determine semantic equivalence across formatting changes.
- No config schema/canonicalization version.
- `frozen_at` is self-declared in config; no independent freeze ledger/signature.
- Historical manifests pre-SCAN-018A lack scan_id/status/outputs; pre-018B lack manifest_version and many integrity fields. `is_scan_complete()` may return false for legacy-readable manifests by design.

### Reconstruction policy

Do not modify historical files. Do not backfill guessed snapshots/hashes. If needed later, create a separate audit report that marks unverifiable provenance as "unknown/unverifiable", not "failed".

---

## 7. Required tests (proposal only)

1. **Raw hash stability:** same bytes -> same `param_sha256`; persisted across manifest/header.
2. **Canonical hash stability:** same semantic config canonicalized repeatedly -> same `config_hash`.
3. **Equivalent JSON formatting:** whitespace/key-order differences with identical semantics -> same `config_hash`, different `param_sha256`.
4. **Key-order independence:** nested object key reorderings -> same canonical hash.
5. **Meaningful configuration changes:** any semantic field change -> canonical hash changes; version/content mismatch detected when version unchanged.
6. **Array-order handling:** array order changes -> canonical hash changes (arrays ordered).
7. **Unicode handling:** equivalent Unicode representations/escapes per spec -> defined outcome; non-equivalent content -> different hash.
8. **Numeric representation:** `1` vs `1.0` vs `1e0` behavior explicitly asserted per spec; float/token edge cases covered.
9. **Version/content mismatch:** same `param_version`, different content/hash flagged; different version, identical content handled per policy.
10. **Snapshot integrity:** snapshot file hash/size matches manifest; raw snapshot hash equals `param_sha256`.
11. **Snapshot-to-manifest consistency:** manifest references snapshot present in scan dir; missing/corrupt snapshot fails audit/completion as specified.
12. **Historical compatibility:** legacy scans without new fields remain readable; `is_scan_complete()` behavior unchanged except intentional, versioned contract updates; no historical file mutation.

Additional regression tests: unknown-field handling, `frozen_at` inclusion/exclusion as specified, canonicalization version field required when `config_hash` present, manifest v1.0.0/v1.1.0 compatibility.

---

## 8. Performance and storage implications

- **Raw-byte hash:** already computed twice in current code path (`header` and `manifest` use separate `hashlib.sha256(params_bytes)` calls) — trivial cost; can reuse one digest.
- **Canonical hash:** small JSON configs (<10KB observed); canonicalization/hash cost negligible compared with scan I/O and validation. Main cost is implementation correctness, especially numeric canonicalization.
- **Snapshots:** ~1-4KB per scan for raw config; negligible vs event/manifests and corpus-scale data. Option C doubles that small cost.
- **Audit/verification:** hashing snapshot is cheap; deep audit that re-reads corpus remains separate from `is_scan_complete()`.

---

## 9. Risks and dependencies

| Risk | Impact | Mitigation |
|------|--------|------------|
| Canonicalization ambiguity (numbers, Unicode, defaults) | non-reproducible or incorrect `config_hash` | versioned canonical spec, golden fixtures, cross-impl tests |
| Redefining `param_sha256` accidentally | breaks historical/protocol compatibility | preserve raw-byte meaning; additive `config_hash` only |
| Silent version/content drift | false provenance confidence | add mismatch detection/audit checks; snapshot raw bytes |
| Historical config bytes already diverged from recorded hashes | cannot verify old scans against current config files | store snapshots going forward; mark historical unverifiable, no backfill |
| Manifest contract churn | consumer breakage | additive optional fields first, minor schema bump, strict tests |
| Snapshot path traversal/integrity | security/integrity regression | reuse SCAN-018A-R1 path/output verification patterns |
| SCAN-018C overlaps SCAN-018B reserved fields | duplicate/conflicting schema evolution | coordinate field names/types before implementation |

Dependencies: SCAN-018B manifest contract (`manifest_version` 1.0.0, `is_scan_complete`), SCAN-018A-R1 path/integrity protections, R4 parameter binding, config freeze workflow/conventions.

---

## 10. Recommended implementation sequence

1. **Spec first:** write canonicalization spec (numeric/Unicode/field inclusion/array order) as a design doc with fixtures; get explicit approval.
2. **Add raw snapshot support (Option A):** write exact param bytes into scan dir; add manifest metadata/output entry; verify `snapshot_sha256 == param_sha256`.
3. **Add canonical hash metadata:** compute `config_hash` per approved spec; store `config_hash`, `config_hash_algo`, `config_canonical_version`; keep `param_sha256` unchanged.
4. **Manifest/version update:** bump manifest minor version (e.g. 1.1.0) with optional additive fields; update `is_scan_complete()` only for compatible validation and snapshot/output integrity if declared.
5. **Validator/audit integration:** extend R4 or add audit checks for snapshot/hash/version consistency; do not break existing scans.
6. **Historical audit tooling (read-only):** report provenance status for existing scans; never mutate historical records.

---

## 11. Restrictions honored

This reconnaissance made no source/test/config/historical/manifest/event modifications, no snapshot generation, and no hash changes. Only this report was created.
