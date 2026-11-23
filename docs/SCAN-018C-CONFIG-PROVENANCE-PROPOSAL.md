# SCAN-018C — Configuration Provenance Implementation Proposal

**Status:** DESIGN AND PROPOSAL ONLY. No implementation authorized.
**Date:** 2026-11-21 (revised this pass)
**Baseline:** `ef1f73b` (`main == origin/main`)
**Inputs (read-only inspection):** `docs/SCAN-018C-CONFIG-PROVENANCE-RECON.md`, `docs/SCAN-018B-MANIFEST-PROPOSAL.md`, `scanline/scan.py`, `scanline/validator.py`, `scanline/validation/r4.py`, `scanline/schema.py`, `scanline/sessions.py`, `scanline/validation/utils.py`, current config fixtures under `config/`, fixture files under `tests/fixtures/`, historical manifests under `records/scans/*/scanner_data_manifest.json`.

This revision is proposal/documentation only. No source, config, test, historical manifest/event/snapshot, or unrelated documentation files are modified except this file.

---

## 1. Executive summary

SCANLINE currently records `param_sha256` as SHA-256 of the **raw parameter-file bytes** read by `run_scan()` (`scanline/scan.py` around raw read/assignment and manifest/header emission in the current driver). R4 recomputes that raw-byte hash and validates parameter binding (`scanline/validation/r4.py`). This provides exact-byte auditability but not semantic provenance: formatting-only changes alter the hash, and historical scans cannot be byte-verified against current same-named config files because configs changed in place and historical scan directories contain no config snapshot.

SCAN-018C proposes an additive provenance contract:

- Preserve `param_sha256` exactly as raw-byte SHA-256 of the original config bytes read once.
- Add `config_hash` as SHA-256 of **`SCANLINE-config-canon-v1`** canonical bytes of the **effective validated configuration** actually consumed by SCANLINE.
- Define a single `load_config()` boundary that reads raw bytes once, parses from those retained bytes, validates and normalizes, resolves module aliases, applies schema-approved defaults and required module-specific normalization/context resolution, produces one authoritative effective configuration, and returns immutable provenance/snapshot metadata.
- Store **both** `param_snapshot.raw.json` (byte-identical copy of the original parameter input; SHA-256 equals `param_sha256`) and `param_snapshot.effective.json` (canonical effective configuration bytes; SHA-256 equals `config_hash`) in each scan directory.
- Integrate snapshot outputs into the SCAN-018B atomic publication flow and `scanner_data_manifest.json` outputs inventory, with manifest minor version **`1.1.0`** for new config-provenance manifests.
- Keep historical records immutable; report historical provenance gaps as unverifiable legacy, never fabricated.

**Canonicalization is a custom SCANLINE specification.** `SCANLINE-config-canon-v1` is project-specific and is **not** RFC 8785 / JCS compliant. This document must not be read or implemented as claiming RFC 8785/JCS compatibility.

---

## 2. Current-state basis (observed, read-only)

| Area | Observed behavior | Reference (current tree) |
|------|-------------------|---------------------------|
| Param load (driver) | `params_bytes = param_path.read_bytes(); params = json.loads(params_bytes)` | `scanline/scan.py` (raw read then JSON parse in `run_scan`) |
| Raw hash | `hashlib.sha256(params_bytes).hexdigest()` written into events header and manifest | `scanline/scan.py` |
| Validation gate | `validate_batch(all_events, header, params_bytes)` before destination writes; failures abort with no artifacts | `scanline/scan.py`, `scanline/validator.py` |
| R4 binding | Recomputes raw-byte SHA-256 over `param_file_bytes`, compares to `header.param_sha256`; checks version equality (param file/header/events), `scan_mode`/`evidence_tier` consistency, forward `frozen_at` strictly before first event `event_ts`; for `session_anomalies` calls `validate_session_config(param_data)` | `scanline/validation/r4.py`, `scanline/sessions.py` |
| Module normalization | Driver normalizes module via `normalize_module_id(params.get("module", "level_proximity"))` for scan behavior; schema also defines `MODULE_ALIASES` (`module_1 -> level_proximity`) | `scanline/scan.py`, `scanline/schema.py` |
| Manifest contract (v1.0.0) | Requires `param_file,param_sha256,param_version,frozen_at` and others; manifest is completion marker; `outputs` entries include `name/sha256/size_bytes`; `is_scan_complete()` verifies v1.0.0 contract when versioned | `scanline/scan.py` |
| Historical scans | Several `records/scans/*/scanner_data_manifest.json` entries lack v1.1.0 provenance fields and snapshots (legacy behavior preserved) | `records/scans/*/scanner_data_manifest.json` (read-only) |
| Historical hash drift (observed) | Recorded historical `param_sha256` values for same-named configs can differ from current working-tree config bytes; verified in §9.4 | §9.4 and recon notes (read-only audit observation) |

## 3. Raw hash vs canonical hash

### 3.1 `param_sha256` (preserved, unchanged)

- **Algorithm:** SHA-256 (hex, lowercase as produced by current driver/validator conventions).
- **Input:** exact original parameter input bytes as read by the authoritative loader from `param_path`, captured once as `raw_bytes` (or the single `params_bytes` object in the current implementation).
- **Capture point:** the same retained raw bytes used for parsing, header/manifest fields, validation (`validate_batch(..., param_file_bytes=...)` / R4), raw snapshot publication, and any subsequent integrity checks in that execution.
- **Meaning:** byte identity of the original config artifact supplied to the scan.
- **Compatibility:** existing field name, type, and semantics unchanged in events header, manifest, validator, tests, and historical records. `is_scan_complete()` and verifiers continue to treat `param_sha256` as the raw-byte hash of the declared raw snapshot/source bytes under the existing contract unless a new manifest version changes that rule (see §7).
- **Prohibition:** MUST NOT be recomputed from a reopened path, canonical serialization, effective/defaulted/normalized config, parsed re-serialization, or a snapshot re-read.

### 3.2 `config_hash` (additive semantic identity)

- **Algorithm:** SHA-256 (hex, lowercase).
- **Canonicalization:** `SCANLINE-config-canon-v1` as defined in §4. **This is not RFC 8785 / JCS and must not be described as RFC 8785/JCS compliant.**
- **Input:** UTF-8 bytes of the canonical JSON serialization of the **effective validated configuration** returned/constructed by `load_config()` (§5), i.e. the complete effective configuration record subject defined in §3.4.
- **Meaning:** semantic identity of the configuration SCANLINE actually consumed (after schema validation, module alias resolution, schema-approved defaults, and required module-specific normalization/context resolution), independent of insignificant raw formatting and independent of object key ordering in the source JSON.
- **Required manifest metadata when present:** `config_hash_algorithm="sha256"`, `config_canonicalization_version="SCANLINE-config-canon-v1"`, `config_hash_subject="effective_validated_config"`.

### 3.3 Distinction

| Property | `param_sha256` | `config_hash` |
|---|---|---|
| Identity class | Raw artifact bytes | Canonical effective configuration (effective validated config record subject) |
| Formatting sensitivity | Yes | No by `SCANLINE-config-canon-v1` (subject to rules below) |
| Key-order sensitivity | Yes at byte level | No (objects recursively sorted by Unicode codepoint order) |
| Numeric token formatting in source | Yes at byte level | Canonicalized by exact-decimal rules in §4; no parsing through binary `float` |
| Module aliases / defaults / normalization | Not applied to the hash input except raw bytes | Applied only through explicit `load_config()` effective-config construction |
| Unknown fields | Present as bytes | Rejected by schema validation unless the specific schema version explicitly permits them (§6) |
| Audit use | Proves exact supplied bytes | Proves semantic/effective config identity under declared canon/version/subject |

### 3.4 Hash subject (explicit)

Define:

`config_hash_subject = "effective_validated_config"`

The canonical hash describes the **complete effective configuration record** produced by `load_config()` for the consumed scan, not merely a pre-validation JSON object. The subject includes:

- Canonical module identity (as resolved/normative for the effective config, e.g. canonical `module` value after alias normalization rules applied in the effective builder).
- All validated, normalized effective fields that affect the module’s behavior or interpretation.
- Approved resolved defaults and aliases that are part of the effective consumed configuration.
- `param_version`.
- `frozen_at`.
- `config_schema_version` where applicable (when the schema version determines interpretation of the configuration; if multiple schema families exist, the effective schema/version identifier that governs validation/normalization semantics must be included in the effective record and therefore in the hash).

**Explicit:** Including `param_version` and `frozen_at` means `config_hash` identifies a **complete configuration record**, not a behavior-only equivalence class. Two records that differ only by those declared fields have different `config_hash` values when they appear in the effective record (and they are part of the subject by definition above).

### 3.5 Exclusions from the hashed subject (no circularity)

The following MUST NOT be included in the hashed effective configuration subject and MUST NOT appear as inputs to `config_hash`:

- `config_hash`
- Hash algorithm name (e.g. `config_hash_algorithm`)
- Canonicalization version metadata (e.g. `config_canonicalization_version`)
- Hash-subject metadata field value stored alongside the hash (e.g. `config_hash_subject`)
- Snapshot filename references (`param_snapshot.raw.json`, `param_snapshot.effective.json`, or any snapshot path/name metadata)
- `param_sha256`

`param_sha256 = SHA256(raw_bytes)` remains the raw-byte identity of the original input. `config_hash = SHA256(canonical_effective_bytes)` remains the canonical effective-config identity. The effective snapshot bytes are exactly the canonical bytes used to calculate `config_hash` (§7).

---

## 4. Canonicalization specification and numeric policy (`SCANLINE-config-canon-v1`)

`SCANLINE-config-canon-v1` is a **custom canonicalization specification** defined by this document. It is **not** RFC 8785/JCS compliant. Do not claim RFC 8785 or JCS compatibility in code, comments, manifests, or documentation. Any behavioral change requires a new canonicalization version string and new golden vectors.

### 4.1 Hash input boundary

1. Read raw bytes once (`raw_bytes`) from the parameter path under the authoritative `load_config()` boundary (§5).
2. Decode raw input as strict UTF-8 for canonicalization input handling; invalid UTF-8 is rejected (see §4.4).
3. Parse JSON from those retained bytes using a **token-preserving, exact-decimal** parser that enforces §4 rules (no binary `float`, reject duplicate keys, reject non-finite tokens). This parser produces the parsed representation used by schema validation and effective-config construction.
4. Validate and build the **effective validated configuration** via `load_config()` (§5). The hash subject is that effective record (§3.4).
5. Canonicalize the effective configuration object per §4.2–§4.6.
6. Encode canonical JSON as UTF-8 (no BOM). Emit **no trailing newline** in canonical snapshot bytes. The bytes written to `param_snapshot.effective.json` are exactly these canonical UTF-8 bytes and are exactly the bytes hashed as `config_hash = SHA256(canonical_utf8_bytes).hexdigest()` (lowercase hex).
7. `param_sha256 = SHA256(raw_bytes).hexdigest()` is computed from the same `raw_bytes` (not from canonical bytes).

### 4.2 Frozen canonicalization rules (normative)

- JSON input is decoded as **strict UTF-8**.
- JSON numeric tokens are parsed exactly using `decimal.Decimal` or an equivalent **token-preserving exact-decimal** implementation.
- **Do not** parse numeric tokens through binary `float` before canonicalization (and do not use default `json.loads` float coercion for canonical/hash parsing).
- Reject **duplicate object keys** during parsing (any object with a repeated member name is invalid). Default “last wins” behavior is forbidden.
- Sort object keys recursively by **Unicode codepoint order** of the decoded JSON string keys.
- Preserve **array order** exactly (never sort arrays).
- Preserve decoded string **codepoints exactly** as represented in the parsed JSON string value (after JSON unescaping) with no re-encoding changes beyond JSON string emission rules below.
- **Do not** apply NFC, NFD, NFKC, or NFKD normalization.
- Emit **compact UTF-8 JSON** with **no insignificant whitespace**. Use separators `,` and `:` only (no spaces).
- Emit **no trailing newline** in canonical snapshot bytes.
- Reject **invalid UTF-8** and **lone surrogate codepoints** (including lone surrogates produced by invalid `\uXXXX` sequences such as unpaired surrogates). Invalid escape sequences are rejected.
- Reject `NaN`, `Infinity`, and `-Infinity` (not valid JSON number tokens; any representation attempted is invalid input).
- Preserve booleans and null as JSON literals `true`, `false`, `null`.
- Preserve the **exact numeric value** during generic canonical parsing (exact decimal parsing). No rounding in the canonical decimal expansion step described below.
- Normalize **`-0`**, **`-0.0`**, and **`-0e0`** (and any mathematically zero decimal token, including forms like `-0.00e+1`) to canonical numeric string **`0`**.
- Normalize mathematically equivalent finite decimal representations consistently (examples): `1`, `1.0`, `1e0` → `1`; `1e2` → `100`; `0.0050` → `0.005`.
- Expand numeric output **without exponent notation** (no `e`/`E` in canonical number strings).
- Remove insignificant trailing fractional zeroes and remove a trailing decimal point when the fractional part is empty after trimming.

