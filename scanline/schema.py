"""Event schema for Scanline: closed-field definitions."""

from typing import Dict, Set

# Closed set of event fields - NO other fields permitted
EVENT_FIELDS: Set[str] = {
    "symbol",
    "timeframe",
    "level_type",
    "level_price",
    "defined_at",
    "distance_atr",
    "atr_window",
    "atr_basis",
    "param_version",
    "event_ts",
}

# Module 1 level types
LEVEL_TYPES: Set[str] = {
    "d1_prior_high",
    "d1_prior_low",
    "d1_session_structure",
    "grid_round",
}

# Emission timeframes
EMISSION_TIMEFRAMES: Set[str] = {"H1", "H4"}

# Module 2 (session_anomalies) closed event fields
SESSION_EVENT_FIELDS: Set[str] = {
    "symbol",
    "timeframe",
    "anomaly_type",
    "session_date",
    "expected_bars",
    "observed_bars",
    "defined_at",
    "gap_hours",
    "param_version",
    "event_ts",
}

ANOMALY_TYPES: Set[str] = {
    "missing_session",
    "stub_session",
    "intra_session_gap",
    "sunday_anomaly",
}

SESSION_EMISSION_TIMEFRAMES: Set[str] = {"H1"}

# Batch header fields - closed set
BATCH_HEADER_FIELDS: Set[str] = {
    "module",
    "scan_mode",
    "evidence_tier",
    "param_file",
    "param_sha256",
    "param_version",
    "frozen_at",
    "universe",
    "emission_timeframes",
    "definition_timeframe",
    "batch_start_ts",
    "batch_end_ts",
}

# Definition timeframe
DEFINITION_TIMEFRAME = "D1"

# ATR basis - Phase 0 basis token only (DEVIATION OF RECORD: collapsed from "closed-bar basis + bar interval")
ATR_BASIS = "closed_bars_only"

# Module registry
MODULES: Set[str] = {"level_proximity", "session_anomalies"}

EVENT_FIELDS_BY_MODULE: Dict[str, Set[str]] = {
    "level_proximity": EVENT_FIELDS,
    "session_anomalies": SESSION_EVENT_FIELDS,
}

LEVEL_TYPES_BY_MODULE: Dict[str, Set[str]] = {
    "level_proximity": LEVEL_TYPES,
}

ANOMALY_TYPES_BY_MODULE: Dict[str, Set[str]] = {
    "session_anomalies": ANOMALY_TYPES,
}

EMISSION_TIMEFRAMES_BY_MODULE: Dict[str, Set[str]] = {
    "level_proximity": EMISSION_TIMEFRAMES,
    "session_anomalies": SESSION_EMISSION_TIMEFRAMES,
}
