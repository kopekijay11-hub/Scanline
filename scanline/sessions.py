"""Session-anomaly detector for Scanline module 2.

H1-only: detects missing/stub sessions, Sunday anomalies, and intra-session gaps.
"""

import json
from datetime import datetime, timedelta, timezone, time
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

INTERVAL_H1 = timedelta(hours=1)
GAP_TOLERANCE = timedelta(minutes=1)


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


_CLUSTER_FIELD_ALIASES = {
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
    "maintenance_local_start": "maintenance_local_start",
    "maintenance_start_local": "maintenance_local_start",
    "rollover_local_start": "maintenance_local_start",
    "maintenance_start": "maintenance_local_start",
    "maintenance_local_end": "maintenance_local_end",
    "maintenance_end_local": "maintenance_local_end",
    "rollover_local_end": "maintenance_local_end",
    "maintenance_end": "maintenance_local_end",
    "stub_tolerance": "stub_tolerance",
    "stub_tol": "stub_tolerance",
    "sun_tolerance": "sun_tolerance",
    "sun_tol": "sun_tolerance",
    "sunday_tolerance": "sun_tolerance",
}

_CLUSTER_CONTAINERS = ("clusters", "cluster_schedule", "clusters_schedule", "session_clusters", "cluster_expected_bars")

_FIXED_UTC_KEYS = {"maintenance_utc_start", "maintenance_start_utc", "maintenance_utc_end", "maintenance_end_utc"}


def _require_int(value, field, minimum=0):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field} must be an integer")
    if value < minimum:
        raise ValueError(f"{field} must be >= {minimum}")
    return value


def _validate_hhmm(value, field):
    """Validate an 'HH:MM' string and return (hour, minute)."""
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string 'HH:MM'")
    parts = value.strip().split(":")
    if len(parts) not in (1, 2):
        raise ValueError(f"{field} must be 'HH:MM'")
    try:
        h = int(parts[0])
        m = int(parts[1]) if len(parts) > 1 else 0
    except (TypeError, ValueError):
        raise ValueError(f"{field} must be 'HH:MM'")
    if not (0 <= h <= 23 and 0 <= m <= 59):
        raise ValueError(f"{field} out of range")
    return h, m


def _top_level_value(params, symbol, keys):
    for key in keys:
        val = params.get(key) if isinstance(params, dict) else None
        if isinstance(val, dict):
            if symbol in val:
                return val[symbol]
        elif isinstance(val, (int, float)) and not isinstance(val, bool):
            return val
    return None


def _find_cluster_record(params, symbol):
    record = None
    for key in _CLUSTER_CONTAINERS:
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
        # flat configuration: pull cluster fields directly from params
        record = {}
        for k, v in (params.items() if isinstance(params, dict) else []):
            if k in _CLUSTER_FIELD_ALIASES or k in _FIXED_UTC_KEYS or k == "symbol":
                record[k] = v
    return record if record is not None else {}


