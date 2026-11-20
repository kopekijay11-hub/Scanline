"""Session-anomaly detector for Scanline module 2.

H1-only: detects missing/stub sessions, Sunday anomalies, and intra-session gaps.
"""

import json
from datetime import datetime, timedelta, timezone, time
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

INTERVAL_H1 = timedelta(hours=1)


def _parse_ts(ts_str: str) -> datetime:
    if ts_str.endswith("Z"):
        ts_str = ts_str[:-1] + "+00:00"
    dt = datetime.fromisoformat(ts_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _fmt_ts(dt: datetime) -> str:
    dt = dt.astimezone(timezone.utc)
    s = dt.isoformat()
    if s.endswith("+00:00"):
        s = s[:-6] + "Z"
    return s


def _cluster_info(params: Dict[str, Any], symbol: str) -> Dict[str, Any]:
    info: Dict[str, Any] = {}
    # find cluster record
    record = None
    for key in ("clusters", "cluster_schedule", "clusters_schedule", "session_clusters"):
        val = params.get(key) if isinstance(params, dict) else None
        if isinstance(val, dict):
            if symbol in val:
                c = val[symbol]
                if isinstance(c, dict):
                    record = dict(c)
                elif isinstance(c, (int, float)) and not isinstance(c, bool):
                    record = {"expected_bars": c}
            if record is None:
                for cname, cinfo in val.items():
                    if isinstance(cinfo, dict) and cinfo.get("symbol") == symbol:
                        record = dict(cinfo)
                        break
        if isinstance(val, list):
            for item in val:
                if isinstance(item, dict) and item.get("symbol") == symbol:
                    record = dict(item)
                    break
    if record is None:
        record = {}
    info.update(record)

    # expected bars
    if "expected_bars" not in info:
        eb = None
        for key in ("expected_bars", "weekday_expected_bars", "expected_weekday_bars"):
            val = params.get(key) if isinstance(params, dict) else None
            if isinstance(val, dict) and symbol in val:
                eb = val[symbol]
                break
        if eb is not None:
            info["expected_bars"] = eb
    if "expected_bars" not in info:
        info["expected_bars"] = params.get("expected_bars", 24) if not isinstance(params.get("expected_bars"), dict) else 24
    try:
        info["expected_bars"] = int(info["expected_bars"])
    except (TypeError, ValueError):
        info["expected_bars"] = 24

    # sunday expected
    if "expected_sun_bars" not in info:
        for key in ("expected_sun_bars", "sunday_expected_bars", "expected_sunday_bars"):
            if key in params and isinstance(params.get(key), dict) and symbol in params[key]:
                info["expected_sun_bars"] = params[key][symbol]
                break
    if "expected_sun_bars" not in info:
        info["expected_sun_bars"] = info.get("sunday_bars", 0)
    try:
        info["expected_sun_bars"] = int(info["expected_sun_bars"])
    except (TypeError, ValueError):
        info["expected_sun_bars"] = 0

    # zone
    if "zone" not in info:
        for key in ("zone", "timezone", "tz", "time_zone"):
            if key in info:
                break
            if isinstance(params, dict) and key in params:
                info["zone"] = params[key]
                break
    if "zone" not in info:
        info["zone"] = "UTC"
    # maintenance local times
    if "maintenance_local_start" not in info and "maintenance_start" not in info:
        for key in ("maintenance_local_start", "maintenance_start_local", "rollover_local_start"):
            if isinstance(params, dict) and key in params:
                info["maintenance_local_start"] = params[key]
                break
    if "maintenance_local_start" not in info and "maintenance_start" in info:
        info["maintenance_local_start"] = info.get("maintenance_start")
    if "maintenance_local_start" not in info:
        info["maintenance_local_start"] = "17:00"

    if "maintenance_local_end" not in info and "maintenance_end" not in info:
        for key in ("maintenance_local_end", "maintenance_end_local", "rollover_local_end"):
            if isinstance(params, dict) and key in params:
                info["maintenance_local_end"] = params[key]
                break
    if "maintenance_local_end" not in info and "maintenance_end" in info:
        info["maintenance_local_end"] = info.get("maintenance_end")
    if "maintenance_local_end" not in info:
        info["maintenance_local_end"] = "18:00"

    # tolerances
    if "stub_tolerance" not in info:
        info["stub_tolerance"] = params.get("stub_tolerance", 1) if isinstance(params, dict) else 1
    if "sun_tolerance" not in info:
        info["sun_tolerance"] = params.get("sun_tolerance", 0) if isinstance(params, dict) else 0

    # fixed utc maintenance override
    if "maintenance_utc_start" in info or "maintenance_start_utc" in info:
        info["_fixed_utc"] = True
    else:
        info["_fixed_utc"] = False

    return info


def _maintenance_utc_interval(info: Dict[str, Any], date) -> Tuple[datetime, datetime]:
    zone = ZoneInfo(info.get("zone", "UTC"))
    if info.get("_fixed_utc"):
        start_str = info.get("maintenance_utc_start") or info.get("maintenance_start_utc") or info.get("maintenance_local_start")
        end_str = info.get("maintenance_utc_end") or info.get("maintenance_end_utc") or info.get("maintenance_local_end")
        sh, sm = _parse_hhmm(start_str)
        eh, em = _parse_hhmm(end_str)
        start = datetime(date.year, date.month, date.day, sh, sm, tzinfo=timezone.utc)
        end = datetime(date.year, date.month, date.day, eh, em, tzinfo=timezone.utc)
        if end <= start:
            end = end + timedelta(days=1)
        return start, end
    sh, sm = _parse_hhmm(info.get("maintenance_local_start", "17:00"))
    eh, em = _parse_hhmm(info.get("maintenance_local_end", "18:00"))
    local_start = datetime(date.year, date.month, date.day, sh, sm, tzinfo=zone)
    local_end = datetime(date.year, date.month, date.day, eh, em, tzinfo=zone)
    if local_end <= local_start:
        local_end = local_end + timedelta(days=1)
    return local_start.astimezone(timezone.utc), local_end.astimezone(timezone.utc)


def _parse_hhmm(s: Any) -> Tuple[int, int]:
    if isinstance(s, str):
        parts = s.strip().split(":")
        h = int(parts[0])
        m = int(parts[1]) if len(parts) > 1 else 0
        return h, m
    if isinstance(s, (int, float)) and not isinstance(s, bool):
        # treat as hour
        return int(s), 0
    return 0, 0


def _core_compute(bars: List[Dict[str, Any]], params: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not bars:
        return []
    bars_sorted = sorted(bars, key=lambda b: _parse_ts(b["open_ts"]))
    symbol = bars_sorted[0].get("symbol")
    if symbol is None:
        symbol = None
    timeframe = bars_sorted[0].get("timeframe", "H1")
    if timeframe is None:
        timeframe = "H1"

    info = _cluster_info(params if isinstance(params, dict) else {}, symbol if symbol is not None else "")
    expected_weekday = int(info.get("expected_bars", 24))
    expected_sun = int(info.get("expected_sun_bars", 0))
    stub_tol = int(info.get("stub_tolerance", 1))
    sun_tol = int(info.get("sun_tolerance", 0))
    frozen_at = params.get("frozen_at") if isinstance(params, dict) else None
    param_version = params.get("param_version") if isinstance(params, dict) else None
    defined_at = frozen_at if frozen_at is not None else _fmt_ts(_parse_ts(bars_sorted[0]["open_ts"]))

    # counts per UTC date
    counts: Dict[Any, int] = {}
    by_date_bars: Dict[Any, List[datetime]] = {}
    for b in bars_sorted:
        ts = _parse_ts(b["open_ts"])
        d = ts.date()
        counts[d] = counts.get(d, 0) + 1
        by_date_bars.setdefault(d, []).append(ts)

    first_ts = _parse_ts(bars_sorted[0]["open_ts"])
    last_ts = _parse_ts(bars_sorted[-1]["open_ts"])
    first_date = first_ts.date()
    last_date = last_ts.date()

    events: List[Dict[str, Any]] = []

    # session-level anomalies for dates strictly inside bounds
    cur = first_date + timedelta(days=1)
    while cur < last_date:
        observed = counts.get(cur, 0)
        weekday = cur.weekday()  # Monday=0 ... Sunday=6
        is_sunday = (weekday == 6)
        if is_sunday:
            if abs(observed - expected_sun) > sun_tol:
                events.append({
                    "symbol": symbol,
                    "timeframe": "H1",
                    "anomaly_type": "sunday_anomaly",
                    "session_date": cur.isoformat(),
                    "expected_bars": expected_sun,
                    "observed_bars": observed,
                    "defined_at": defined_at,
                    "gap_hours": 0,
                    "param_version": param_version,
                    "event_ts": _fmt_ts(datetime(cur.year, cur.month, cur.day, 23, 0, tzinfo=timezone.utc)),
                })
        else:
            # Monday-Friday (0-4) only; Saturday skip
            if weekday <= 4:
                if observed == 0 and expected_weekday > 0:
                    events.append({
                        "symbol": symbol,
                        "timeframe": "H1",
                        "anomaly_type": "missing_session",
                        "session_date": cur.isoformat(),
                        "expected_bars": expected_weekday,
                        "observed_bars": 0,
                        "defined_at": defined_at,
                        "gap_hours": 0,
                        "param_version": param_version,
                        "event_ts": _fmt_ts(datetime(cur.year, cur.month, cur.day, 23, 0, tzinfo=timezone.utc)),
                    })
                elif 0 < observed < expected_weekday - stub_tol:
                    events.append({
                        "symbol": symbol,
                        "timeframe": "H1",
                        "anomaly_type": "stub_session",
                        "session_date": cur.isoformat(),
                        "expected_bars": expected_weekday,
                        "observed_bars": observed,
                        "defined_at": defined_at,
                        "gap_hours": 0,
                        "param_version": param_version,
                        "event_ts": _fmt_ts(datetime(cur.year, cur.month, cur.day, 23, 0, tzinfo=timezone.utc)),
                    })
        cur = cur + timedelta(days=1)

    # intra-session gaps: consecutive H1 within same UTC date
    for d, ts_list in by_date_bars.items():
        ts_list = sorted(ts_list)
        maint_start, maint_end = _maintenance_utc_interval(info, d)
        for i in range(1, len(ts_list)):
            prev = ts_list[i - 1]
            curr = ts_list[i]
            if (curr - prev) > INTERVAL_H1 + timedelta(minutes=1):
                # allowed if within maintenance window
                allowed = False
                if prev >= maint_start - timedelta(minutes=30) and curr <= maint_end + timedelta(minutes=30):
                    allowed = True
                # also if gap interval overlaps maintenance window substantially
                if not allowed:
                    overlap_start = max(prev, maint_start)
                    overlap_end = min(curr, maint_end)
                    if overlap_end > overlap_start and (overlap_end - overlap_start) >= timedelta(minutes=30):
                        allowed = True
                if not allowed:
                    gap_hours = int((curr - prev).total_seconds() // 3600)
                    if gap_hours < 1:
                        gap_hours = 1
                    events.append({
                        "symbol": symbol,
                        "timeframe": "H1",
                        "anomaly_type": "intra_session_gap",
                        "session_date": d.isoformat(),
                        "expected_bars": expected_weekday,
                        "observed_bars": len(ts_list),
                        "defined_at": defined_at,
                        "gap_hours": gap_hours,
                        "param_version": param_version,
                        "event_ts": _fmt_ts(curr),
                    })

    events.sort(key=lambda e: (e["event_ts"], e["anomaly_type"], e["session_date"]))
    return events


def _normalize_args(args, kwargs):
    # returns (list_of_bar_lists_per_symbol? Actually we want list of (symbol,bars))
    params = kwargs.get("params")
    bars = None
    symbol = kwargs.get("symbol")
    # positional parsing
    positional = list(args)
    if len(positional) == 1:
        bars = positional[0]
    elif len(positional) == 2:
        # could be (bars, params) or (symbol, bars)
        if isinstance(positional[1], dict) and ("module" in positional[1] or "param_version" in positional[1] or "clusters" in positional[1] or "expected_bars" in positional[1]):
            bars = positional[0]
            params = positional[1]
        else:
            symbol = positional[0]
            bars = positional[1]
    elif len(positional) >= 3:
        # (symbol, bars, params) or (bars, params, ...)
        if isinstance(positional[0], str):
            symbol = positional[0]
            bars = positional[1]
            params = positional[2]
        else:
            bars = positional[0]
            params = positional[1]
    if params is None:
        params = {}
    return symbol, bars, params


def compute_events(*args, **kwargs):
    symbol, bars, params = _normalize_args(args, kwargs)
    if isinstance(bars, dict):
        # symbol -> bars
        all_events = []
        for sym, bs in bars.items():
            all_events.extend(_core_compute(bs, params))
        return all_events
    if isinstance(bars, list) and bars and isinstance(bars[0], dict) and "open_ts" not in bars[0] and isinstance(bars[0], (list, tuple)):
        # list of (symbol, bars)
        all_events = []
        for item in bars:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                all_events.extend(_core_compute(item[1], params))
        return all_events
    if bars is None:
        bars = []
    # if symbol provided and bars list, tag bars? core uses bar symbol
    if symbol is not None and isinstance(bars, list):
        for b in bars:
            if isinstance(b, dict) and "symbol" not in b:
                b["symbol"] = symbol
    return _core_compute(bars, params)


# aliases
compute_session_events = compute_events
compute_session_anomalies = compute_events
detect_session_anomalies = compute_events
scan_sessions = compute_events