Additional serialization notes (normative): top-level JSON value for scanner/effective config canonicalization is a **JSON object** (non-object top-level is invalid for this subject). Strings are emitted as JSON strings using standard JSON escaping with UTF-8 output; implementations MUST produce canonically equivalent UTF-8 bytes under these rules (do not insert insignificant whitespace). There is no BOM.

### 4.3 Numeric parsing rules (exact decimal)

- Accepted JSON number lexeme (conceptual): `-?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][+-]?[0-9]+)?` with standard JSON constraints (no leading `+`, no leading zero in the integer part except the single digit `0` when not followed by `.`, `e`, or `E` as appropriate to the token form).
- Parsing MUST be performed from the original token string into an exact decimal value (`decimal.Decimal` or equivalent). **Do not** go through binary `float`.
- Canonical form is the exact mathematical decimal value of that token, formatted per §4.2 (no exponent, trimmed fractional zeros, `-0` family → `0`).
- Examples (exact parser/canonical behavior): token `1` → canonical `1`; `1.0` → `1`; `1e0` → `1`; `1e2` → `100`; `0.0050` → `0.005`; `-0`, `-0.0`, `-0e0` → `0`.

### 4.4 Numeric bounds (concrete v1 limits)

These are the proposed v1 limits for `SCANLINE-config-canon-v1`. They are **deterministic resource bounds**: they bound decimal expansion and protect against pathological numeric tokens. Use these limits unless inspection of the actual current configuration set demonstrates that a legitimate existing SCANLINE configuration requires a different bound (see evidence below).

- **Maximum numeric coefficient digits:** **128**. Count **all digits in the mantissa** of the parsed decimal value, including **leading and trailing zeroes in that mantissa representation** used for counting, but **excluding** sign, decimal point, and exponent. (Equivalently: count every decimal digit character that appears in the significand before applying the exponent shift in the exact decimal parse; implementations must document the counting rule and apply it consistently.) Reject any numeric token whose coefficient digit count exceeds 128 **before** producing canonical output.
- **Maximum absolute explicit base-10 exponent:** **308**. Let `E_abs = |exponent|` for any explicit exponent in the JSON number token; reject if `E_abs > 308`.
- **Derived maximum canonical expanded numeric representation:** **437 characters**, excluding a leading sign, under the 128-coefficient-digit and ±308 explicit-exponent limits. This is a **mathematical upper bound** derived in §4.4.2, not an independent permissive limit. Canonical form has no exponent, no insignificant fractional zeroes, and no trailing decimal point.
- **Defensive output assertion (optional, non-permissive):** Implementations MAY retain a defensive assertion that canonical expanded numeric length excluding sign is `<= 512`. If retained, it MUST be documented as a **defensive unreachable guard only**: it does not authorize acceptance of any token that exceeds the coefficient or exponent limits, and it does not imply that a 512-character numeric token is accepted. A 512-character expanded numeric token is **unreachable for accepted input** under the 128/308 limits; accepted input cannot exceed 437 characters excluding sign.
- Reject any value exceeding **any** accepted-input limit (coefficient digits, absolute explicit exponent, raw size, nesting depth) before canonical output is generated. The derived 437-character bound is implied by those limits; implementations may check it defensively but must not treat 512 as an acceptance ceiling independent of the input limits.
- **Additional structural limits:** maximum raw configuration size **1 MiB** (1,048,576 bytes) for the parameter input accepted by `load_config()` in v1 unless a legitimate current configuration requires larger; maximum JSON nesting depth **64** levels of nested objects/arrays unless legitimate current configurations require deeper nesting. These are guardrails for deterministic parsing; if any legitimate current config exceeds them, do not silently relax—report the exact file, offending value/structure, and required bound, then select and document a justified explicit replacement bound (see §4.4.1).

**Why these limits exist:** deterministic resource bounds, bounded decimal expansion (preventing multi-megabyte numeric expansions), and protection against pathological numeric tokens that would otherwise cause unbounded work or memory in naive implementations.

#### 4.4.1 Evidence against current configs/fixtures (read-only verification, 2026-11-21)

Verification was run read-only against actual repository files using a temporary script outside the repo (`/tmp/scan018c_limits.py`, inspected before execution). The script decoded strict UTF-8, parsed JSON with a token-preserving scanner, rejected duplicate keys/trailing content in parse, measured max JSON nesting depth by parser depth, counted numeric mantissa digits as all significand digits in the token (including leading/trailing zeroes, excluding sign/decimal point/exponent), measured absolute explicit exponent, and computed canonical expanded numeric length excluding leading sign per canon-v1 rules.

| File | Raw bytes | Max nesting depth | Max mantissa digits | Max abs exponent | Max canonical expanded len (excl sign) | Raw size <=1MiB | Depth <=64 | Mantissa <=128 | Abs exp <=308 | Canon len <=437 (derived) | All accepted-input limits satisfied |
|---|---:|---:|---:|---:|---:|:---:|:---:|:---:|:---:|:---:|:---:|
| `config/scanner_params.level_proximity.json` | 757 | 3 | 5 | 0 | 5 | yes | yes | yes | yes | yes | yes |
| `config/scanner_params.level_proximity-1.1.0.json` | 872 | 3 | 3 | 0 | 4 | yes | yes | yes | yes | yes | yes |
| `config/scanner_params.level_proximity-2.0.0.json` | 1819 | 3 | 3 | 0 | 4 | yes | yes | yes | yes | yes | yes |
| `config/scanner_params.level_proximity-2.1.0.json` | 1811 | 3 | 4 | 0 | 4 | yes | yes | yes | yes | yes | yes |
| `tests/fixtures/frozen_params.json` | 575 | 3 | 4 | 0 | 5 | yes | yes | yes | yes | yes | yes |
| `tests/fixtures/frozen_params_noncanonical.json` | 575 | 3 | 4 | 0 | 5 | yes | yes | yes | yes | yes | yes |
| `tests/fixtures/byte_hash_variant.json` | 2649 | 4 | 6 | 0 | 7 | yes | yes | yes | yes | yes | yes |

**Result:** All inspected relevant current configs and listed fixtures fit the proposed accepted-input limits. No legitimate existing config exceeded any limit; no limit was relaxed. The derived canonical-length bound is 437 (excluding sign); all inspected files are far below it.

#### 4.4.2 Mathematical derivation of canonical expanded-length bound (independent Python verification, 2026-11-21)

**Goal:** derive the maximum possible canonical expanded numeric representation length, excluding a leading sign, for a **valid JSON numeric token accepted under canon-v1 input limits**: coefficient digit count `m <= 128` and absolute explicit base-10 exponent `|E| <= 308`.

**Definitions (matching §4.4):**

- `m` = number of mantissa/coefficient digits in the token, counting all significand digits including leading/trailing zeroes, excluding sign, decimal point, and exponent.
- `p` = number of fractional digits in the mantissa (`0 <= p <= m-1` for a JSON number with a decimal point; `p=0` for integer mantissa). JSON requires at least one digit in integer part and, if a decimal point is present, at least one digit in fraction part.
- `E` = explicit base-10 exponent integer; accepted input requires `|E| <= 308`.
- `k` = number of significant digits in the value after removing insignificant leading zeroes from the coefficient (`1 <= k <= m` for nonzero; zero normalizes to `0`, length 1).
- `s = E - p` = decimal shift of the integer significand.
- Canonical form: no exponent, no insignificant fractional zeroes, no trailing decimal point; `-0` family becomes `0`.

**Canonical length formula (nonzero value, excluding sign):**

- If `s >= 0`: canonical is integer digits = `k + s`.
- If `s < 0` and `k + s > 0`: decimal point falls inside digits = `k + 1`.
- If `s < 0` and `k + s <= 0`: canonical is `0.` + `(- (k+s))` leading zeros after decimal + `k` digits = `2 - s`.

**Maximization:** length is monotonic nondecreasing in `k` for the maximizing cases, so use `k = m = 128`. Also `p = m-1 = 127` maximizes `-s = p-E` in the small-fraction case.

| Case | m | p | E | s=E-p | Canon length excl sign | Example class |
|---|---:|---:|---:|---:|---:|---|
| Large integer exponent | 128 | 0 | 308 | 308 | `128+308=436` | `9`*128 + `e308` |
| Large integer exponent, fractional mantissa | 128 | 127 | 308 | 181 | `128+181=309` | `1.` + `1`*127 + `e308` |
| Small magnitude, integer mantissa | 128 | 0 | -308 | -308 | `2 - (-308)=310` | `1`*128 + `e-308` |
| Small magnitude, maximal fraction digits | 128 | 127 | -308 | -435 | `2 - (-435)=437` | `0.` + `1`*127 + `e-308` |

**Result:** the maximum over all `1<=m<=128, 0<=p<=m-1, -308<=E<=308` is **437** characters excluding sign, achieved at `(m,p,E)=(128,127,-308)`.

**Python verification (read-only, `/tmp`, 2026-11-21):**

```text
full search: max_len=437 at (m=128, p=127, E=-308)
targeted: (128,0,308)->436, (128,127,308)->309, (128,0,-308)->310, (128,127,-308)->437
actual canonicalization:
  '0.'+'1'*127+'e-308'  coeff=128 absE=308 canon_len_excl_sign=437
  '1.'+'2'*127+'e-308'  coeff=128 absE=308 canon_len_excl_sign=437
  '-'+'0.'+'1'*127+'e-308' canon_len_excl_sign=437 (sign excluded)
  '9'*128+'e308'        coeff=128 absE=308 canon_len_excl_sign=436
```

**Contradiction resolution:** a 512-character numeric value such as `10^511` is **not accepted**. `10^511` has coefficient digits 1 and explicit exponent 511; it violates `|E| <= 308` and must be rejected before canonical output. Any accepted input under the 128/308 limits has canonical expanded length `<= 437` excluding sign. The previous 512 limit is removed as an independent acceptance limit; an optional defensive assertion `<= 512` may remain only as an unreachable guard (§4.4).

#### 4.4.3 Explicit boundary tests (read-only, /tmp script)

All boundary cases were tested with temporary scripts outside the repo (`/tmp/scan018c_limits.py`, ad hoc Python checks). “Accepted by limit” means the constructed value is within the stated accepted-input limit; “rejected by limit” means it exceeds an accepted-input limit and must be rejected before canonical output.

| Limit | Case | Input/value | Observed | Accepted at limit | Rejected one beyond |
|---|---|---|---|:---:|:---:|
| Mantissa coefficient digits (128) | at limit | token with 128 significand digits (`1` + 127 zeros) | coeff_digits=128, canon_len_excl_sign=128 | yes | - |
| Mantissa coefficient digits (128) | one beyond | 129 significand digits | coeff_digits=129, canon_len_excl_sign=129 | - | yes |
| Absolute explicit base-10 exponent (308) | at limit | `1e308` | abs_exponent=308, canon_len_excl_sign=309 | yes | - |
| Absolute explicit base-10 exponent (308) | one beyond | `1e309` | abs_exponent=309, canon_len_excl_sign=310 | - | yes |
| Derived canonical expanded length excl sign (437) | at limit (positive form equivalent magnitude) | `9`*128 + `e308` gives 436; max 437 at small-magnitude form below | max derived 437 | yes | - |
| Derived canonical expanded length excl sign (437) | at limit | `0.` + `1`*127 + `e-308` | coeff=128, absE=308, canon_len_excl_sign=437 | yes | - |
| Derived canonical expanded length excl sign (437) | negative at limit | `-0.` + `1`*127 + `e-308` | coeff=128, absE=308, canon_len_excl_sign=437 (sign excluded) | yes | - |
| Derived canonical expanded length excl sign (437) | one beyond by exponent | `0.` + `1`*127 + `e-309` | absE=309, canon_len_excl_sign=438; rejected by exponent limit | - | yes (by exponent) |
| Derived canonical expanded length excl sign (437) | one beyond by coefficient | `0.` + `1`*128 + `e-308` | coeff=129, canon_len_excl_sign=438; rejected by coefficient limit | - | yes (by coefficient) |
| Raw config size (1 MiB / 1,048,576 bytes) | at limit | size=1,048,576 | accepted_by_limit=true | yes | - |
| Raw config size (1 MiB / 1,048,576 bytes) | one beyond | size=1,048,577 | accepted_by_limit=false | - | yes |
| JSON nesting depth (64) | at limit | constructed nested object with observed_depth=64 | accepted_by_limit=true | yes | - |
| JSON nesting depth (64) | one beyond | observed_depth=65 | accepted_by_limit=false | - | yes |

**Defensive 512 assertion (if retained):** synthetic canonical string length 512 can be constructed for guard testing only; it is **not** producible by any accepted canon-v1 input under coeff<=128 and |E|<=308. Therefore tests for a 512 guard must be labeled as synthetic output-guard tests, separate from input-acceptance tests.

