"""Schema registry for SCANLINE configuration families (SCAN-018C-I2)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Mapping, Optional, Tuple

from scanline.schema import normalize_module_id


class ConfigSchemaError(ValueError):
    """Schema resolution/validation error for configuration loading."""


class UnknownModuleError(ConfigSchemaError):
    pass


class UnknownParamVersionError(ConfigSchemaError):
    pass


class MissingSchemaVersionError(ConfigSchemaError):
    pass


class AmbiguousConfigFamilyError(ConfigSchemaError):
    pass


class UnknownFieldError(ConfigSchemaError):
    pass


class InvalidFieldTypeError(ConfigSchemaError):
    pass


class UnsupportedLegacyFormError(ConfigSchemaError):
    pass


@dataclass(frozen=True)
class SchemaEntry:
    module: str
    config_family: str
    config_schema_version: str
    param_version: str
    allowed_fields: Tuple[str, ...]
    allowed_raw_fields: Tuple[str, ...]
    normalize_effective: Callable[[Dict[str, Any]], Dict[str, Any]]
    runtime_projection: Callable[[Dict[str, Any]], Dict[str, Any]]
    description: str = ""


# Registry key: (config_family, param_version)
_REGISTRY: Dict[Tuple[str, str], SchemaEntry] = {}


def register_schema(entry: SchemaEntry) -> None:
    key = (entry.config_family, entry.param_version)
    if key in _REGISTRY:
        existing = _REGISTRY[key]
        if existing != entry:
            raise AmbiguousConfigFamilyError(
                f"ambiguous schema registry entry for {key}"
            )
        return
    _REGISTRY[key] = entry


def clear_registry() -> None:
    _REGISTRY.clear()


def iter_schema_entries():
    return list(_REGISTRY.values())


def resolve_schema(parsed: Mapping[str, Any], *, schema_version: Optional[str] = None) -> SchemaEntry:
    if not isinstance(parsed, Mapping):
        raise ConfigSchemaError("parsed config must be an object")

    raw_module = parsed.get("module")
    if raw_module is None:
        raise UnknownModuleError("missing module")
    if not isinstance(raw_module, str) or not raw_module.strip():
        raise UnknownModuleError("module must be a non-empty string")

    canonical_module = normalize_module_id(raw_module)
    known_modules = {e.module for e in _REGISTRY.values()}
    if canonical_module not in known_modules:
        raise UnknownModuleError(f"unknown module: {raw_module!r}")

    param_version = parsed.get("param_version")
    if param_version is None:
        raise UnknownParamVersionError("missing param_version")
    if not isinstance(param_version, str) or not param_version.strip():
        raise UnknownParamVersionError("param_version must be a non-empty string")

    # config_family is stable identity derived from module/schema metadata.
    family_candidates = [e for e in _REGISTRY.values() if e.module == canonical_module]
    families = sorted({e.config_family for e in family_candidates})
    if not families:
        raise UnknownModuleError(f"no schema family for module: {canonical_module}")
    if len(families) != 1:
        raise AmbiguousConfigFamilyError(
            f"ambiguous config family for module {canonical_module}: {families}"
        )
    config_family = families[0]

    key = (config_family, param_version)
    entry = _REGISTRY.get(key)
    if entry is None:
        raise UnknownParamVersionError(
            f"unknown param_version {param_version!r} for config_family {config_family!r}"
        )

    if schema_version is not None:
        if not isinstance(schema_version, str) or not schema_version.strip():
            raise MissingSchemaVersionError("schema_version must be a non-empty string")
        if schema_version != entry.config_schema_version:
            raise MissingSchemaVersionError(
                f"schema_version mismatch: requested {schema_version!r}, resolved {entry.config_schema_version!r}"
            )

    if not entry.config_schema_version:
        raise MissingSchemaVersionError("resolved schema missing config_schema_version")

    return entry


def ensure_allowed_fields(effective: Mapping[str, Any], allowed_fields: Tuple[str, ...], *, context: str) -> None:
    allowed = set(allowed_fields)
    unknown = sorted([k for k in effective.keys() if k not in allowed])
    if unknown:
        raise UnknownFieldError(f"unknown {context} field(s): {unknown}")


def require_type(value: Any, expected: type | tuple[type, ...], field: str) -> None:
    if isinstance(expected, tuple):
        ok = isinstance(value, expected) and not (isinstance(value, bool) and bool not in expected)
    else:
        ok = isinstance(value, expected) and not (isinstance(value, bool) and expected is not bool)
    if not ok:
        exp_name = (
            tuple(t.__name__ for t in expected) if isinstance(expected, tuple) else expected.__name__
        )
        raise InvalidFieldTypeError(f"{field} must be {exp_name}")


def reject_bool_numeric(value: Any, field: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InvalidFieldTypeError(f"{field} must be numeric")