def _cluster_info(params, symbol):
    if not isinstance(params, dict):
        raise ValueError("session params must be a dict")

    raw = _find_cluster_record(params, symbol)
    if not isinstance(raw, dict):
        raise ValueError("cluster configuration must be a dict")

    # normalize aliases
    info = {}
    for k, v in raw.items():
        if k == "symbol":
            continue
        if k in _CLUSTER_FIELD_ALIASES:
            canon = _CLUSTER_FIELD_ALIASES[k]
            if canon in info and info[canon] != v:
                raise ValueError(f"conflicting alias values for {canon}")
            info[canon] = v
        elif k in _FIXED_UTC_KEYS:
            info[k] = v
        else:
            raise ValueError(f"unknown session configuration field: {k}")

    # expected_bars (required, but allow top-level fallback for compatibility)
    if "expected_bars" not in info:
        eb = _top_level_value(params, symbol, ("expected_bars", "weekday_expected_bars", "expected_weekday_bars"))
        if eb is not None:
            info["expected_bars"] = eb
    if "expected_bars" not in info:
        raise ValueError("expected_bars is required")
    info["expected_bars"] = _require_int(info["expected_bars"], "expected_bars", 0)

    # expected_sun_bars (optional, default 0)
    if "expected_sun_bars" not in info:
        es = _top_level_value(params, symbol, ("expected_sun_bars", "sunday_expected_bars", "expected_sunday_bars"))
        if es is not None:
            info["expected_sun_bars"] = es
        else:
            info["expected_sun_bars"] = 0
    info["expected_sun_bars"] = _require_int(info["expected_sun_bars"], "expected_sun_bars", 0)

    # zone (optional, default UTC)
    if "zone" not in info:
        z = None
        for key in ("zone", "timezone", "tz", "time_zone"):
            if key in params and not isinstance(params.get(key), dict):
                z = params.get(key)
                break
        info["zone"] = "UTC" if z is None else z
    if not isinstance(info["zone"], str) or not info["zone"].strip():
        raise ValueError("zone must be a non-empty string")
    try:
        ZoneInfo(info["zone"])
    except Exception:
        raise ValueError(f"invalid timezone: {info['zone']}")

    # maintenance local start (optional, default 17:00)
    if "maintenance_local_start" not in info:
        # fixed utc override?
        if "maintenance_utc_start" in info or "maintenance_start_utc" in info:
            info["maintenance_local_start"] = info.get("maintenance_utc_start") or info.get("maintenance_start_utc")
        else:
            ml = None
            for key in ("maintenance_local_start", "maintenance_start_local", "rollover_local_start"):
                if key in params and not isinstance(params.get(key), dict):
                    ml = params.get(key)
                    break
            if ml is None:
                for key in ("maintenance_start",):
                    if key in params and not isinstance(params.get(key), dict):
                        ml = params.get(key)
                        break
            info["maintenance_local_start"] = "17:00" if ml is None else ml
    # if fixed utc provided as int? validate below
    _validate_hhmm(info["maintenance_local_start"], "maintenance_local_start")

    # maintenance local end (optional, default 18:00)
    if "maintenance_local_end" not in info:
        if "maintenance_utc_end" in info or "maintenance_end_utc" in info:
            info["maintenance_local_end"] = info.get("maintenance_utc_end") or info.get("maintenance_end_utc")
        else:
            ml = None
            for key in ("maintenance_local_end", "maintenance_end_local", "rollover_local_end"):
                if key in params and not isinstance(params.get(key), dict):
                    ml = params.get(key)
                    break
            if ml is None:
                for key in ("maintenance_end",):
                    if key in params and not isinstance(params.get(key), dict):
                        ml = params.get(key)
                        break
            info["maintenance_local_end"] = "18:00" if ml is None else ml
    _validate_hhmm(info["maintenance_local_end"], "maintenance_local_end")

    # fixed utc fields validation
    for fk in ("maintenance_utc_start", "maintenance_start_utc"):
        if fk in info:
            _validate_hhmm(info[fk], fk)
    for fk in ("maintenance_utc_end", "maintenance_end_utc"):
        if fk in info:
            _validate_hhmm(info[fk], fk)

    # tolerances (optional defaults)
    if "stub_tolerance" not in info:
        st = params.get("stub_tolerance", 1) if not isinstance(params.get("stub_tolerance"), dict) else 1
        info["stub_tolerance"] = 1 if st is None else st
    info["stub_tolerance"] = _require_int(info["stub_tolerance"], "stub_tolerance", 0)

    if "sun_tolerance" not in info:
        st = params.get("sun_tolerance", 0) if not isinstance(params.get("sun_tolerance"), dict) else 0
        info["sun_tolerance"] = 0 if st is None else st
    info["sun_tolerance"] = _require_int(info["sun_tolerance"], "sun_tolerance", 0)

    # maintenance consistency: start and end must not be identical
    sh, sm = _validate_hhmm(info["maintenance_local_start"], "maintenance_local_start")
    eh, em = _validate_hhmm(info["maintenance_local_end"], "maintenance_local_end")
    if sh == eh and sm == em:
        raise ValueError("maintenance window start and end must differ")

    # fixed utc flag
    if "maintenance_utc_start" in info or "maintenance_start_utc" in info:
        info["_fixed_utc"] = True
    else:
        info["_fixed_utc"] = False

    return info

