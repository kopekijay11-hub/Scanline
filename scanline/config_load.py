"""Authoritative configuration loading for SCANLINE (SCAN-018C-I2)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from scanline.config_canon import (
    CANON_VERSION,
    CONFIG_HASH_ALGORITHM,
    CONFIG_HASH_SUBJECT,
    CanonicalizationError,
    canonicalize,
    canonicalize_object,
)
from scanline.config_registry import (
    AmbiguousConfigFamilyError,
    ConfigSchemaError,
    InvalidFieldTypeError,
    MissingSchemaVersionError,
    SchemaEntry,
    UnknownFieldError,
    UnknownModuleError,
    UnknownParamVersionError,
    UnsupportedLegacyFormError,
    ensure_allowed_fields,
    reject_bool_numeric,
    require_type,
    resolve_schema,
)
from scanline.schema import normalize_module_id


class ConfigLoadError(ConfigSchemaError):
    """Failed to load/validate configuration."""


@dataclass(frozen=True)
class LoadedConfig:
    raw_bytes: bytes
    parsed_config: Dict[str, Any]
    effective_config: Dict[str, Any]
    runtime_config: Dict[str, Any]
    param_sha256: str
    config_hash: str
    config_hash_algorithm: str
    config_canonicalization_version: str
    config_hash_subject: str
    raw_snapshot_bytes: bytes
    effective_snapshot_bytes: bytes
    param_file: str
    module: str
    config_family: str
    param_version: str
    frozen_at: str
    config_schema_version: str


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _is_typed_numeric_cell(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and set(value.keys()) == {"numeric_type", "value"}
        and value.get("numeric_type") in {"integer", "binary64"}
    )


def _typed_cell_runtime(value: Mapping[str, Any], field: str) -> Any:
    ntype = value.get("numeric_type")
    v = value.get("value")
    if ntype == "integer":
        if isinstance(v, bool) or not isinstance(v, int):
            raise InvalidFieldTypeError(f"{field} integer typed cell value must be int")
        return int(v)
    if ntype == "binary64":
        if not isinstance(v, str):
            raise InvalidFieldTypeError(f"{field} binary64 typed cell value must be string")
        try:
            f = float(v)
        except Exception as e:
            raise InvalidFieldTypeError(f"{field} binary64 typed cell value invalid: {e}") from e
        if not (f == f and abs(f) != float("inf")):
            raise InvalidFieldTypeError(f"{field} binary64 typed cell must be finite")
        # preserve runtime type distinction: float, not int
        return float(f)
    raise InvalidFieldTypeError(f"{field} has invalid numeric_type")


def project_runtime(obj: Any, *, field_path: str = "$") -> Any:
    if _is_typed_numeric_cell(obj):
        return _typed_cell_runtime(obj, field_path)
    if isinstance(obj, dict):
        return {k: project_runtime(v, field_path=f"{field_path}.{k}") for k, v in obj.items()}
    if isinstance(obj, list):
        return [project_runtime(v, field_path=f"{field_path}[{i}]") for i, v in enumerate(obj)]
    return obj


def _normalize_binary64_value(value: Any, field: str) -> Dict[str, Any]:
    reject_bool_numeric(value, field)
    # accept int/float from parsed JSON; convert to finite IEEE-754 binary64
    f = float(value)
    if not (f == f and abs(f) != float("inf")):
        raise InvalidFieldTypeError(f"{field} must be finite")
    if value != 0 and f == 0.0:
        raise InvalidFieldTypeError(f"{field} underflows to zero")
    # shortest round-trip decimal representation
    return {"numeric_type": "binary64", "value": repr(f)}


def _normalize_grid_step(value: Any, field: str) -> Dict[str, Any]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InvalidFieldTypeError(f"{field} must be numeric")
    if isinstance(value, int):
        if value <= 0:
            raise InvalidFieldTypeError(f"{field} must be > 0")
        return {"numeric_type": "integer", "value": int(value)}
    f = float(value)
    if not (f == f and abs(f) != float("inf")):
        raise InvalidFieldTypeError(f"{field} must be finite")
    if f <= 0:
        raise InvalidFieldTypeError(f"{field} must be > 0")
    if f.is_integer():
        # float token but integer-valued: preserve binary64 type semantics?
        # Source inspection: levels.py inspects original type; 5.0 should behave as float.
        # So binary64 cell.
        pass
    if value != 0 and f == 0.0:
        raise InvalidFieldTypeError(f"{field} underflows to zero")
    return {"numeric_type": "binary64", "value": repr(f)}


def _normalize_level_proximity(parsed: Mapping[str, Any], schema: SchemaEntry) -> Dict[str, Any]:
    if not isinstance(parsed, Mapping):
        raise ConfigLoadError("level_proximity config must be object")
    allowed_raw = set(getattr(schema, "allowed_raw_fields", schema.allowed_fields)) | {"module"}
    unknown = sorted([k for k in parsed.keys() if k not in allowed_raw])
    if unknown:
        raise UnknownFieldError(f"unknown level_proximity field(s): {unknown}")

    module = normalize_module_id(parsed.get("module"))
    if module != "level_proximity":
        raise UnknownModuleError(f"unexpected module for level_proximity schema: {parsed.get('module')!r}")

    param_version = parsed.get("param_version")
    frozen_at = parsed.get("frozen_at")
    if not isinstance(param_version, str) or not param_version.strip():
        raise InvalidFieldTypeError("param_version must be non-empty string")
    if not isinstance(frozen_at, str) or not frozen_at.strip():
        raise InvalidFieldTypeError("frozen_at must be non-empty string")

    universe = parsed.get("universe")
    if not isinstance(universe, list) or not universe or not all(isinstance(s, str) and s for s in universe):
        raise InvalidFieldTypeError("universe must be non-empty list[str]")
    emission_timeframes = parsed.get("emission_timeframes")
    if not isinstance(emission_timeframes, list) or not emission_timeframes or not all(isinstance(s, str) and s for s in emission_timeframes):
        raise InvalidFieldTypeError("emission_timeframes must be non-empty list[str]")
    definition_timeframe = parsed.get("definition_timeframe")
    if not isinstance(definition_timeframe, str) or not definition_timeframe:
        raise InvalidFieldTypeError("definition_timeframe must be non-empty string")
    level_types = parsed.get("level_types")
    if not isinstance(level_types, list) or not level_types or not all(isinstance(s, str) and s for s in level_types):
        raise InvalidFieldTypeError("level_types must be non-empty list[str]")

    atr_window = parsed.get("atr_window")
    if isinstance(atr_window, bool) or not isinstance(atr_window, int) or atr_window <= 0:
        raise InvalidFieldTypeError("atr_window must be positive integer")

    atr_basis = parsed.get("atr_basis")
    crossing_semantics = parsed.get("crossing_semantics")
    band_edge = parsed.get("band_edge")
    gap_through = parsed.get("gap_through")
    state_key = parsed.get("state_key")
    gap_semantics = parsed.get("gap_semantics")
    for name, val in [
        ("atr_basis", atr_basis),
        ("crossing_semantics", crossing_semantics),
        ("band_edge", band_edge),
        ("gap_through", gap_through),
        ("state_key", state_key),
        ("gap_semantics", gap_semantics),
    ]:
        if not isinstance(val, str) or not val:
            raise InvalidFieldTypeError(f"{name} must be non-empty string")

    atr_excludes = parsed.get("atr_excludes_emission_bar")
    if atr_excludes is not True:
        raise InvalidFieldTypeError("atr_excludes_emission_bar must be true")

    bands_raw = parsed.get("proximity_bands_atr")
    if isinstance(bands_raw, dict):
        if set(bands_raw.keys()) != {"structural", "grid"}:
            raise InvalidFieldTypeError("proximity_bands_atr object must have structural and grid")
        structural = _normalize_binary64_value(bands_raw["structural"], "proximity_bands_atr.structural")
        grid = _normalize_binary64_value(bands_raw["grid"], "proximity_bands_atr.grid")
    elif isinstance(bands_raw, list):
        if len(bands_raw) != 1:
            raise UnsupportedLegacyFormError("legacy proximity_bands_atr list must have length 1")
        structural = _normalize_binary64_value(bands_raw[0], "proximity_bands_atr[0]")
        grid = _normalize_binary64_value(bands_raw[0], "proximity_bands_atr[0]")
    else:
        raise InvalidFieldTypeError("proximity_bands_atr must be object or legacy single-item list")

    grid_steps_raw = parsed.get("grid_steps", {})
    if grid_steps_raw is None:
        grid_steps_raw = {}
    if not isinstance(grid_steps_raw, dict):
        raise InvalidFieldTypeError("grid_steps must be object")
    grid_steps: Dict[str, Any] = {}
    for sym, step in grid_steps_raw.items():
        if not isinstance(sym, str) or not sym:
            raise InvalidFieldTypeError("grid_steps keys must be non-empty strings")
        grid_steps[sym] = _normalize_grid_step(step, f"grid_steps.{sym}")

    effective = {
        "module": "level_proximity",
        "param_version": param_version,
        "frozen_at": frozen_at,
        "config_schema_version": schema.config_schema_version,
        "config_family": schema.config_family,
        "universe": list(universe),
        "emission_timeframes": list(emission_timeframes),
        "definition_timeframe": definition_timeframe,
        "level_types": list(level_types),
        "atr_window": atr_window,
        "atr_basis": atr_basis,
        "proximity_bands_atr": {
            "structural": structural,
            "grid": grid,
        },
        "grid_steps": grid_steps,
        "crossing_semantics": crossing_semantics,
        "band_edge": band_edge,
        "gap_through": gap_through,
        "state_key": state_key,
        "gap_semantics": gap_semantics,
        "atr_excludes_emission_bar": True,
    }
    ensure_allowed_fields(effective, schema.allowed_fields, context="level_proximity effective")
    return effective


def _runtime_level_proximity(effective: Mapping[str, Any]) -> Dict[str, Any]:
    rt = project_runtime(dict(effective))
    # runtime should not require typed cells; bands become floats
    rt.pop("config_schema_version", None)
    rt.pop("config_family", None)
    # keep module/param_version/frozen_at and all behavior fields
    return rt

from scanline.sessions import _validate_hhmm, _parse_hhmm, _require_int


def _normalize_session_maintenance(raw: Mapping[str, Any], *, symbol: str) -> Dict[str, Any]:
    # raw is canonical-resolved source fields (no alias keys except maybe none)
    fixed_start_keys = [k for k in ("maintenance_utc_start", "maintenance_start_utc") if k in raw]
    fixed_end_keys = [k for k in ("maintenance_utc_end", "maintenance_end_utc") if k in raw]
    local_start_keys = [k for k in ("maintenance_local_start", "maintenance_start_local", "rollover_local_start", "maintenance_start") if k in raw]
    local_end_keys = [k for k in ("maintenance_local_end", "maintenance_end_local", "rollover_local_end", "maintenance_end") if k in raw]

    def _one(keys, label):
        vals = [raw[k] for k in keys]
        if not vals:
            return None
        # conflicting values among aliases not allowed
        first = vals[0]
        for v in vals[1:]:
            if v != first:
                raise ConfigLoadError(f"conflicting {label} aliases for symbol {symbol}")
        return first

    fixed_start = _one(fixed_start_keys, "maintenance start")
    fixed_end = _one(fixed_end_keys, "maintenance end")
    local_start = _one(local_start_keys, "maintenance start")
    local_end = _one(local_end_keys, "maintenance end")

    has_fixed = bool(fixed_start_keys or fixed_end_keys)
    has_local = bool(local_start_keys or local_end_keys)

    if has_fixed and has_local:
        # if values are identical and unambiguous? safer fail closed: ambiguous mode.
        raise ConfigLoadError(
            f"ambiguous maintenance mode for symbol {symbol}: fixed-UTC and local aliases both present"
        )

    if has_fixed:
        start = fixed_start if fixed_start is not None else "17:00"
        end = fixed_end if fixed_end is not None else "18:00"
        _validate_hhmm(start, f"symbols.{symbol}.maintenance.start_hhmm")
        _validate_hhmm(end, f"symbols.{symbol}.maintenance.end_hhmm")
        mode = "fixed_utc"
    else:
        start = local_start if local_start is not None else "17:00"
        end = local_end if local_end is not None else "18:00"
        _validate_hhmm(start, f"symbols.{symbol}.maintenance.start_hhmm")
        _validate_hhmm(end, f"symbols.{symbol}.maintenance.end_hhmm")
        mode = "local"

    sh, sm = _parse_hhmm(start)
    eh, em = _parse_hhmm(end)
    if sh == eh and sm == em:
        raise ConfigLoadError(f"maintenance start and end must differ for symbol {symbol}")

    def _canon_hhmm(s):
        h, m = _parse_hhmm(s)
        return f"{h:02d}:{m:02d}"

    return {
        "mode": mode,
        "start_hhmm": _canon_hhmm(start),
        "end_hhmm": _canon_hhmm(end),
    }


def _session_collect_symbol_records(parsed: Mapping[str, Any]) -> Dict[str, Dict[str, Any]]:
    # Accept approved container forms and flat. Resolve explicit symbol scope.
    containers = ["clusters", "cluster_schedule", "clusters_schedule", "session_clusters", "cluster_expected_bars"]
    records: Dict[str, Dict[str, Any]] = {}
    found_container = False

    def merge(sym, rec):
        if not isinstance(rec, dict):
            raise ConfigLoadError(f"symbol record for {sym} must be object")
        dst = records.setdefault(sym, {})
        for k, v in rec.items():
            if k == "symbol":
                if v != sym:
                    raise ConfigLoadError(f"symbol mismatch in record: {sym!r} vs {v!r}")
                continue
            if k in dst and dst[k] != v:
                raise ConfigLoadError(f"conflicting field {k!r} for symbol {sym}")
            dst[k] = v

    for key in containers:
        if key not in parsed:
            continue
        found_container = True
        val = parsed[key]
        if isinstance(val, dict):
            for sym, rec in val.items():
                if not isinstance(sym, str) or not sym:
                    raise ConfigLoadError("symbol keys must be non-empty strings")
                if isinstance(rec, dict):
                    merge(sym, dict(rec))
                elif isinstance(rec, (int, float)) and not isinstance(rec, bool):
                    merge(sym, {"expected_bars": rec})
                else:
                    raise ConfigLoadError(f"unsupported cluster record for {sym}")
        elif isinstance(val, list):
            for item in val:
                if not isinstance(item, dict) or "symbol" not in item:
                    raise ConfigLoadError("list cluster records must be objects with symbol")
                sym = item["symbol"]
                if not isinstance(sym, str) or not sym:
                    raise ConfigLoadError("cluster symbol must be non-empty string")
                merge(sym, dict(item))
        else:
            raise ConfigLoadError(f"{key} must be object or list")

    if not found_container:
        # flat config: infer symbol scope. If universe present, require exactly one symbol or fail closed.
        flat_keys = {
            "expected_bars","weekday_expected_bars","expected_weekday_bars","expected",
            "expected_sun_bars","sunday_expected_bars","expected_sunday_bars","sunday_bars",
            "zone","timezone","tz","time_zone",
            "maintenance_local_start","maintenance_start_local","rollover_local_start","maintenance_start",
            "maintenance_local_end","maintenance_end_local","rollover_local_end","maintenance_end",
            "maintenance_utc_start","maintenance_start_utc","maintenance_utc_end","maintenance_end_utc",
            "stub_tolerance","stub_tol","sun_tolerance","sun_tol","sunday_tolerance",
        }
        has_flat = any(k in parsed for k in flat_keys)
        if has_flat:
            universe = parsed.get("universe")
            symbol = parsed.get("symbol")
            if isinstance(symbol, str) and symbol.strip():
                merge(symbol.strip(), {k: v for k, v in parsed.items() if k in flat_keys})
            elif isinstance(universe, list) and len(universe) == 1 and isinstance(universe[0], str) and universe[0].strip():
                merge(universe[0].strip(), {k: v for k, v in parsed.items() if k in flat_keys})
            else:
                raise ConfigLoadError(
                    "session flat config requires explicit symbol scope (symbol or single-element universe)"
                )
    if not records:
        raise ConfigLoadError("session config has no resolvable symbol records")
    return records

def _normalize_session_anomalies(parsed: Mapping[str, Any], schema: SchemaEntry) -> Dict[str, Any]:
    if not isinstance(parsed, Mapping):
        raise ConfigLoadError("session_anomalies config must be object")

    allowed_raw = set(getattr(schema, "allowed_raw_fields", schema.allowed_fields))
    unknown = sorted([k for k in parsed.keys() if k not in allowed_raw])
    if unknown:
        raise UnknownFieldError(f"unknown session_anomalies field(s): {unknown}")

    module = normalize_module_id(parsed.get("module"))
    if module != "session_anomalies":
        raise UnknownModuleError(f"unexpected module for session_anomalies schema: {parsed.get('module')!r}")
    param_version = parsed.get("param_version")
    frozen_at = parsed.get("frozen_at")
    if not isinstance(param_version, str) or not param_version.strip():
        raise InvalidFieldTypeError("param_version must be non-empty string")
    if not isinstance(frozen_at, str) or not frozen_at.strip():
        raise InvalidFieldTypeError("frozen_at must be non-empty string")

    universe = parsed.get("universe")
    emission_timeframes = parsed.get("emission_timeframes")
    if universe is not None:
        if not isinstance(universe, list) or not universe or not all(isinstance(s, str) and s for s in universe):
            raise InvalidFieldTypeError("universe must be non-empty list[str]")
    if emission_timeframes is not None:
        if not isinstance(emission_timeframes, list) or not emission_timeframes or not all(isinstance(s, str) and s for s in emission_timeframes):
            raise InvalidFieldTypeError("emission_timeframes must be non-empty list[str]")

    symbol_records = _session_collect_symbol_records(parsed)
    symbols_out: Dict[str, Any] = {}

    alias_map = {
        "expected_bars": "expected_bars",
        "weekday_expected_bars": "expected_bars",
        "expected_weekday_bars": "expected_bars",
        "expected": "expected_bars",
        "expected_sun_bars": "expected_sun_bars",
        "sunday_expected_bars": "expected_sun_bars",
        "expected_sunday_bars": "expected_sun_bars",
        "sunday_bars": "expected_sun_bars",
        "zone": "zone",
        "timezone": "zone",
        "tz": "zone",
        "time_zone": "zone",
        "stub_tolerance": "stub_tolerance",
        "stub_tol": "stub_tolerance",
        "sun_tolerance": "sun_tolerance",
        "sun_tol": "sun_tolerance",
        "sunday_tolerance": "sun_tolerance",
    }
    maint_keys = {
        "maintenance_local_start","maintenance_start_local","rollover_local_start","maintenance_start",
        "maintenance_local_end","maintenance_end_local","rollover_local_end","maintenance_end",
        "maintenance_utc_start","maintenance_start_utc","maintenance_utc_end","maintenance_end_utc",
    }

    for sym, rec in symbol_records.items():
        # normalize aliases
        norm: Dict[str, Any] = {}
        maint_raw: Dict[str, Any] = {}
        for k, v in rec.items():
            if k in maint_keys:
                if k in maint_raw and maint_raw[k] != v:
                    raise ConfigLoadError(f"conflicting maintenance field {k} for {sym}")
                maint_raw[k] = v
                continue
            if k in alias_map:
                canon = alias_map[k]
                if canon in norm and norm[canon] != v:
                    raise ConfigLoadError(f"conflicting alias values for {canon} symbol {sym}")
                norm[canon] = v
                continue
            raise UnknownFieldError(f"unknown session symbol field: {k}")

        if "expected_bars" not in norm:
            raise ConfigLoadError(f"expected_bars is required for symbol {sym}")
        expected_bars = _require_int(norm["expected_bars"], f"symbols.{sym}.expected_bars", 0)
        expected_sun = _require_int(norm.get("expected_sun_bars", 0), f"symbols.{sym}.expected_sun_bars", 0)
        zone = norm.get("zone", "UTC")
        if not isinstance(zone, str) or not zone.strip():
            raise ConfigLoadError(f"symbols.{sym}.zone must be non-empty string")
        try:
            from zoneinfo import ZoneInfo
            ZoneInfo(zone)
        except Exception as e:
            raise ConfigLoadError(f"invalid timezone for symbol {sym}: {zone}") from e
        stub_tolerance = _require_int(norm.get("stub_tolerance", 1), f"symbols.{sym}.stub_tolerance", 0)
        sun_tolerance = _require_int(norm.get("sun_tolerance", 0), f"symbols.{sym}.sun_tolerance", 0)
        maintenance = _normalize_session_maintenance(maint_raw, symbol=sym)

        symbols_out[sym] = {
            "expected_bars": expected_bars,
            "expected_sun_bars": expected_sun,
            "zone": zone,
            "maintenance": maintenance,
            "stub_tolerance": stub_tolerance,
            "sun_tolerance": sun_tolerance,
        }

    effective = {
        "module": "session_anomalies",
        "param_version": param_version,
        "frozen_at": frozen_at,
        "config_schema_version": schema.config_schema_version,
        "config_family": schema.config_family,
        "symbols": symbols_out,
    }
    if universe is not None:
        effective["universe"] = list(universe)
    if emission_timeframes is not None:
        effective["emission_timeframes"] = list(emission_timeframes)
    ensure_allowed_fields(effective, schema.allowed_fields, context="session_anomalies effective")
    return effective


def _runtime_session_anomalies(effective: Mapping[str, Any]) -> Dict[str, Any]:
    eff = project_runtime(dict(effective))
    clusters = {}
    symbols = eff.get("symbols", {})
    for sym, cfg in symbols.items():
        m = cfg.get("maintenance", {})
        rec = {
            "symbol": sym,
            "expected_bars": cfg["expected_bars"],
            "expected_sun_bars": cfg["expected_sun_bars"],
            "zone": cfg["zone"],
            "stub_tolerance": cfg["stub_tolerance"],
            "sun_tolerance": cfg["sun_tolerance"],
            "maintenance_local_start": m["start_hhmm"],
            "maintenance_local_end": m["end_hhmm"],
        }
        if m.get("mode") == "fixed_utc":
            rec["maintenance_utc_start"] = m["start_hhmm"]
            rec["maintenance_utc_end"] = m["end_hhmm"]
        clusters[sym] = rec

    rt: Dict[str, Any] = {
        "module": "session_anomalies",
        "param_version": eff["param_version"],
        "frozen_at": eff["frozen_at"],
        "clusters": clusters,
    }
    if "universe" in eff:
        rt["universe"] = list(eff["universe"])
    if "emission_timeframes" in eff:
        rt["emission_timeframes"] = list(eff["emission_timeframes"])
    # flat compatibility for single-symbol configs
    if len(symbols) == 1:
        only = next(iter(symbols.values()))
        m = only["maintenance"]
        rt["expected_bars"] = only["expected_bars"]
        rt["expected_sun_bars"] = only["expected_sun_bars"]
        rt["zone"] = only["zone"]
        rt["stub_tolerance"] = only["stub_tolerance"]
        rt["sun_tolerance"] = only["sun_tolerance"]
        rt["maintenance_local_start"] = m["start_hhmm"]
        rt["maintenance_local_end"] = m["end_hhmm"]
        if m.get("mode") == "fixed_utc":
            rt["maintenance_utc_start"] = m["start_hhmm"]
            rt["maintenance_utc_end"] = m["end_hhmm"]
    return rt

from scanline.config_registry import register_schema, SchemaEntry, iter_schema_entries


def _register_default_schemas() -> None:
    # Idempotent registration
    existing = {(e.config_family, e.param_version, e.config_schema_version) for e in iter_schema_entries()}
    # Legacy helper kept for compatibility; real registration is _ensure_default_registry.
    return None


def _ensure_default_registry() -> None:
    from scanline.config_registry import _REGISTRY

    needed_lp = ["1.0.0", "1.1.0", "2.0.0", "2.1.0"]
    for pv in needed_lp:
        key = ("level_proximity", pv)
        if key not in _REGISTRY:
            register_schema(SchemaEntry(
                module="level_proximity",
                config_family="level_proximity",
                config_schema_version="1",
                param_version=pv,
                allowed_fields=(
                    "module","param_version","frozen_at","config_schema_version","config_family",
                    "universe","emission_timeframes","definition_timeframe","level_types",
                    "atr_window","atr_basis","proximity_bands_atr","grid_steps",
                    "crossing_semantics","band_edge","gap_through","state_key","gap_semantics","atr_excludes_emission_bar",
                ),
                allowed_raw_fields=(
                    "module","param_version","frozen_at",
                    "universe","emission_timeframes","definition_timeframe","level_types",
                    "atr_window","atr_basis","proximity_bands_atr","grid_steps",
                    "crossing_semantics","band_edge","gap_through","state_key","gap_semantics","atr_excludes_emission_bar",
                ),
                normalize_effective=(lambda pv=pv: (lambda p, s: _normalize_level_proximity(p, s)))(),
                runtime_projection=lambda e: _runtime_level_proximity(e),
                description=f"Level proximity schema v1 for param_version {pv}",
            ))

    skey = ("session_anomalies", "1.0.0")
    if skey not in _REGISTRY:
        register_schema(SchemaEntry(
            module="session_anomalies",
            config_family="session_anomalies",
            config_schema_version="1",
            param_version="1.0.0",
            allowed_fields=(
                "module","param_version","frozen_at","config_schema_version","config_family","symbols","universe","emission_timeframes",
            ),
            allowed_raw_fields=(
                "module","param_version","frozen_at","universe","emission_timeframes","symbol",
                "clusters","cluster_schedule","clusters_schedule","session_clusters","cluster_expected_bars",
                "expected_bars","weekday_expected_bars","expected_weekday_bars","expected",
                "expected_sun_bars","sunday_expected_bars","expected_sunday_bars","sunday_bars",
                "zone","timezone","tz","time_zone",
                "maintenance_local_start","maintenance_start_local","rollover_local_start","maintenance_start",
                "maintenance_local_end","maintenance_end_local","rollover_local_end","maintenance_end",
                "maintenance_utc_start","maintenance_start_utc","maintenance_utc_end","maintenance_end_utc",
                "stub_tolerance","stub_tol","sun_tolerance","sun_tol","sunday_tolerance",
            ),
            normalize_effective=lambda p, s: _normalize_session_anomalies(p, s),
            runtime_projection=lambda e: _runtime_session_anomalies(e),
            description="Session anomalies schema v1 for param_version 1.0.0",
        ))


def load_config(param_path: str | Path, *, schema_version: Optional[str] = None) -> LoadedConfig:
    _ensure_default_registry()
    path = Path(param_path)
    raw_bytes = path.read_bytes()  # single read
    param_sha256 = _sha256_hex(raw_bytes)

    try:
        parsed_any = json.loads(raw_bytes)
    except Exception as e:
        # keep legacy-style parse errors visible but deterministic
        raise ConfigLoadError(f"invalid JSON in {path.name}: {e}") from e
    if not isinstance(parsed_any, dict):
        raise ConfigLoadError("top-level config must be a JSON object")

    # Parse also through canon parser for duplicate-key/UTF-8/number rules?
    # raw_bytes already loaded; use strict parser to catch duplicate keys and invalid numerics.
    try:
        # Use canonical parser to validate structure; but it returns Decimals for fractional numbers.
        from scanline.config_canon import parse_json_bytes
        _strict = parse_json_bytes(raw_bytes)
        # Do not use _strict as parsed_config directly because it changes numeric types; keep json.loads object for compatibility,
        # but duplicate-key/invalid token checks above are enforced by parse_json_bytes.
    except CanonicalizationError as e:
        raise ConfigLoadError(f"config canonical parse failed: {e}") from e

    parsed_config = parsed_any

    schema = resolve_schema(parsed_config, schema_version=schema_version)

    effective_config = schema.normalize_effective(parsed_config, schema)
    # ensure config_schema_version/family are present and correct
    if effective_config.get("config_schema_version") != schema.config_schema_version:
        effective_config = dict(effective_config)
        effective_config["config_schema_version"] = schema.config_schema_version
    if effective_config.get("config_family") != schema.config_family:
        effective_config = dict(effective_config)
        effective_config["config_family"] = schema.config_family
    if effective_config.get("module") != schema.module:
        effective_config = dict(effective_config)
        effective_config["module"] = schema.module

    try:
        effective_snapshot_bytes = canonicalize_object(effective_config)
    except CanonicalizationError as e:
        raise ConfigLoadError(f"effective config canonicalization failed: {e}") from e
    config_hash = _sha256_hex(effective_snapshot_bytes)

    runtime_config = schema.runtime_projection(effective_config)
    runtime_config = project_runtime(runtime_config)

    param_version = effective_config.get("param_version")
    frozen_at = effective_config.get("frozen_at")
    if not isinstance(param_version, str) or not isinstance(frozen_at, str):
        raise ConfigLoadError("effective config missing param_version/frozen_at")

    raw_snapshot_bytes = bytes(raw_bytes)

    return LoadedConfig(
        raw_bytes=raw_bytes,
        parsed_config=parsed_config,
        effective_config=effective_config,
        runtime_config=runtime_config,
        param_sha256=param_sha256,
        config_hash=config_hash,
        config_hash_algorithm=CONFIG_HASH_ALGORITHM,
        config_canonicalization_version=CANON_VERSION,
        config_hash_subject=CONFIG_HASH_SUBJECT,
        raw_snapshot_bytes=raw_snapshot_bytes,
        effective_snapshot_bytes=effective_snapshot_bytes,
        param_file=path.name,
        module=schema.module,
        config_family=schema.config_family,
        param_version=param_version,
        frozen_at=frozen_at,
        config_schema_version=schema.config_schema_version,
    )