Numeric semantic boundary cases (all within limits, canonicalized as shown): `0`→`0`, `-0`→`0`, `-0.0`→`0`, `-0e0`→`0`, `0e308`→`0`, `-0e308`→`0`, `1e308`/`1E308`→309-digit expanded integer, `0.0050`→`0.005`, `1.000`→`1`, `-1.000`→`-1`. These confirm zero/negative-zero normalization, exponent expansion, and trailing-zero normalization behavior at/near bounds.

### 4.5 “Non-exactly-representable” (explicit definition)

This phrase MUST NOT remain ambiguous. Two phases are distinguished:

1. **Exact decimal parsing and canonicalization (generic layer).** A finite JSON decimal number token is parsed into an exact decimal value by the canon-v1 parser (`Decimal`/equivalent from the token string, no binary `float`). There is no claim that such a token is “not exactly representable” as a `Decimal`; on the contrary, finite decimal tokens are represented exactly at this layer subject only to the explicit bounds in §4.4. Canonicalization outputs that exact decimal value in expanded decimal form per rules above.
2. **Schema-defined conversion to the runtime type consumed by the module (schema/normalization layer).** After parsing/validation, each numeric field is interpreted according to the schema’s declared type and the module’s runtime consumer requirements. “Non-exactly-representable” in operational terms means: the value cannot be accepted as the declared schema type under the rules below **without violating those rules** (e.g. not integral for an integer field, or not representable as a finite IEEE-754 binary64 under the stated conversion policy when the field is float-backed). Ordinary values like `0.1` are **not** rejected solely because their binary64 representation is inexact; rejection happens only when schema/runtime conversion rules require it (see policy).

**Schema/type declaration requirement:** The schema (and effective-config builder) MUST declare for each numeric field whether it is an **integer**, **Decimal** (exact decimal retained), or **binary float** (converted to IEEE-754 binary64 at the schema normalization boundary).

**Recommended v1 policy (apply unless actual SCANLINE schema/consumer design requires a documented alternative):**

- **Integer fields:** accept only mathematically integral values (after exact decimal parsing) and enforce schema range constraints. A token such as `1.0` or `1e0` is mathematically integral and MAY be accepted **only if** schema normalization explicitly converts it to the integer representation required by the consumer; otherwise reject. Fractional values (e.g. `1.5`) are rejected for integer fields.
- **Decimal fields:** retain the exact `Decimal` value (no rounding, no binary-float conversion).
- **Binary-float fields:** convert explicitly to finite IEEE-754 binary64 at the schema normalization boundary. Reject on overflow to infinity. Reject if a **nonzero** input underflows to zero in the resulting float representation (treat as invalid for that field). Document that ordinary binary64 rounding is part of that field’s declared runtime semantics.
- **Effective snapshot/hash for float-backed fields:** represent the effective normalized value in the effective configuration using the **shortest round-trip decimal representation of the actual runtime float** (equivalent to `Decimal(repr(runtime_float))` in Python terms, i.e. the decimal text that round-trips to the same binary64 value) so that the effective snapshot and `config_hash` describe the value the module actually consumes. This does **not** mean the original decimal token is preserved byte-for-byte when conversion is declared; it means the effective record records the converted runtime value canonically.
- **Do not** reject ordinary values such as `0.1` merely because they are not exactly representable in binary64. The conversion semantics are explicit as above and the effective hash reflects the resulting runtime float value.

#### 4.5.1 Field-by-field numeric runtime semantics (inspected read-only; v1.1.0 implementation prerequisite for unresolved cases)

Source inspected read-only: `scanline/levels.py`, `scanline/sessions.py`, `scanline/scan.py`, `scanline/validation/r4.py`, `scanline/validation/r5.py`, `scanline/validation/utils.py`, `scanline/schema.py`, and config fixtures under `config/`. No schema model exists in code today; observed semantics below are traced to actual consumers.

| Module / config family | Field/path | Schema type (declared target for v1.1.0) | Runtime type actually consumed today | Normalization/conversion rule (observed -> proposed effective) | Range/integrality constraints (observed) | Representation in `effective_config` | Effective representation hashes exact consumed value? | Status |
|---|---|---|---|---|---|---|---|---|
| `level_proximity` | `atr_window` | integer | `int` (`_validate_params` rejects bool/non-int/<=0; returns `int(atr_window)`; emitted as `params["atr_window"]`) | Parse exact decimal token; require mathematically integral integer; normalize to JSON integer in effective config. | integer, `> 0`; bool rejected. | JSON integer | Yes, if normalized to integer. | Resolved by code trace. |
| `level_proximity` | `proximity_bands_atr` (legacy list form) | schema-versioned union normalized to object | list of one numeric or dict with `structural`/`grid`; consumed as floats in `bands` dict | Accept legacy `[x]` only where schema version permits; normalize to `{"structural": <float>, "grid": <float>}` in effective config. | each band numeric and not bool; list form requires length 1; dict form requires both keys. | object with numeric `structural`,`grid` in canonical effective form | Only after explicit normalization; raw token form is not preserved in effective hash. | Resolved shape; float exactness policy required (see float rows). |
| `level_proximity` | `proximity_bands_atr.structural` | binary float (proposed) | `float(structural_band)` in levels runtime | Exact-decimal parse -> schema validate finite numeric -> convert to binary64 at normalization boundary; effective snapshot stores shortest round-trip decimal of runtime float. | finite numeric; not bool; semantic range otherwise not explicitly enforced in code. | canonical decimal string of runtime float value | Yes for runtime float consumed; not raw token identity. | Resolved by proposed policy; implementation must codify. |
| `level_proximity` | `proximity_bands_atr.grid` | binary float (proposed) | `float(grid_band)` | Same as structural band. | finite numeric; not bool. | shortest round-trip decimal of runtime float | Yes for runtime float consumed. | Resolved by proposed policy. |
| `level_proximity` | `grid_steps.<SYMBOL>` | type-sensitive numeric (schema-declared; integer or binary64) | `float(step)` for comparisons/range generation; **formatting branch inspects original Python type**: `isinstance(grid_steps.get(symbol), int) and float(...).is_integer()` causes integer-valued grid prices to be emitted as `int` when step is `int` (`scanline/levels.py:150-151`). `step` is also converted to `float` for arithmetic (`:133`). | Normalize to typed numeric cell per §4.5.2: integer-source consumed as integer -> `{"numeric_type":"integer","value":<int>}`; binary64-source consumed as float -> `{"numeric_type":"binary64","value":"<shortest-round-trip-decimal>"}`. Do **not** collapse `5` and `5.0`. | `> 0` when present; absent means no grid levels for symbol. | Typed numeric cell in `effective_config`; runtime projection returns native `int`/`float`. | Yes, for consumed runtime value/type as represented by the typed cell. | **Resolved by §4.5.2 (Option A).** Implementation pending. |
| `level_proximity` | event `level_price`/`distance_atr` (emitted, not config) | N/A | float/numeric event fields | Not config inputs. | N/A | N/A | N/A | Out of config-hash subject. |
| `session_anomalies` | `expected_bars` (top-level or cluster-resolved) | integer | `int` via `_require_int(..., minimum=0)`; compared as `int(...)` in R1 | Exact-decimal parse; require mathematically integral integer; normalize to integer in effective config. | integer, `>= 0`; bool rejected. | JSON integer | Yes if normalized. | Resolved. |
| `session_anomalies` | `expected_sun_bars` | integer | `int` via `_require_int(..., minimum=0)` | Same as integer fields. | integer, `>= 0`. | JSON integer | Yes. | Resolved. |
| `session_anomalies` | `stub_tolerance` | integer | `int` via `_require_int(..., minimum=0)` | Same. | integer, `>= 0`. | JSON integer | Yes. | Resolved. |
| `session_anomalies` | `sun_tolerance` | integer | `int` via `_require_int(..., minimum=0)` | Same. | integer, `>= 0`. | JSON integer | Yes. | Resolved. |
| `session_anomalies` | maintenance fields (`maintenance_local_*`, `maintenance_start/end`, `rollover_local_*`, `maintenance_utc_*`, aliases) | canonical maintenance object (schema-declared) | parsed as `HH:MM` by `_validate_hhmm`/`_parse_hhmm`; local vs fixed-UTC affects `_maintenance_utc_interval` behavior; `_fixed_utc` flag derived | Normalize to canonical `maintenance` object per §5.5.2: `{"mode":"local"|"fixed_utc","start_hhmm":"HH:MM","end_hhmm":"HH:MM"}`. Preserve mode; never silently drop/reinterpret/replace. | valid `HH:MM`, start != end; mode determined by explicit schema rules | canonical maintenance object in `effective_config` | Yes. | **Resolved by §5.5.1-§5.5.5.** Implementation pending. |
| `session_anomalies` | `zone` | string | `ZoneInfo(zone)` validated | Preserve validated string. | non-empty valid IANA/ZoneInfo zone. | JSON string | Yes. | Resolved. |
| all modules | `param_version`, `frozen_at`, `module`, `config_schema_version` | string | string metadata; module normalized by alias map | Module alias normalized in effective config; others preserved as validated strings. | required non-empty where schema requires. | JSON strings | Yes. | Resolved. |

**Discrepancies / unresolved prerequisites (must be resolved before claiming full design verification):**

1. **`grid_steps.<SYMBOL>` type-sensitive formatting (resolved by provenance contract; implementation pending):** `scanline/levels.py:150-151` inspects the original `grid_steps.get(symbol)` Python type. For an integer-valued step, `int` emits integer-typed `level_price` values; `float` emits float-typed `level_price` values. This is observable in emitted events and therefore in event-byte identity. The proposal selects **Option A: preserve type semantics explicitly** in effective config and hash (§4.5.2). Option B (normalizing behavior away) would require a separately authorized implementation change and must not be implied by this proposal.
2. **No formal schema layer in code:** Current validation is ad hoc in detectors/validators. v1.1.0 must introduce explicit schema declarations per field (integer/Decimal/binary float/string/typed-numeric/etc.) before `load_config()` can be authoritative.
3. **Float-backed config fields:** Current runtime casts some values to `float` (`proximity_bands_atr`, `grid_steps` arithmetic). Proposed policy is binary64 conversion at normalization with shortest round-trip decimal in effective snapshot for float-backed fields; this is a deliberate contract choice and must be approved and tested. It does not apply to fields whose runtime type semantics are intentionally preserved (e.g. `grid_steps` integer-vs-float formatting semantics).
4. **Session config effective shape:** `sessions.py` accepts multiple aliases/containers/fallbacks. §5.5 freezes the canonical resolved shape, maintenance normalization, and fail-closed rules. Implementation must inventory all accepted forms and prove no silent behavior change for currently accepted configs.
5. **Schema identity/family resolution:** v1.1.0 requires authoritative schema-version and config-family resolution (§7.5). No registry exists in code today.

If any implementation-pending item remains unresolved at implementation time, the implementation is not fully verified against this proposal.

#### 4.5.2 Type-preserving effective representation for type-sensitive numeric fields (normative)

This section freezes the effective representation for schema fields whose observable runtime behavior depends on original numeric type. It resolves the `grid_steps.<SYMBOL>` gap identified by source inspection: `scanline/levels.py` uses `float(step)` for arithmetic but inspects `isinstance(grid_steps.get(symbol), int) and float(...).is_integer()` when formatting emitted `level_price` values, so integer `5` and binary64 `5.0` can produce different emitted event bytes. Generic canon-v1 numeric canonicalization would collapse both to `5`; therefore type-sensitive fields MUST NOT be represented as plain canon-v1 JSON numbers in `effective_config`.

**Typed numeric cell (schema-owned):**

For every schema-declared type-sensitive numeric field, the effective configuration stores a **typed numeric object** with exactly these members:

| Member | Type | Meaning |
|---|---|---|
| `numeric_type` | string | `"integer"` or `"binary64"` |
| `value` | integer or string | Integer cell: JSON integer equal to the consumed integer value. Binary64 cell: JSON string containing the shortest round-trip decimal representation of the consumed IEEE-754 binary64 runtime value. |

**Normative forms:**

- **Integer cell:** `{"numeric_type":"integer","value":5}`
  - `value` MUST be a JSON integer token in canonical form (canon-v1 number rules apply to that integer token).
  - The consumed runtime value is `int(value)` / Python `int` with integer semantics.
  - Mathematically integral source tokens accepted for an integer-typed schema field (e.g. `5`, `5.0`, `5e0`, only where schema permits integral-token normalization) normalize to the same integer cell when the consumed integer value is identical.
- **Binary64 cell:** `{"numeric_type":"binary64","value":"5.0"}`
  - `value` MUST be a JSON string whose content is the shortest round-trip decimal representation of the actual runtime `binary64` value consumed by the module (Python-equivalent: `repr(float(runtime_value))` in current CPython semantics, i.e. a decimal string that round-trips to the same IEEE-754 binary64). The string is preserved exactly as a JSON string by canon-v1 (no numeric recanonicalization of its contents).
  - The consumed runtime value is `float(value_string)` / IEEE-754 binary64 with float semantics.
  - Ordinary binary64 rounding is part of declared binary64 runtime semantics; effective config records the consumed runtime float, not an unrounded source token.