def _maintenance_utc_interval(info: Dict[str, Any], date) -> List[Tuple[datetime, datetime]]:
    """Return candidate maintenance windows (UTC) that can affect ``date``.

    Fixed-UTC mode returns a single window defined in UTC. Local mode derives
    candidate local calendar dates from ``date`` (UTC) +/- one day and keeps
    those whose UTC span intersects the UTC day ``[date, date+1)``.
    """
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
        return [(start, end)]
    sh, sm = _parse_hhmm(info.get("maintenance_local_start", "17:00"))
    eh, em = _parse_hhmm(info.get("maintenance_local_end", "18:00"))
    day_start = datetime(date.year, date.month, date.day, tzinfo=timezone.utc)
    day_end = day_start + timedelta(days=1)
    result: List[Tuple[datetime, datetime]] = []
    seen = set()
    for delta in (-1, 0, 1):
        ld = date + timedelta(days=delta)
        local_start = datetime(ld.year, ld.month, ld.day, sh, sm, tzinfo=zone)
        local_end = datetime(ld.year, ld.month, ld.day, eh, em, tzinfo=zone)
        if local_end <= local_start:
            local_end = local_end + timedelta(days=1)
        start_utc = local_start.astimezone(timezone.utc)
        end_utc = local_end.astimezone(timezone.utc)
        # keep only windows whose raw UTC span intersects this UTC day
        if end_utc <= day_start or start_utc >= day_end:
            continue
        key = (start_utc, end_utc)
        if key in seen:
            continue
        seen.add(key)
        result.append(key)
    if not result:
        # fallback to original behavior (should not occur)
        local_start = datetime(date.year, date.month, date.day, sh, sm, tzinfo=zone)
        local_end = datetime(date.year, date.month, date.day, eh, em, tzinfo=zone)
        if local_end <= local_start:
            local_end = local_end + timedelta(days=1)
        result.append((local_start.astimezone(timezone.utc), local_end.astimezone(timezone.utc)))
    return result


def _parse_hhmm(s: Any) -> Tuple[int, int]:
    """Parse an 'HH:MM' (or hour) value into (hour, minute).

    Raises ValueError for malformed or unsupported input instead of
    silently defaulting to midnight.
    """
    if isinstance(s, str):
        parts = s.strip().split(":")
        if len(parts) not in (1, 2):
            raise ValueError("invalid HH:MM value")
        h = int(parts[0])
        m = int(parts[1]) if len(parts) > 1 else 0
        return h, m
    if isinstance(s, (int, float)) and not isinstance(s, bool):
        # treat as hour
        return int(s), 0
    raise ValueError("invalid HH:MM value")


def _group_bars_by_utc_date(
    bars_sorted: List[Dict[str, Any]],
) -> Tuple[Dict[Any, int], Dict[Any, List[datetime]], Any, Any]:
    """Group bars by UTC calendar date; return counts, per-date timestamps, and bounds."""
    counts: Dict[Any, int] = {}
    by_date_bars: Dict[Any, List[datetime]] = {}
    for b in bars_sorted:
        ts = _parse_ts(b["open_ts"])
        d = ts.date()
        counts[d] = counts.get(d, 0) + 1
        by_date_bars.setdefault(d, []).append(ts)
    first_date = _parse_ts(bars_sorted[0]["open_ts"]).date()
    last_date = _parse_ts(bars_sorted[-1]["open_ts"]).date()
    return counts, by_date_bars, first_date, last_date


def _session_level_anomalies(
    first_date: Any,
    last_date: Any,
    counts: Dict[Any, int],
    symbol: Any,
    expected_weekday: int,
    expected_sun: int,
    stub_tol: int,
    sun_tol: int,
    defined_at: Any,
    param_version: Any,
) -> List[Dict[str, Any]]:
    """Detect missing/stub/Sunday anomalies for interior UTC dates (unchanged semantics)."""
    events: List[Dict[str, Any]] = []
    cur = first_date + timedelta(days=1)
    while cur < last_date:
        observed = counts.get(cur, 0)
        weekday = cur.weekday()  # Monday=0 ... Sunday=6
        is_sunday = weekday == 6
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
    return events


def _intra_session_gap_events(
    by_date_bars: Dict[Any, List[datetime]],
    info: Dict[str, Any],
    symbol: Any,
    expected_weekday: int,
    defined_at: Any,
    param_version: Any,
) -> List[Dict[str, Any]]:
    """Detect intra-session gaps for consecutive bars within the same UTC date."""
    events: List[Dict[str, Any]] = []
    for d, ts_list in by_date_bars.items():
        ts_list = sorted(ts_list)
        maint_windows = _maintenance_utc_interval(info, d)
        for i in range(1, len(ts_list)):
            prev = ts_list[i - 1]
            curr = ts_list[i]
            if (curr - prev) > INTERVAL_H1 + GAP_TOLERANCE:
                # allowed if within any candidate maintenance window
                allowed = False
                for maint_start, maint_end in maint_windows:
                    if prev >= maint_start - timedelta(minutes=30) and curr <= maint_end + timedelta(minutes=30):
                        allowed = True
                        break
                    # also if gap interval overlaps maintenance window substantially
                    if not allowed:
                        overlap_start = max(prev, maint_start)
                        overlap_end = min(curr, maint_end)
                        if overlap_end > overlap_start and (overlap_end - overlap_start) >= timedelta(minutes=30):
                            allowed = True
                            break
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
    return events


