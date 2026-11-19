"""Event schema for Scanline: closed-field definitions."""

from typing import Set

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

# Batch header fields - closed set
BATCH_HEADER_FIELDS: Set[str] = {
    "module",
    "scan_mode",
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