**Collision-safety and distinctness:**

- Integer and binary64 cells are distinguished by `numeric_type` and by `value` JSON type (`integer` number vs `string`). They cannot collide under canon-v1 object canonicalization.
- For a type-sensitive field, an integer-source consumed value `5` and a binary64-source consumed value `5.0` have different effective representations and different `config_hash` values, because observable runtime behavior differs.
- The typed object is schema-owned: it appears only at schema-declared type-sensitive field locations. Generic canon-v1 still applies to ordinary JSON objects/arrays/strings/numbers elsewhere; it does not gain special-case behavior for arbitrary objects that happen to contain `numeric_type`.

**Schema identification and validation:**

- The schema registry/field declarations MUST identify every type-sensitive numeric field. For v1.1.0 known case: `level_proximity.grid_steps.<SYMBOL>` is type-sensitive.
- For a type-sensitive field, raw parsed numeric JSON tokens are accepted only as schema input; `load_config()` converts them to the typed numeric cell in `effective_config`.
- Untyped plain JSON numeric values MUST NOT silently enter a type-sensitive effective field. After validation/normalization, every type-sensitive field in `effective_config` is a typed numeric cell.
- If schema metadata is missing, ambiguous, or does not declare the type-sensitive field, `load_config()` fails closed; no v1.1.0 provenance-complete manifest/snapshot/hash is emitted.

**Runtime projection (`LoadedConfig` relationship):**

- `raw_bytes`/`parsed` preserve the original input; `raw_snapshot_bytes` is byte-identical to `raw_bytes`.
- `effective_config` contains typed numeric cells for type-sensitive fields. This is the config_hash subject; `effective_snapshot_bytes` are canon-v1 UTF-8 bytes of `effective_config` with no trailing newline; `config_hash = SHA256(effective_snapshot_bytes)`.
- `LoadedConfig` MUST also provide the detector-facing runtime projection used by scan execution (implementation field name may be `runtime_config` or equivalent; the proposal requires the projection, not a specific private name). In that projection, typed numeric cells are projected back to native runtime values: integer cell -> `int`, binary64 cell -> `float` (`binary64`). Detectors receive native numeric types and values; they MUST NOT be required to interpret typed provenance cells.
- The projection is deterministic and lossless with respect to the consumed runtime value/type declared by the cell. It does not alter `effective_snapshot_bytes` or `config_hash`.

**Float/bounds policy interaction:**

- Binary64 cells use the finite IEEE-754 binary64 conversion policy in §4.5. Overflow to infinity and nonzero underflow to zero are rejected at normalization.
- The `value` string is the shortest round-trip decimal of the runtime float; canon-v1 does not rewrite its characters as a numeric token because it is a JSON string.
- Integer cells are bounded by integer schema/range rules; the integer JSON number inside the cell remains subject to generic canon-v1 numeric representation rules.

**Positive golden vectors (typed numeric cells):**

| Vector ID | Input (effective typed value) | Expected canonical UTF-8 JSON | Expected SHA-256 | Verification result |
|---|---|---|---|---|
| T1 | `{"numeric_type":"integer","value":5}` | `{"numeric_type":"integer","value":5}` | `2ac1f847d99827f1b6e5873759065fa719c183d71ed1fab076ddec78fee62b50` | PASS (independent /tmp rerun 2026-11-21; idempotent) |
| T2 | `{"numeric_type":"binary64","value":"5.0"}` | `{"numeric_type":"binary64","value":"5.0"}` | `2677df426ffd05d12b5ddd6567be5e168783c957a8549f5d0f3ddd720057f45f` | PASS (independent /tmp rerun 2026-11-21; idempotent) |

**Required assertions:**

- T1 and T2 have different canonical bytes and different SHA-256 hashes.
- Re-canonicalizing parsed canonical bytes is idempotent for both.
- Runtime projection yields `int` for T1 and `float` (not `int`) for T2; both numeric values are mathematically 5, but runtime type distinction is preserved.

### 4.6 Examples (normative illustrations)

- **Exact parser behavior:** JSON token `-0.00500e+1` parses exactly to decimal −0.05; canonical form is `-0.05`. Token `1e2` parses exactly to 100; canonical `100`.
- **Integer field rejecting fractional value:** an integer-declared field with input `1.5` → schema validation rejects (not integral). Input `2.0` is integral in value; acceptance depends on explicit normalization rules for that schema version (if normalization converts to integer `2`, the effective record contains integer `2` which canonicalizes as `2`; if the schema forbids non-integer tokens outright, reject). The rules above require that fractional values like `1.5` are rejected for integer fields.
- **Float-backed field defined conversion and effective canonical value:** a float-declared field with input token `0.1` (exact decimal 1/10) is converted to binary64 at normalization; the effective config records the shortest round-trip decimal of that runtime float (e.g. the canonical decimal string corresponding to `Decimal(repr(float(0.1)))` in practice), and `config_hash` is computed over that effective representation. This documents rounding as declared runtime semantics.
- **Overflow and underflow rejection (float-backed):** a value that overflows to binary64 infinity is rejected. A **nonzero** value that underflows to binary64 zero is rejected.
- **Numeric limit rejection:** a token with absolute exponent `|e| > 308` is rejected by §4.4; a token whose mantissa digit count exceeds 128 is rejected. Under those accepted-input limits, canonical expanded length excluding sign is mathematically bounded to `<= 437` (§4.4.2); any token whose canonical expansion would exceed 437 is unreachable for accepted input and should be treated as rejected by the coefficient/exponent/input rules. A defensive `<= 512` output assertion, if retained, is unreachable-guard only and does not authorize acceptance.
- **Type-sensitive grid step (normative):** for schema-declared `grid_steps.<SYMBOL>`, source integer `5` normalizes to effective cell `{"numeric_type":"integer","value":5}` and source binary64 `5.0` normalizes to effective cell `{"numeric_type":"binary64","value":"5.0"}`. The effective cells, canonical bytes, and `config_hash` values differ; runtime projection returns `int(5)` and `float(5.0)` respectively. This preserves the observable formatting/type behavior in `scanline/levels.py`.

### 4.7 Unicode, strings, duplicate keys, idempotence (restated)

- No Unicode normalization in v1 (NFC/NFD remain distinct byte/content differences in the JSON source and are preserved as parsed strings in the effective record subject to JSON rules).
- Invalid UTF-8, lone surrogate codepoints, and invalid escape sequences are rejected.
- Duplicate object member names are rejected at parse time.
- For any valid input `x` accepted by canon-v1 parsing+effective canonicalization of the subject, `canonicalize(canonicalize(x_effective)) == canonicalize(x_effective)` holds by construction of the canonical form.

## 5. Effective configuration builder (`load_config()`)

SCANLINE must have one authoritative configuration boundary. `config_hash` is computed only from the effective validated config produced by this boundary.

### 5.1 Contract

```text
load_config(param_path: Path | str, *, schema_version: str | None = None) -> LoadedConfig
```

**Inputs:**

| Input | Type | Meaning |
|---|---|---|
| `param_path` | path | Parameter file to read once. |
| `schema_version` | optional str | Expected/selected schema validation version; if omitted, resolved from config content and supported schema registry. |
| `symbol_scope` / scan context | optional, schema-dependent | Required only where effective normalization depends on resolved scan scope (e.g. session `symbols` map). If required and missing/ambiguous, `load_config()` fails closed for v1.1.0 provenance. |

**Returned `LoadedConfig` fields:**

| Field | Type | Meaning |
|---|---|---|
| `raw_bytes` | `bytes` | Exact original file bytes read once from `param_path`. |
| `parsed` | `dict`/object | Parsed JSON object after token-preserving parse and duplicate-key rejection; no semantic defaults applied. |
| `effective_config` | `dict` | Validated, normalized, module-aware effective config actually consumed by SCANLINE. Type-sensitive numeric fields are represented as typed numeric cells per §4.5.2. |
| `param_sha256` | `str` | `SHA256(raw_bytes).hexdigest()` (lowercase hex). This is the single public raw-provenance digest field; it is the same digest currently stored in headers/manifests as raw-byte param identity. |
| `config_hash` | `str` | `sha256(canonicalize(effective_config))` under canon-v1. |
| `config_hash_algorithm` | `str` | `"sha256"`. |
| `config_canonicalization_version` | `str` | `"SCANLINE-config-canon-v1"`. |
| `config_hash_subject` | `str` | `"effective_validated_config"`. |
| `config_schema_version` | `str` | Required non-null schema version identifier resolved/validated by `load_config()` for v1.1.0 provenance records (§7.3). |
| `raw_snapshot_bytes` | `bytes` | Byte-identical snapshot payload for `param_snapshot.raw.json`; equals `raw_bytes`. |
| `effective_snapshot_bytes` | `bytes` | Canonical UTF-8 bytes for `param_snapshot.effective.json`; hash equals `config_hash`. These bytes are the exact canon-v1 serialization of `effective_config`, including typed numeric cells where schema requires them. |
| `param_file` | `str` | Basename of original param file. |
| `module` | `str` | Normalized canonical module ID. |
| `param_version` | `str` | Validated param version from effective config. |
| `frozen_at` | `str` | Validated frozen_at from effective config. |
| `runtime_config` (required projection) | `dict` | Deterministic detector-facing projection of `effective_config` where typed numeric cells are projected to native runtime values (`integer` cell -> `int`, `binary64` cell -> `float`). This projection is not separately hashed; `config_hash` remains over `effective_snapshot_bytes`. |

**Raw-hash field decision (resolved):** `LoadedConfig` exposes **`param_sha256` only** as the public/raw provenance digest. `raw_sha256` is **not** a separate field and is not computed separately; it is an exact alias in prose only for compatibility with existing naming. Implementations MUST compute the raw digest once from `raw_bytes` and expose it as `param_sha256`.

### 5.2 Boundary rules

1. **Single read:** `raw_bytes` is read once. Scanner, validator, R4, snapshot writer, and manifest writer must use `LoadedConfig`; no second path read for hash/snapshot.
2. **Validation before effective hash:** `config_hash` is computed only after schema validation and effective-config construction succeed.
3. **Raw/effective separation:** raw snapshot preserves supplied bytes; effective snapshot preserves normalized consumed config.
4. **No runtime metadata in effective config:** scan ID, execution timestamps, output paths, code state, corpus metadata, and manifest completion metadata are excluded.
5. **Deterministic normalization:** module alias normalization, allowed defaulting, and shape normalization must be explicit, versioned, and tested.
6. **Type-sensitive numeric projection:** schema-declared type-sensitive numeric fields normalize to typed numeric cells in `effective_config` (§4.5.2). The runtime projection exposes native `int`/`float` values to detectors. Untyped numeric values are rejected for those fields.
7. **Fail-closed provenance:** if effective representation cannot be established deterministically, `load_config()` may support legacy read/validation only where explicitly allowed, but it MUST NOT produce v1.1.0 `effective_snapshot_bytes`, `config_hash`, or a provenance-complete manifest.

### 5.3 Effective-config normalization (v1 proposal)

| Area | Rule |
|---|---|
| Module | `module_1` normalizes to `level_proximity` in effective config; raw snapshot retains original bytes. Unknown module strings are not silently normalized into supported modules. |
| Level proximity bands | Legacy list `[x]` may normalize to `{"structural": x, "grid": x}` only if schema version explicitly permits this normalization; normalized form is what gets hashed. |
| `grid_steps` | Type-sensitive numeric field. Effective config stores a typed numeric cell per §4.5.2 (`integer` or `binary64`); runtime projection supplies native `int`/`float` to detector. `5` and `5.0` MUST produce different effective representations/hashes. |
| Session config | Alias normalization/defaulting allowed only by explicit schema/version rules; effective config must be fully explicit and canonicalized as defined in §5.5. Raw snapshot retains original bytes/shape. |
| Unknown fields | **Rejected** unless a specific schema version explicitly permits them (§6). |
| Deprecated fields | Rejected unless schema version explicitly allows and defines migration/normalization. |

### 5.5 Session effective configuration shape (frozen for v1.1.0)

**Source trace (read-only):** `scanline/sessions.py` — `_CLUSTER_FIELD_ALIASES`, `_CLUSTER_CONTAINERS`, `_FIXED_UTC_KEYS`, `_find_cluster_record`, `_cluster_info`, `_normalize_args`, `_apply_contextual_symbol`, `validate_session_config`; `scanline/validation/r4.py` calls `validate_session_config(param_data)` for `session_anomalies`; `scanline/validation/r1.py` uses `utils.cluster_expected_bars` for retrospective schedule checks. Read-only inspection confirmed fixed-UTC acceptance in runtime (`maintenance_utc_start/end` and aliases set `_fixed_utc`, `_maintenance_utc_interval` interprets them as UTC clock times) and in tests (`tests/test_sessions.py::test_fixed_utc_unchanged`).

#### 5.5.1 Accepted maintenance-related input fields (complete)