def _core_compute(bars: List[Dict[str, Any]], params: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Compute session-anomaly events for a bar series (semantics preserved)."""
    if isinstance(params, dict):
        validate_session_config(params)
    if not bars:
        return []
    bars_sorted = sorted(bars, key=lambda b: _parse_ts(b["open_ts"]))
    _symbols = {b.get("symbol") if isinstance(b, dict) else None for b in bars_sorted}
    if len(_symbols) > 1:
        raise ValueError("mixed-symbol input: bars contain multiple distinct symbols")
    symbol = bars_sorted[0].get("symbol") if isinstance(bars_sorted[0], dict) else None
    if symbol is None:
        symbol = None
    _timeframes = {(b.get("timeframe") if (isinstance(b, dict) and b.get("timeframe") is not None) else "H1") for b in bars_sorted}
    if len(_timeframes) > 1:
        raise ValueError("mixed-timeframe input: bars contain multiple distinct timeframes")
    timeframe = bars_sorted[0].get("timeframe", "H1") if isinstance(bars_sorted[0], dict) else "H1"
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

    counts, by_date_bars, first_date, last_date = _group_bars_by_utc_date(bars_sorted)

    events: List[Dict[str, Any]] = []
    events.extend(_session_level_anomalies(
        first_date, last_date, counts, symbol, expected_weekday, expected_sun,
        stub_tol, sun_tol, defined_at, param_version,
    ))
    events.extend(_intra_session_gap_events(
        by_date_bars, info, symbol, expected_weekday, defined_at, param_version,
    ))

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
    if isinstance(bars, list) and bars and isinstance(bars[0], (list, tuple)):
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


_SESSION_TOP_LEVEL_KEYS = {
    "module",
    "param_version",
    "version",
    "frozen_at",
    "clusters",
    "cluster_schedule",
    "clusters_schedule",
    "session_clusters",
    "cluster_expected_bars",
    "expected_bars",
    "weekday_expected_bars",
    "expected_weekday_bars",
    "expected_sun_bars",
    "sunday_expected_bars",
    "expected_sunday_bars",
    "zone",
    "timezone",
    "tz",
    "time_zone",
    "maintenance_local_start",
    "maintenance_start_local",
    "rollover_local_start",
    "maintenance_start",
    "maintenance_local_end",
    "maintenance_end_local",
    "rollover_local_end",
    "maintenance_end",
    "maintenance_utc_start",
    "maintenance_start_utc",
    "maintenance_utc_end",
    "maintenance_end_utc",
    "stub_tolerance",
    "stub_tol",
    "sun_tolerance",
    "sun_tol",
    "sunday_tolerance",
}

_CLUSTER_CONTAINERS = ("clusters", "cluster_schedule", "clusters_schedule", "session_clusters", "cluster_expected_bars")


def _session_symbols(params):
    syms = []
    for key in _CLUSTER_CONTAINERS:
        val = params.get(key) if isinstance(params, dict) else None
        if isinstance(val, dict):
            syms.extend(list(val.keys()))
        elif isinstance(val, list):
            for item in val:
                if isinstance(item, dict) and "symbol" in item:
                    syms.append(item["symbol"])
    return syms


def validate_session_config(params):
    if not isinstance(params, dict):
        raise ValueError("session params must be a dict")
    for k in params:
        if k not in _SESSION_TOP_LEVEL_KEYS:
            raise ValueError(f"unknown session configuration field: {k}")
    syms = _session_symbols(params)
    if syms:
        for sym in syms:
            _cluster_info(params, sym)
    else:
        # flat configuration
        if any(k in _CLUSTER_FIELD_ALIASES or k in _FIXED_UTC_KEYS for k in params):
            _cluster_info(params, "")
    return None


def session_config_errors(params):
    try:
        validate_session_config(params)
        return []
    except Exception as e:
        return [str(e)]


# aliases
validate_session_params = validate_session_config
validate_session_configuration = validate_session_config
validate_session_anomalies_config = validate_session_config
