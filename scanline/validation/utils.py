"""Shared helpers for Scanline validation (SCAN-015)."""

import hashlib
import json
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List

from scanline.schema import normalize_module_id


def parse_ts(ts_str: str) -> datetime:
    if ts_str.endswith("Z"):
        ts_str = ts_str[:-1] + "+00:00"
    return datetime.fromisoformat(ts_str)


def validate_timestamp(ts_str: str) -> bool:
    try:
        parse_ts(ts_str)
        return True
    except (ValueError, TypeError):
        return False


def check_numeric(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def get_first_event_ts(events: List[Dict[str, Any]]) -> datetime:
    parsed_ts = [parse_ts(e["event_ts"]) for e in events]
    return min(parsed_ts)


def cluster_expected_bars(param_data: Any, symbol: Any) -> Any:
    if not isinstance(param_data, dict):
        return None
    for key in ("expected_bars", "weekday_expected_bars", "expected_weekday_bars"):
        val = param_data.get(key)
        if isinstance(val, dict):
            if symbol in val:
                return val.get(symbol)
    for key in ("clusters", "cluster_schedule", "clusters_schedule", "session_clusters", "cluster_expected_bars"):
        val = param_data.get(key)
        if isinstance(val, dict):
            c = val.get(symbol)
            if isinstance(c, int) and not isinstance(c, bool):
                return c
            if isinstance(c, dict):
                for ek in ("expected_bars", "weekday_expected_bars", "expected_weekday_bars", "expected"):
                    if ek in c:
                        return c.get(ek)
        if isinstance(val, list):
            for item in val:
                if isinstance(item, dict):
                    if item.get("symbol") == symbol:
                        for ek in ("expected_bars", "weekday_expected_bars", "expected_weekday_bars", "expected"):
                            if ek in item:
                                return item.get(ek)
    clusters = param_data.get("clusters")
    if isinstance(clusters, dict):
        for cname, cinfo in clusters.items():
            if isinstance(cinfo, dict) and cinfo.get("symbol") == symbol:
                for ek in ("expected_bars", "weekday_expected_bars", "expected_weekday_bars", "expected"):
                    if ek in cinfo:
                        return cinfo.get(ek)
    return None


def normalize_module(raw_module: Any) -> Any:
    return normalize_module_id(raw_module)


def grid_member(grid_steps: Any, symbol: Any, price: Any) -> bool:
    step = grid_steps.get(symbol) if isinstance(grid_steps, dict) else None
    if step is None:
        return False
    try:
        dprice = Decimal(str(price))
        dstep = Decimal(str(step))
    except (InvalidOperation, ValueError, TypeError):
        return False
    if dstep <= 0:
        return False
    try:
        return (dprice % dstep) == 0
    except Exception:
        return False