| Accepted input field / alias | Where accepted | Input class | Validation rule (current observed) | Runtime interpretation (current observed) | Required/defaulted/conditional | Canonical effective representation (v1.1.0) | Included in `config_hash`? |
|---|---|---|---|---|---|---|---|
| `maintenance_local_start` | cluster record, flat top-level, top-level scalar fallback | local-time | `_validate_hhmm`: string `HH:MM`, `00:00-23:59` | local clock time in resolved `zone`; converted through `ZoneInfo` per date in `_maintenance_utc_interval` | default `"17:00"` if no maintenance start supplied | `maintenance.mode="local"`, `maintenance.start_hhmm=<HH:MM>`, `maintenance.end_hhmm=<HH:MM>`, `maintenance.source_field=<accepted alias>` optional audit metadata excluded from hash; canonical hash fields are mode/start/end only | Yes, via canonical `maintenance` object |
| `maintenance_start_local` | alias same as above | local-time | same | same | alias; conflicts rejected | normalized to canonical local `maintenance` object | Yes |
| `rollover_local_start` | alias same as above | local-time | same | same | alias; conflicts rejected | normalized to canonical local `maintenance` object | Yes |
| `maintenance_start` | alias same as above | local-time (generic alias) | same | same | alias; conflicts rejected | normalized to canonical local `maintenance` object | Yes |
| `maintenance_local_end` | cluster record, flat top-level, top-level scalar fallback | local-time | `_validate_hhmm`; start != end | local clock end in resolved `zone`; window may cross day when end <= start | default `"18:00"` if no maintenance end supplied | canonical local `maintenance.end_hhmm` | Yes |
| `maintenance_end_local` | alias | local-time | same | same | alias | canonical local `maintenance.end_hhmm` | Yes |
| `rollover_local_end` | alias | local-time | same | same | alias | canonical local `maintenance.end_hhmm` | Yes |
| `maintenance_end` | alias | local-time (generic alias) | same | same | alias | canonical local `maintenance.end_hhmm` | Yes |
| `maintenance_utc_start` | cluster record / flat accepted field | fixed-UTC time | `_validate_hhmm` | fixed UTC clock time; `_maintenance_utc_interval` builds UTC window directly, no zone conversion of clock fields; `_fixed_utc` flag set | conditional: if present, fixed-UTC mode applies; conflicts with conflicting start aliases rejected | `maintenance.mode="fixed_utc"`, `maintenance.start_hhmm=<HH:MM>`, `maintenance.end_hhmm=<HH:MM>` | Yes |
| `maintenance_start_utc` | alias | fixed-UTC time | same | same | alias | same fixed-UTC canonical object | Yes |
| `maintenance_utc_end` | cluster record / flat accepted field | fixed-UTC time | `_validate_hhmm`; start != end | fixed UTC clock end | conditional with fixed-UTC mode | canonical fixed-UTC `maintenance.end_hhmm` | Yes |
| `maintenance_end_utc` | alias | fixed-UTC time | same | same | alias | same fixed-UTC canonical object | Yes |
| `zone` / `timezone` / `tz` / `time_zone` | cluster record, top-level scalar fallback | timezone context | non-empty string, valid `ZoneInfo` | resolves local maintenance to UTC intervals; also part of session interpretation | default `"UTC"` | canonical `zone` string; remains in effective config | Yes |

**No omitted maintenance field:** every currently accepted maintenance-related input field above MUST be either (a) accepted and normalized into the canonical effective representation, or (b) rejected by explicit schema-versioned fail-closed validation. Silent omission, silent reinterpretation, and silent replacement are forbidden.

#### 5.5.2 Canonical maintenance effective representation (normative)

`symbols.<SYMBOL>.maintenance` is a required canonical object in the v1.1.0 session effective config:

```json
{
  "mode": "local" | "fixed_utc",
  "start_hhmm": "HH:MM",
  "end_hhmm": "HH:MM"
}
```

Rules:

- `mode` is explicit and required. It is `"fixed_utc"` only when an accepted fixed-UTC maintenance alias is present and validated; otherwise `"local"`.
- `start_hhmm`/`end_hhmm` are canonical `HH:MM` 24-hour strings as validated/normalized by schema rules. They preserve the consumed clock values; they do not absorb `zone`.
- `zone` remains a separate required effective field. For `mode="local"`, runtime interprets clock values in `zone`. For `mode="fixed_utc"`, runtime interprets clock values as fixed UTC; `zone` still exists as resolved session timezone context and MUST remain explicit in effective config to avoid ambiguity.
- Default local maintenance when no maintenance input is supplied: `{"mode":"local","start_hhmm":"17:00","end_hhmm":"18:00"}`.
- `start_hhmm == end_hhmm` is invalid (matches current runtime).
- Fixed-UTC aliases MUST NOT be normalized to local mode. Local aliases MUST NOT be normalized to fixed-UTC mode.
- The canonical `maintenance` object is part of the hashed effective config. `maintenance.source_field`, alias spellings, container shapes, and unresolved fallback chains are input provenance only and MUST NOT appear in effective config.

#### 5.5.3 Canonical session effective shape (v1.1.0 target)

The effective config for `session_anomalies` MUST be a single canonical JSON object representing the resolved configuration actually consumed.

Required top-level effective fields:

| Field | Type | Rule |
|---|---|---|
| `module` | string | canonical `"session_anomalies"` |
| `param_version` | string | validated non-empty string |
| `frozen_at` | string | validated timestamp string |
| `config_schema_version` | string | required non-null for v1.1.0 |
| `symbols` | object | map of canonical symbol -> resolved symbol config; keys sorted by Unicode codepoint in canonical bytes |

Required resolved per-symbol fields (`symbols.<SYMBOL>`):

| Field | Type | Rule |
|---|---|---|
| `expected_bars` | integer | resolved required integer >= 0 |
| `expected_sun_bars` | integer | resolved integer >= 0; default 0 |
| `zone` | string | resolved non-empty valid ZoneInfo name; default `"UTC"` |
| `maintenance` | object | canonical maintenance object per §5.5.2; required |
| `stub_tolerance` | integer | resolved integer >= 0; default 1 |
| `sun_tolerance` | integer | resolved integer >= 0; default 0 |

No alias names, no container variants, no `maintenance_utc_*`, and no legacy `maintenance_local_*` fields appear in the effective config. Raw snapshot preserves original input bytes.

#### 5.5.4 Normalization rules

- All accepted aliases map to canonical field names; aliases are not emitted in effective config.
- Container forms (`clusters`, `cluster_schedule`, `clusters_schedule`, `session_clusters`, `cluster_expected_bars`, dict/list/flat forms accepted by runtime) normalize to `symbols` map only where the resolved symbol scope is explicit.
- Conflicting alias values for the same canonical field are validation errors.
- Missing required `expected_bars` after resolution is a validation error.
- Defaults inserted by normalization are part of effective config and affect `config_hash`.
- Fixed-UTC maintenance input is normalized only to `maintenance.mode="fixed_utc"` with validated HH:MM values; it is never dropped and never reinterpreted as local zone-converted maintenance.
- Local maintenance input is normalized only to `maintenance.mode="local"`.

#### 5.5.5 Fail-closed conditions for session configs

A session config MUST be treated as **unsupported for v1.1.0 provenance emission** (fail closed) when any of the following applies:

| Condition | Behavior |
|---|---|
| Effective representation cannot be established deterministically from validated input + resolved schema | Reject v1.1.0 provenance emission; do not emit `param_snapshot.effective.json` or `config_hash` |
| Symbol scope required to resolve `symbols` map is ambiguous or unavailable to `load_config()` | Reject/fail closed for v1.1.0 provenance |
| Maintenance mode is ambiguous (e.g., conflicting fixed-UTC and local inputs that cannot be resolved by explicit schema rule) | Validation error / unsupported normalization; no provenance-complete manifest |
| Accepted maintenance alias present but schema-versioned normalization rule is missing | Unsupported schema/config normalization; fail closed |
| Any accepted field would be silently omitted, reinterpreted, replaced, or defaulted in a way not explicitly defined by schema version | Fail closed; no fabricated effective snapshot/hash |
| Config is readable under legacy rules but not representable under the v1.1.0 effective schema | May remain readable under legacy/runtime validation path only where existing behavior allows; MUST NOT receive v1.1.0 provenance-complete manifest, MUST NOT receive fabricated `param_snapshot.effective.json`, MUST NOT receive fabricated `config_hash` |
| Schema identity/family/version cannot be resolved authoritatively | Fail closed per §7.5.4 |

**Required result/reporting:** unsupported cases return/record a clear unsupported-schema or config-normalization result (implementation error code/name to be fixed at implementation time, but must be explicit and machine-testable). They are not "complete" v1.1.0 provenance manifests.

**No silent behavior change:** this freezes the target; implementation must inventory all accepted session config forms, including fixed-UTC maintenance, and prove no silent behavior change for currently accepted configs before enforcement.

### 5.4 `config_hash` and configuration-record identity

`config_hash` identifies the effective validated config content. `config_hash` does **not** include its own hash metadata (`config_hash`, `config_hash_algorithm`, `config_canonicalization_version`, `config_hash_subject`, snapshot names/hashes/sizes), and therefore has no circularity.

The **configuration-record identity** used for provenance/audit is broader than `config_hash` alone and includes:

- `config_hash` (effective validated config content),
- `config_hash_algorithm`,
- `config_canonicalization_version`,
- `config_hash_subject`,
- `param_version` (declared config label from effective config),
- `frozen_at` (declared config freeze/provenance timestamp from effective config),
- `module` / config family scope.

This means `param_version` and `frozen_at` participate in complete configuration-record identity and audit checks, while remaining inside the hashed effective config content unless a future version explicitly defines a separate semantic-only hash.

---

## 6. Unknown-field policy

**Policy (unambiguous):** **Schema validation rejects unknown fields unless the specific schema version explicitly permits them.** No silent dropping of unknown fields.

- **Default:** any object field not defined by the active (resolved) schema version is invalid for a schema-validated effective configuration.
- **Exception:** only a **specific schema version** that explicitly permits a field (with documented scope, type/shape, defaults, and semantics) may admit it. A future schema version may introduce a field; that allowance applies only to configurations validated under that schema version (or later versions that explicitly carry forward the rule). Older schema versions remain unchanged in meaning: inputs containing that field are rejected under older validators unless the older schema version text explicitly allowed it (it did not).
- **No silent drops:** the canonicalizer/hashing pipeline MUST NOT silently discard unknown fields. If a field is accepted, it is validated, represented in `effective_config` exactly as defined by that schema version, and therefore included in `effective_snapshot_bytes` and `config_hash`. If it is not accepted, `load_config()` fails validation.
- **Distinction — generic serializer tests vs schema-validated effective configs:** generic `SCANLINE-config-canon-v1` serialization/canonicalization tests may exercise arbitrary valid JSON structures to prove deterministic serialization behavior (including behavior on unknown keys present in a test fixture object). Those tests do **not** imply that scanner parameter schemas accept unknown fields. **Effective-config hashing in SCANLINE applies only to schema-validated configs that pass `load_config()`** under the declared schema rules.
- **Accepted effective configuration content:** the accepted `effective_config` (and thus the effective snapshot/hash subject content) contains **all permitted semantic fields** defined by the schema/version and **none** of the fields that would have been silently ignored — because ignored fields are not permitted. Any field that survives validation is either part of the defined schema surface for that version or explicitly permitted by that version’s exception rule.
- **Manifest/metadata objects:** evolution of `scanner_data_manifest.json` follows SCAN-018B rules (separate concern from parameter config schema strictness). This section governs **parameter/effective configuration schemas** validated by `load_config()`.

---

## 7. Dual snapshots and SCAN-018B manifest integration

### 7.1 Snapshot files (exact)

1. **`param_snapshot.raw.json`**
   - Exact byte-for-byte copy of the original parameter input (`raw_bytes`).
   - `SHA256(param_snapshot.raw.json bytes on disk) == param_sha256`.
   - Published so raw-byte provenance is auditable without trusting the original path at read time.

2. **`param_snapshot.effective.json`**
   - Exact canonical effective configuration bytes (`effective_snapshot_bytes`), UTF-8, compact JSON per `SCANLINE-config-canon-v1`, **no trailing newline**.
   - `SHA256(param_snapshot.effective.json bytes on disk) == config_hash`.

Both snapshots MUST:
- Be written using the existing same-directory temporary-file, flush/fsync, and atomic-replace pattern used by SCAN-018B publication (e.g. write `*.tmp.<pid>`, `flush()`, `os.fsync(fileno())`, `os.replace(tmp, final)`, then best-effort directory sync) before the final manifest is made durable as the completion marker.
- Be durably published before writing `scanner_data_manifest.json` with `status="COMPLETE"`.
- Be included in `scanner_data_manifest.json`’s `outputs` inventory with exact `name`, `sha256`, and `size_bytes` values.
- Be verified by `is_scan_complete()` for a **v1.1.0** manifest (see §7.3).

Stable relative names within the scan directory: `param_snapshot.raw.json`, `param_snapshot.effective.json`. These names are fixed; they MUST remain covered by existing path-traversal and symlink protections (no absolute paths, no `..`, no escaping the scan directory).

### 7.2 Capture and publication sequence (normative)

1. `load_config()` reads `raw_bytes` once, parses from retained bytes, validates and builds `effective_config`, produces `raw_snapshot_bytes == raw_bytes`, `effective_snapshot_bytes` (canonical), `param_sha256`, `config_hash`, and all required metadata (§5). If effective representation cannot be established for v1.1.0 (e.g. §5.5.5), stop: no v1.1.0 effective snapshot/hash/manifest.
2. Publish `events.json` via the existing atomic publication path (as today), using data derived from `LoadedConfig.runtime_config` / validated runtime inputs (not typed provenance cells).
3. Publish `param_snapshot.raw.json` from `raw_snapshot_bytes` via the same atomic temp+fsync+`os.replace` pattern.
4. Publish `param_snapshot.effective.json` from `effective_snapshot_bytes` via the same atomic temp+fsync+`os.replace` pattern.
5. Compute/assemble `scanner_data_manifest.json` including `outputs` entries for `events.json`, `param_snapshot.raw.json`, `param_snapshot.effective.json` with correct `sha256`/`size_bytes`.
6. Publish manifest last as the completion marker only after required outputs are durable.

**Prohibitions:** never reopen the mutable parameter path to compute a hash or rebuild a snapshot during publication; never write manifest before the two snapshots (and events output as required) are durably published; never fabricate effective snapshot/hash for unsupported/legacy-unrepresentable configs.

### 7.3 Manifest version transition (precise)

- **Existing v1.0.0 manifests** remain readable under the existing **v1.0.0** contract. `is_scan_complete()` behavior for v1.0.0 records is unchanged in meaning: they are validated by the v1.0.0 rules as defined by SCAN-018B (including the legacy categories described there). Absence of snapshots/config provenance fields in a v1.0.0 record means **legacy/unverifiable provenance** under the new provenance contract, **not** evidence that the scan failed.
- **New config-provenance manifests** use manifest version **`1.1.0`** (`manifest_version` string `"1.1.0"`).
- For a manifest declaring **`1.1.0`**, the following are **required** and **integrity-checked** by verification logic:
  - All fields required by the v1.0.0 base contract that remain applicable (scan identity, status `COMPLETE`, execution timestamps per contract, outputs list rules, etc.), **plus** the additive provenance fields listed below and both snapshot outputs present and consistent.
  - `config_hash` (lowercase hex SHA-256).
  - `config_hash_algorithm` == `"sha256"`.
  - `config_canonicalization_version` == `"SCANLINE-config-canon-v1"`.
  - `config_hash_subject` == `"effective_validated_config"`.
  - `config_schema_version` (**required, non-null string**) for every v1.1.0 config-provenance manifest.
  - Snapshot references/fields as specified below (`config_snapshot_raw`, `config_snapshot_effective`) and corresponding `outputs` entries.
  - `is_scan_complete()` (or the v1.1.0 verifier) MUST verify: declared outputs exist inside the scan directory (containment + no symlink escape), hashes and sizes match, `param_snapshot.raw.json` SHA-256 equals `param_sha256`, `param_snapshot.effective.json` SHA-256 equals `config_hash`, and hash/algorithm/canonicalization/subject/schema-version metadata fields are present and consistent. A manifest MUST NOT be marked v1.1.0 provenance-complete when §5.5.5 fail-closed conditions apply.
- **Minor version is an additive contract extension**; do **not** silently reinterpret v1.0.0 records as v1.1.0. Version parsing/dispatch follows SCAN-018B rules (unknown major rejected as unverifiable in that framework; compatible minors handled per contract).
- **No fabrication:** do not fabricate snapshots or canonical hashes for historical records.

**`config_schema_version` decision (resolved):** For v1.1.0, `config_schema_version` is **required and must be a non-null string**. Rationale: effective-config interpretation, allowed normalization, unknown-field handling, and numeric conversion semantics are schema-version-dependent (§4–§6); omitting schema identity makes provenance ambiguous. `null` is not permitted in v1.1.0. If a future real supported use case needs schema identity unavailable, that case requires a separately approved contract revision that defines the exact condition, deterministic interpretation rules, and `config_family` derivation; it is not an implementation-time option for v1.1.0.

### 7.5 Schema identity and config-family resolution (frozen for v1.1.0)

This section defines how each supported config family obtains `config_schema_version` and `config_family`. It prevents implicit schema guessing.

#### 7.5.1 Authoritative schema-version source

`config_schema_version` is the **authoritative schema identity** for validation, normalization, effective-config construction, and hash interpretation.

**Authoritative source (v1.1.0):** a **schema registry entry** resolved by canonical `module` (config family) and the config's declared `param_version`/schema compatibility rule, as recorded in repository-controlled schema metadata. The registry is code/config metadata owned by SCANLINE, not inferred from arbitrary file contents beyond validated fields.

**Resolution order (normative):**

1. **Canonical module resolution:** parse raw JSON, validate top-level `module` as string, normalize via explicit alias map (`module_1` -> `level_proximity`) only through schema-aware loader rules. Unknown/unsupported module fails.
2. **Config-family resolution:** derive `config_family` from canonical module/schema metadata (§7.5.2). For current modules, `config_family == canonical module` unless an explicit schema registry entry declares a subfamily.
3. **Schema-version resolution:** look up `(config_family, param_version)` or family-declared schema mapping in the authoritative schema registry. The registry entry MUST declare: `config_family`, supported `param_version` selectors/mappings, `config_schema_version`, validator/normalizer id, and effective-config shape version. The resolved `config_schema_version` is written into `LoadedConfig.config_schema_version` and required manifest field.
4. **Validation/normalization:** run the schema validator/normalizer identified by that registry entry. Unknown fields/defaults/aliases/numeric type semantics are interpreted only under that resolved schema version.

**No silent fallback:** if module/family/schema version cannot be resolved unambiguously, `load_config()` MUST fail with an explicit error. A v1.1.0 manifest MUST NOT be emitted when schema identity cannot be resolved.

#### 7.5.2 Stable config-family identity

`config_family` is a stable, explicit identity derived from module/schema metadata, not from file path or basename.

| Canonical module | Config family | Current observed config files | Schema-version source (v1.1.0 implementation requirement) |
|---|---|---|---|
| `level_proximity` | `level_proximity` | `config/scanner_params.level_proximity*.json` (observed: 1.0.0, 1.1.0, 2.0.0, 2.1.0) | Registry mapping for `level_proximity` + `param_version` -> `config_schema_version` |
| `session_anomalies` | `session_anomalies` | no canonical config file observed in `config/` during this read-only pass; schema family still reserved by module identity | Registry mapping required before v1.1.0 manifests can be emitted for this family |

**Rules:**

- `config_family` MUST be stable across config file renames/moves. Filenames are discovery hints only.
- `param_version` is not a global namespace and MUST NOT be used alone as family identity. The same `param_version` string in different families is not comparable.
- If future schema introduces subfamilies under one module, the registry must declare an explicit `config_family` discriminator; module alone becomes insufficient.
- The manifest may include `config_family` as an additive v1.1.0 field if implementation chooses; if omitted, verifier derives it only through the same authoritative registry rule. This proposal recommends including it explicitly in manifest/runtime metadata to avoid ambiguity.

#### 7.5.3 Relationship between module, config family, schema version, and param file

| Concept | Meaning | Authoritative? | Source |
|---|---|---|---|
| Parameter file path/name | Discovery/input location | No | operator invocation / scan args |
| `module` | Canonical module identity | Yes, after alias normalization | parsed config + module alias map |
| `config_family` | Stable schema/config family identity | Yes | schema registry / module metadata |
| `param_version` | Declared config label within family | Yes as label; not identity alone | effective config |
| `config_schema_version` | Schema/normalization contract version | Yes | schema registry resolution |
| `param_sha256` | Raw bytes identity | Yes | raw file bytes |
| `config_hash` | Effective validated config identity | Yes | canonical effective bytes |

A filename like `scanner_params.level_proximity-2.1.0.json` is a discovery hint. It MUST NOT be the authoritative source of module, family, or schema version. Authoritative identity comes from validated content + registry resolution.

#### 7.5.4 Missing or ambiguous schema identity

`load_config()` and v1.1.0 manifest emission MUST fail when:

- `module` is missing, non-string, unknown, or ambiguously normalized.
- `param_version` is missing/invalid where required for schema resolution.
- No registry entry matches `(config_family, param_version)` or declared schema selector.
- Multiple registry entries match ambiguously.
- Resolved schema version is null/empty/non-string.
- Config content requires a schema feature/field not permitted by resolved schema version.
- File basename implies a different family/version than validated content+registry resolution; basename may be logged for diagnostics but cannot override authoritative resolution.

**Failure mode:** explicit validation/provenance error; no manifest `status="COMPLETE"`, no v1.1.0 provenance manifest emitted, no fabricated `config_schema_version`.

#### 7.5.5 Audit-only config-version integrity alignment

Version-integrity comparisons remain audit-only (§8), but they are scoped by `(module, config_family, param_version, config_canonicalization_version, config_hash_subject)` and must use registry-resolved family identity. A `param_version` collision across families is not a mismatch; it is out of scope because family differs.

### 7.4 Exact additive fields for v1.1.0 (normative names)

When `manifest_version == "1.1.0"` and config provenance is recorded (the new path), the manifest MUST include at least:

- `config_hash` (string, hex)
- `config_hash_algorithm` (string; `"sha256"`)
- `config_canonicalization_version` (string; `"SCANLINE-config-canon-v1"`)
- `config_hash_subject` (string; `"effective_validated_config"`)
- `config_schema_version` (string; **required, non-null** for v1.1.0)
- `config_snapshot_raw` (string; fixed value `"param_snapshot.raw.json"`)
- `config_snapshot_effective` (string; fixed value `"param_snapshot.effective.json"`)

Also include existing raw provenance fields unchanged: `param_file`, `param_sha256`, `param_version`, `frozen_at` (and `module`/other v1.0.0 fields as applicable).

`outputs` inventory MUST include entries for:

```json
{"name": "events.json", "sha256": "<...>", "size_bytes": <...>},
{"name": "param_snapshot.raw.json", "sha256": "<param_sha256>", "size_bytes": <...>},
{"name": "param_snapshot.effective.json", "sha256": "<config_hash>", "size_bytes": <...>}
```

All file references and output inventory entries use **stable relative names** within the scan directory and remain covered by existing path-traversal and symlink protections. (Osiris, as always, 8''x9'' kicker safe for family viewing… joking aside: no escaping the scan dir.)

`is_scan_complete()`/verifier behavior (target): for manifests declaring these snapshots/hashes, verify declared outputs exist inside scan dir, hashes/sizes match, raw snapshot hash equals `param_sha256`, effective snapshot hash equals `config_hash`, and hash metadata fields are present/consistent, including required non-null `config_schema_version`. Legacy manifests remain readable; unverifiable legacy remains unverifiable.

---

## 8. Version integrity and audit-only policy (per-family scope)

**Scope (normative):** Version/content integrity checks are scoped by:

`(module, config_family, param_version, config_canonicalization_version, config_hash_subject)`

**`config_family` definition (explicit):** `config_family` is an **explicit stable configuration-family identity** derived from **module/schema metadata** (not an unstable file path and not a global `param_version` namespace), resolved per §7.5. For current SCANLINE families, default `config_family == canonical module` unless the schema registry explicitly declares a subfamily. The value MUST be stable across config file renames/moves and MUST NOT be derived from `param_file` basename except through schema metadata lookup. If schema identity cannot be resolved, provenance emission fails (§7.5.4); audit comparison must report unresolved identity rather than guessing family.

`param_version` is a declared config label, not a content-derived identifier. SCANLINE MUST NOT auto-bump, rewrite, or silently “fix” versions.

### 8.1 Mismatch classes (differentiated)

| Observation | Detection | Classification | Action |
|---|---|---|---|
| Same family/version scope but different effective `config_hash` | Same `(module, config_family, param_version, config_canonicalization_version, config_hash_subject)`, different `config_hash` | **`version_content_mismatch`** | Audit finding/report only. No auto-bump, no rewrite, no invalidation of historical scans. |
| Same effective `config_hash` but different raw hash | Same effective hash, different `param_sha256` (e.g. formatting/artifact drift) | **`raw_artifact_mismatch`** (formatting/artifact drift) | Audit info/report only. Not a semantic config mismatch. |
| Different `param_version` but same effective `config_hash` | Same effective hash, different declared `param_version` in the scoped comparison | **`version_relabel` / same-content-new-version observation** | Audit info/warning only. Visible; does not imply the content changed. |

Additional notes:
- Differences across different `config_canonicalization_version` or different `config_hash_subject` are **out of scope** for this comparison class except as incompatible audit contexts (do not conflate versions).
- “Same effective config hash” means identical `config_hash` under the same canon version and subject.

### 8.2 Audit/reporting policy (explicit)

- The version-integrity check MUST report audit findings; it MUST NOT mutate records.
- Explicit prohibitions: **no automatic `param_version` bump. No automatic configuration rewrite. No automatic invalidation or rejection of historical scans solely because a mismatch is observed. No fabricated historical provenance.**
- Audit findings are visible and actionable but **do not mutate the source record** (no changes to config files, manifests, snapshots, events, or historical artifacts).
- Scan-time R4 continues enforcing header/param/event `param_version` equality and raw-byte binding as today. A stricter scan-time registry rejection is **not** enabled by this proposal.
- Any future enforcement policy (e.g. rejecting scans on mismatch) requires **separate approval** and a **separately versioned contract**.

---

## 9. Golden vectors and independent Python verification

Verification was performed **independently in this repository environment** on 2026-11-21 (read-only execution of temporary Python scripts under `/tmp`, e.g. `/tmp/scan018c_verify2.py`, `/tmp/scan018c_verify3.py`, `/tmp/scan018c_verify_neg2.py`, `/tmp/scan018c_verify_fixtures.py`). The checks implement `SCANLINE-config-canon-v1` behavior described in §4: strict UTF-8 decoding expectations for inputs tested, reject duplicate keys, parse numeric tokens as exact decimals via token strings (no binary `float`), recursive object key sorting by Unicode codepoint, array order preserved, no Unicode normalization, compact JSON string/structure emission consistent with the rules, and SHA-256 over canonical UTF-8 bytes with **no trailing newline**. All positive expected SHA-256 values listed below were **rerun and matched** in this session (not merely copied forward without verification).

### 9.1 Positive vectors (complete)

Every vector includes: Vector ID, input (JSON string or description sufficient to reproduce), expected canonical UTF-8 JSON, expected SHA-256, verification result.

| Vector ID | Input (reproducible) | Expected canonical UTF-8 JSON | Expected SHA-256 | Verification result |
|---|---|---|---|---|
| V1 — recursive object key ordering | JSON: `{"b":1, "a":2}` | `{"a":2,"b":1}` | `d3626ac30a87e6f7a6428233b3c68299976865fa5508e4267c5415c76af7a772` | PASS (rerun 2026-11-21) |
| V2 — nested object ordering | JSON: `{"z":{"b":1,"a":2},"y":0}` | `{"y":0,"z":{"a":2,"b":1}}` | `00b04662c2a3a6e1f9ea1af59ec0fc4929e2e9671ad5e06e573319a962af9a4b` | PASS (rerun 2026-11-21) |
| V3 — array order preserved | JSON: `{"a":[2,1]}` | `{"a":[2,1]}` | `439e3fbf35fa867d156db2626f94efbd435852a97bbe16660ee529d9bda0e502` | PASS (rerun 2026-11-21) |
| V4 — formatting-only equivalent config (example) | JSON: `{"universe":["GOLD","EURUSD"],"atr_window":14,"frozen_at":"2026-11-19T03:25:04Z","param_version":"1.0.0","module":"level_proximity"}` | `{"atr_window":14,"frozen_at":"2026-11-19T03:25:04Z","module":"level_proximity","param_version":"1.0.0","universe":["GOLD","EURUSD"]}` | `4f9f75cf2d9dfb55e0aa74c0c1eb4b7cf1b9227a4641d877c571d190ec48272b` | PASS (rerun 2026-11-21) |
| V5 — meaningful config change | JSON: `{"atr_window":14,"frozen_at":"2026-11-19T03:25:04Z","module":"level_proximity","note":"x","param_version":"1.0.0","universe":["GOLD","EURUSD"]}` | `{"atr_window":14,"frozen_at":"2026-11-19T03:25:04Z","module":"level_proximity","note":"x","param_version":"1.0.0","universe":["GOLD","EURUSD"]}` | `bcd955d0706c1f5cdfd6ee5f44fdffed29e467d1273694954d1c4de02edb1b77` | PASS (rerun 2026-11-21) |
| V6 — `1.0` canonical numeric equivalence (explicit forms tested) | **Explicitly tested equivalent forms:** `{"x":1}`, `{"x":1.0}`, `{"x":1e0}`. Canonical for the normalized numeric value is `{"x":1}`. | `{"x":1}` | `5041bf1f713df204784353e82f6a4a535931cb64f1f4b4a5aeaffcb720918b22` | PASS (rerun 2026-11-21; all three forms canonicalize equivalently to the same canonical JSON/bytes shown) |
| V7 — exponent expansion (`1e2`) | JSON: `{"x":1e2}` | `{"x":100}` | `6ae8ec2b1e8338f7511a7ea1366734f52ad540e10118fdb4a1221f10b9026f77` | PASS (rerun 2026-11-21) |
| V8 — trailing fractional zero removal | JSON: `{"x":0.0050}` | `{"x":0.005}` | `35229c9fd3ecdd0f753cffe2d26d76070cdfa81d2c72748890e65bb97ce53e98` | PASS (rerun 2026-11-21) |
| V9 — negative-zero variant `-0` | JSON: `{"x":-0}` | `{"x":0}` | `5bff452c5ed93f2e87a23984db5a15050c6477335fdec955b70063bb2d692bf1` | PASS (rerun 2026-11-21) |
| V10 — negative-zero variant `-0.0` | JSON: `{"x":-0.0}` | `{"x":0}` | `5bff452c5ed93f2e87a23984db5a15050c6477335fdec955b70063bb2d692bf1` | PASS (rerun 2026-11-21) |
| V11 — negative-zero variant `-0e0` | JSON: `{"x":-0e0}` | `{"x":0}` | `5bff452c5ed93f2e87a23984db5a15050c6477335fdec955b70063bb2d692bf1` | PASS (rerun 2026-11-21) |
| V12 — NFC string preserved | JSON: `{"name":"café"}` (NFC form in source) | `{"name":"café"}` | `645fa443126a8954fc6d871912b8fc67bc2ee8feae417efe55546251962ca74d` | PASS (rerun 2026-11-21) |
| V13 — boolean and null handling | JSON: `{"a":true,"b":false,"c":null}` | `{"a":true,"b":false,"c":null}` | `58ea9f23c715c4f8fee078efd41139485403f053775482d58b6f4f454b34ecf0` | PASS (rerun 2026-11-21) |
| V14 — array of objects | JSON: `{"a":[{"b":2,"a":1},3]}` | `{"a":[{"a":1,"b":2},3]}` | `1528798bdb2ff2ad39d5a8afac006825970fddc1d9264a7fda325368e42f553e` | PASS (rerun 2026-11-21) |
| V15 — canonicalization idempotence | Input object: `{"b":[{"d":1.0,"c":2}],"a":-0.0}` (JSON form) → canonicalize once to `{"a":0,"b":[{"c":2,"d":1}]}`; canonicalize the canonical output again yields identical bytes. | `{"a":0,"b":[{"c":2,"d":1}]}` | `b95941771326fb7728bc2ab75cde2a4970238f83fab5a7e436adcb6bb83bf584` | PASS (`canonicalize(canonicalize(x)) == canonicalize(x)`: True; rerun 2026-11-21) |
| V16 — NFC form | JSON: `{"name":"café"}` (NFC) | `{"name":"café"}` | `645fa443126a8954fc6d871912b8fc67bc2ee8feae417efe55546251962ca74d` | PASS (rerun 2026-11-21) |
| V17 — NFD form | JSON: `{"name":"cafe\u0301"}` (NFD / decomposed sequence in the JSON string content) | `{"name":"café"}` (canonical UTF-8 JSON string content as produced by canon-v1 string emission for that parsed value) | `4b7186ff40a64bfae3cb4bd75ac13b0de5ee693190f20812aaff208a77560ca7` | PASS (rerun 2026-11-21). **Visually equivalent NFC vs NFD strings remain byte-distinct** because `SCANLINE-config-canon-v1` performs **no Unicode normalization**. |
| V18 — NFC versus NFD remain distinct | Compare V16 and V17 | N/A | NFC: `645fa443126a8954fc6d871912b8fc67bc2ee8feae417efe55546251962ca74d`; NFD: `4b7186ff40a64bfae3cb4bd75ac13b0de5ee693190f20812aaff208a77560ca7` (different) | PASS (distinct hashes confirmed; rerun 2026-11-21) |

**V6 detail (explicit):** tested `{"x":1}`, `{"x":1.0}`, and `{"x":1e0}`; all canonicalize to `{"x":1}` with SHA-256 `5041bf1f713df204784353e82f6a4a535931cb64f1f4b4a5aeaffcb720918b22`.

**V9/V10/V11 detail (explicit):** tested `{"x":-0}`, `{"x":-0.0}`, `{"x":-0e0}`; all canonicalize to `{"x":0}` with SHA-256 `5bff452c5ed93f2e87a23984db5a15050c6477335fdec955b70063bb2d692bf1`.

### 9.2 Effective-configuration vectors

These vectors are effective-record rules produced by `load_config()` normalization, not generic JSON canonicalizer behavior alone.

| Vector ID | Input effective-record source (parsed/effective input) | Expected effective representation (canon-v1 serialized, effective config) | Expected SHA-256 | Notes |
|---|---|---|---|---|
| E1 | `{"module":"module_1","param_version":"1.0.0","frozen_at":"2026-01-01T00:00:00Z"}` | `{"frozen_at":"2026-01-01T00:00:00Z","module":"level_proximity","param_version":"1.0.0"}` | `602f8adb883740858bb6ff8c7a7e8a23683d53a330927e8bf867759ef7bd8f67` | Module alias normalized in effective config; raw snapshot retains original bytes. |
| T1 | Typed numeric cell (integer, type-sensitive field): `{"numeric_type":"integer","value":5}` | `{"numeric_type":"integer","value":5}` | `2ac1f847d99827f1b6e5873759065fa719c183d71ed1fab076ddec78fee62b50` | Runtime projection: `int(5)`, `isinstance(..., int)` true. Idempotent canonicalization. |
| T2 | Typed numeric cell (binary64, type-sensitive field): `{"numeric_type":"binary64","value":"5.0"}` | `{"numeric_type":"binary64","value":"5.0"}` | `2677df426ffd05d12b5ddd6567be5e168783c957a8549f5d0f3ddd720057f45f` | Runtime projection: `float(5.0)`, `isinstance(..., float)` true and `isinstance(..., int)` false. Idempotent canonicalization. |
| M1 | Session maintenance canonical object, local default: `{"mode":"local","start_hhmm":"17:00","end_hhmm":"18:00"}` | `{"end_hhmm":"18:00","mode":"local","start_hhmm":"17:00"}` | `b57d8c35971017b2f6091b463f1d1b245ca8375a563e65a47ec78a2249fc102b` | Canonical local maintenance object; aliases/defaults normalized before hashing. |
| M2 | Session maintenance canonical object, fixed UTC: `{"mode":"fixed_utc","start_hhmm":"17:00","end_hhmm":"18:00"}` | `{"end_hhmm":"18:00","mode":"fixed_utc","start_hhmm":"17:00"}` | `b635a6a0a2827917f28ca89d66afd1688787102dc6a7fa20118bb567f500b14f` | Fixed UTC mode preserved distinctly; never collapsed into local mode. |

**Typed vector assertions (verified 2026-11-21, independent /tmp script):** T1 != T2 canonical bytes and hashes; both idempotent under canon-v1 parse/canonicalize; runtime projection preserves `int` vs `float` type distinction while preserving numeric value 5. M1 != M2 confirms maintenance mode is hash-significant.

### 9.3 Negative vectors (rejected inputs)

All of the following are **rejected**. Results below are from independent reruns in this session (temporary scripts under `/tmp`) unless marked as implementation-required. Generic canonicalizer parse/validation behavior is distinguished from schema validation behavior in §6.

| Vector ID | Input / case | Expected rejection reason | Verification result |
|---|---|---|---|
| N10 | Untyped plain numeric in a schema-declared type-sensitive effective field (e.g. `grid_steps.GOLD` represented as plain `5` in effective config after normalization) | Reject: type-sensitive field requires typed numeric cell (`numeric_type` + typed `value`); no silent untyped numeric admission | Required by §4.5.2; implementation test required |
| N11 | Session config with accepted fixed-UTC maintenance alias but missing/ambiguous schema normalization rule | Reject/fail closed for v1.1.0 provenance: unsupported schema/config normalization; no fabricated effective snapshot/hash | Required by §5.5.5; implementation test required |
| N12 | Session config where resolved `symbols` scope cannot be deterministically established | Reject/fail closed for v1.1.0 provenance emission; legacy readable only if explicitly allowed, but no v1.1.0 complete manifest | Required by §5.5.5; implementation test required |
| N1 | Duplicate object key, e.g. `{"a":1,"a":2}` | Reject: duplicate object key | **PASS (rejected)** — example message observed: `duplicate key: 'a'` |
| N2 | NaN, e.g. `{"x":NaN}` (non-JSON literal in source text) | Reject: non-finite / not a valid JSON number literal per canon-v1 | **PASS (rejected)** in strict canon-v1/tokenized parsing context used for verification; note: Python’s default `json.loads` of that exact text **accepts** the token in some environments (producing a float) which is **forbidden** for canon-v1 hash parsing—canon-v1 must use token-preserving/exact rules and must reject NaN. |
| N3 | Infinity, e.g. `{"x":Infinity}` | Reject: non-finite / invalid | **PASS (rejected)** under canon-v1 rules; default permissive JSON float parsing is not used. |
| N4 | -Infinity, e.g. `{"x":-Infinity}` | Reject: non-finite / invalid | **PASS (rejected)** under canon-v1 rules; default permissive JSON float parsing is not used. |
| N5 | Leading plus sign, e.g. `{"x":+1}` | Reject: invalid JSON number lexeme (leading `+`) | **PASS (rejected)** — observed parse error from JSON tokenizer in verification run |
| N6 | Leading zero in an integer, e.g. `{"x":01}` | Reject: invalid JSON number lexeme (leading zero) | **PASS (rejected)** — observed parse error |
| N7 | Trailing comma, e.g. `{"a":1,}` | Reject: invalid JSON | **PASS (rejected)** — observed parse error |
| N8 | JSON comment, e.g. `{"a":1 /*c*/}` | Reject: invalid JSON | **PASS (rejected)** — observed parse error |
| N9 | Lone surrogate escape, e.g. `{"a":"\ud800"}` (JSON string containing lone surrogate) | Reject: invalid Unicode / lone surrogate | **PASS (rejected)** under strict Unicode handling |

Additional negative cases (must be rejected; specify behavior):

- **Invalid UTF-8 byte sequence** in the raw input: reject (strict UTF-8 decode required for canonicalization input path).
- **Unsupported top-level JSON types** where the config schema requires an object (e.g. top-level array, string, number, null): reject for the effective config / canon-v1 subject. (Generic serializer experiments may exist separately, but SCANLINE effective-config hashing requires a JSON object subject per §4.2.)
- **Numeric coefficient/exponent/canonical-length boundary violations** per §4.4: any token with mantissa coefficient digit count > **128**, or `|exponent| > 308` for an explicit exponent, must be rejected before canonical output. The derived canonical expanded-length bound for accepted input is `<= 437` characters excluding sign (§4.4.2); do not accept a token that would require expansion beyond that bound. A defensive `<= 512` output assertion may exist only as an unreachable guard and does not authorize accepting inputs that violate coefficient/exponent limits.
- **Unknown schema field in a strict schema-validated effective config:** reject unless that **specific schema version** explicitly permits the field (§6). This is a **schema validation** rejection, not merely a generic JSON parse choice.

**Distinction (normative):** Generic canonicalizer tests verify deterministic handling of valid JSON structures for the serialization rules and may be used to study structure; **the module schema validator** rejects unknown fields unless explicitly permitted by that schema version. The generic serializer does **not** grant permission to silently accept unknown fields in a validated effective configuration.

### 9.4 Repository fixture verification (actual files, read-only)

Computed read-only from actual repository files on 2026-11-21 using the independent verification script described above. Raw SHA-256 is over exact file bytes (`param_sha256` semantics). Canonical SHA-256 is over `SCANLINE-config-canon-v1` canonical UTF-8 bytes of the parsed JSON content (no trailing newline in canonical bytes).

| File | Raw size bytes | Canonical size bytes | Raw SHA-256 (`param_sha256` semantics) | Canonical SHA-256 (canon-v1) | Notes |
|---|---:|---:|---|---|---|
| `tests/fixtures/frozen_params.json` | 575 | 430 | `0ca0696e775e2575e57ca3a076d8e75cfc6aafc647694bebe03e7c4dcd13ae67` | `5ae44b2480bac9cbd227448be8b941716702de7dcbeb0ee0c5ae7a6a4bf4e671` | Semantically equivalent to noncanonical fixture; raw differs, canonical equal. |
| `tests/fixtures/frozen_params_noncanonical.json` | 575 | 430 | `2ebf893175bc5585a33d9630c6db296d459703c23e03af4f41fb0aa1645552e3` | `5ae44b2480bac9cbd227448be8b941716702de7dcbeb0ee0c5ae7a6a4bf4e671` | Formatting/key-order variant; canonical equal to `frozen_params.json`. |
| `tests/fixtures/byte_hash_variant.json` | 2649 | 1960 | `9719db2048a0ddfd0f633187921bc124dcc5f7a8132a8a8d1465634246fef205` | `1d50f8d5331acae61ec9bbaf16d1737a1988d260911df7abb1367f264f953770` | JSON fixture content canonicalized under canon-v1; raw and canonical differ as expected. |

**Additional current config files (read-only):**

| File | Raw size bytes | Canonical size bytes | Raw SHA-256 (`param_sha256`) | Canonical SHA-256 (canon-v1) | Historical raw-hash comparison (audit observation) |
|---|---:|---:|---|---|---|
| `config/scanner_params.level_proximity.json` | 757 | 665 | `1f921fa1e84a1a1f5c0d3ae9d67a454eb27715c9aa7fc606e4ad5956a4eb5f0a` | `a008ae098df2578dfc1700e6ba28087c57431854d5e3ca461378a30246328b54` | No pre-existing same-name historical manifest raw hash recorded in the cited audit set; treat as current working-tree artifact. |
| `config/scanner_params.level_proximity-1.1.0.json` | 872 | 688 | `dc0a2315521c393c9b14392de838fdbd10c13665a9d9cd0a5403735ed46d022c` | `ea15b7a2e6111d4de66290e0f01a0d002a629ce500224905e67eae4783d2eb96` | Historical manifest `param_sha256` observed in audit notes: `53a99a5f426c95c7bb6a4577ed6988c45d7ebabe27aced22ed560d54e604b1d6` (**differs** from current raw). Do **not** rewrite/backfill historical records. |
| `config/scanner_params.level_proximity-2.0.0.json` | 1819 | 1305 | `247dcc38ab022d46091d39419549e69c235bc428cceb20349f868bd3e6eae37e` | `68d5ca76b100d6914ebd3f43c08aa472e7dae0c8a2e971e747c27cd24a2aac35` | Historical manifest `param_sha256` observed in audit notes: `a11ff2b961d3b0212003187b28ace302826a3f69ad3223dbb3f2df03d4495445` (**differs** from current raw). Do **not** rewrite/backfill historical records. |
| `config/scanner_params.level_proximity-2.1.0.json` | 1811 | 1313 | `d18dfb5a7a8f12281a0a71a4628b449d255e33940af9e49d2c45802fb6f39e01` | `f5f9b43949fc853531832ad0042b3721e9ec939b0ba46ba834a849c0edbfbb12` | Historical manifest `param_sha256` observed in audit notes: `1181255cfb1b9529211ec3df2c9dd725748c7079775d20fc2d288673b4e6c6fb` (**differs** from current raw). Do **not** rewrite/backfill historical records. |

**Byte-length confirmation:** The first two frozen fixtures have different raw SHA-256 values but identical canonical SHA-256 values and identical canonical byte lengths (430), confirming formatting/key-order-only difference at raw level and semantic equivalence at canonical level.

**Fixture observations:** `frozen_params.json` and `frozen_params_noncanonical.json` differ in raw bytes but share the same canonical hash, confirming formatting/key-order invariance for that semantic content. Current `config/*.json` raw hashes differ from the cited historical recorded `param_sha256` values for the same-named versioned files; historical scans remain unverifiable against current bytes unless snapshots were preserved (they were not in those legacy records). These are **audit observations only**; no historical data is modified.

## 10. Manifest / scan integration details

### 10.1 SCAN-018B compatibility

- Preserve all SCAN-018A/B required meanings and fields.
- `manifest_version` for this additive contract: `1.1.0`.
- Existing `is_scan_complete` remains lightweight and read-only; v1.1.0-aware verification adds snapshot/hash consistency checks when fields are present.
- Raw snapshot and effective snapshot are regular scan outputs with `size_bytes` and `sha256` in `outputs`, so they participate in SCAN-018B output-integrity verification.

### 10.2 Historical provenance

- Do not modify historical manifests/events/snapshots/hashes.
- Missing historical snapshot/canonical hash is reported as `unverifiable_missing_snapshot`/`legacy_unverifiable`, not fabricated.
- Current config files may not be used to backfill historical byte identity.

---

## 11. Implementation sequence (after approval)

1. **Spec lock & golden fixtures** — codify canon-v1 vectors and fixture hashes as tests; confirm E1 effective-normalization vector.
2. **`load_config()` boundary** — single-read raw bytes, parse with duplicate-key/exact-decimal rules, schema validation, effective-config construction.
3. **Raw snapshot publication** — publish `param_snapshot.raw.json` from `raw_bytes`; include in outputs; verify `raw == param_sha256`.
4. **Effective snapshot + config_hash** — publish `param_snapshot.effective.json`; compute `config_hash`; add manifest metadata fields.
5. **Manifest 1.1.0 verification** — extend verifier for additive fields/output consistency; keep legacy behavior.
6. **Audit/reporting** — read-only provenance audit with scoped version-content mismatch reporting.

---

## 12. Risks and unresolved decisions

| Risk / decision | Impact | Recommendation |
|---|---|---|
| Numeric exactness bounds | ambiguous acceptance of huge exponents/precision | enforce coeff<=128, |explicit exponent|<=308; derived canonical expanded length <=437 excl sign; optional 512 guard only unreachable; no float fallback |
| Unknown-field strictness vs compatibility | may reject currently tolerated configs | strict by default; allow only per-schema-version explicit exceptions |
| Effective-config normalization scope | hash changes if normalization under-specified | centralize in `load_config()`; golden vectors per module/family |
| `grid_steps` type semantics | int vs float can change emitted event bytes | preserve type semantics in effective config/hash (Option A) via typed numeric cells §4.5.2; no silent collapse |
| Session config canonical shape | flat/containerized/alias forms may differ | define one canonical resolved shape per schema version (§5.5); aliases are input-only |
| Schema identity resolution | missing/ambiguous schema version makes provenance unverifiable | fail closed; require non-null `config_schema_version` and registry-resolved `config_family` (§7.5) |
| Manifest required-field promotion | breaking contract | additive in 1.1.0; do not silently reinterpret v1.0.0 |

---

## 13. Restrictions honored and verification record

This proposal does **not** modify production code, tests, configuration files, historical manifests, historical events, snapshots, or hashes. No commit/push performed. Implementation requires explicit approval.

### 13.1 Git/scope record (this pass)

- **Initial `git status --short --branch`:** captured before modification: `## main...origin/main` with pre-existing untracked files including `docs/SCAN-018C-CONFIG-PROVENANCE-PROPOSAL.md`, `docs/SCAN-018C-CONFIG-PROVENANCE-RECON.md`, and other unrelated untracked docs listed in initial status. The proposal file was **already untracked at task start**; this pass edited that existing untracked proposal in place.
- **Final `git status --short --branch`:** unchanged set of untracked files; no tracked files modified; no unrelated pre-existing changes altered.
- **`git diff --check`:** no output / exit 0.
- **Read-only verification scripts:** temporary scripts created outside repo under `/tmp/scan018c_limits.py` and `/tmp/scan018c_limits_report.json`; inspected before execution; no repository tests added.

### 13.2 Remaining unresolved implementation prerequisites

1. **Formal schema declarations per numeric field:** codebase currently has ad hoc validation; `load_config()` needs explicit per-field schema type (integer/Decimal/binary float/typed-numeric/string/etc.) before authoritative effective hashing.
2. **`grid_steps.<SYMBOL>` type-preserving implementation:** contract is frozen to Option A (§4.5.2). Implementation must preserve integer-vs-float observable semantics in effective config and runtime emission using typed numeric cells; runtime projection must return native `int`/`float`; no normalization to same hash/bytes for `5` vs `5.0` under current behavior.
3. **Float-backed effective representation policy adoption:** proposal recommends binary64 conversion + shortest round-trip decimal in effective snapshot for float-backed fields; implementation must codify and test this contract where float semantics are intended.
4. **Session canonical effective shape implementation:** §5.5 freezes target shape, accepted maintenance fields, canonical maintenance object, and fail-closed rules. Implementation must inventory all session config forms/fixed-UTC usage, define schema-versioned canonicalization, and prove no silent behavior change for currently accepted configs. Unsupported/ambiguous effective representations must fail closed with no v1.1.0 provenance-complete manifest.
5. **Schema registry implementation:** implement authoritative module->config_family->config_schema_version registry and fail-closed resolution per §7.5; include session_anomalies family mapping before emitting v1.1.0 session provenance.
6. **Canon-v1 parser implementation:** production parser must be token-preserving/exact-decimal, reject duplicate keys/invalid UTF-8/lone surrogates/non-finite tokens, and enforce numeric/size/depth accepted-input limits before canonical output. Derived canonical-length bound is 437; optional 512 guard is unreachable-only.
