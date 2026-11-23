"""Calendar attribution for session_anomalies (SCAN-021).

Additive annotation layer: never suppresses or alters detector events.
Calendar input is versioned JSON with sha256 recorded in outputs.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from scanline.prereg import cluster_key_for_event

CAL_ATTR_VERSION = "scan021-calendar-v1"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_calendar(path: Path) -> Tuple[Dict[str, Any], str]:
    raw = Path(path).read_bytes()
    obj = json.loads(raw.decode("utf-8"))
    if not isinstance(obj, dict):
        raise ValueError("calendar must be JSON object")
    rules = obj.get("rules")
    if not isinstance(rules, list):
        raise ValueError("calendar.rules must be list")
    return obj, sha256_bytes(raw)


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    d = date(year, month, 1)
    while d.weekday() != weekday:
        d += timedelta(days=1)
    d += timedelta(days=7 * (n - 1))
    if d.month != month:
        raise ValueError("nth weekday out of month")
    return d


def _last_weekday(year: int, month: int, weekday: int) -> date:
    import calendar
    last = date(year, month, calendar.monthrange(year, month)[1])
    while last.weekday() != weekday:
        last -= timedelta(days=1)
    return last


def resolve_rule_dates(rule: Mapping[str, Any], years: Sequence[int]) -> List[date]:
    rr = rule.get("recurrence")
    if not isinstance(rr, dict):
        # explicit date(s)
        d = rule.get("date")
        if isinstance(d, str):
            return [date.fromisoformat(d)]
        dates = rule.get("dates")
        if isinstance(dates, list):
            out = []
            for x in dates:
                if isinstance(x, str):
                    out.append(date.fromisoformat(x))
            return out
        raise ValueError(f"rule {rule.get('rule_id')} missing recurrence/date")
    rtype = rr.get("type")
    out: List[date] = []
    for y in years:
        if rtype == "fixed_date":
            out.append(date(y, int(rr["month"]), int(rr["day"])))
        elif rtype == "nth_weekday":
            out.append(_nth_weekday(y, int(rr["month"]), int(rr["weekday"]), int(rr["n"])))
        elif rtype == "last_weekday":
            out.append(_last_weekday(y, int(rr["month"]), int(rr["weekday"])))
        elif rtype == "fixed_date_observed":
            # US observed: Sat->Fri, Sun->Mon
            d = date(y, int(rr["month"]), int(rr["day"]))
            if d.weekday() == 5:
                d = d - timedelta(days=1)
            elif d.weekday() == 6:
                d = d + timedelta(days=1)
            out.append(d)
        else:
            raise ValueError(f"unknown recurrence type: {rtype}")
    return out


def rule_applies_to_symbol(rule: Mapping[str, Any], symbol: str) -> bool:
    scope = rule.get("venue_scope")
    if scope is None:
        return True
    if isinstance(scope, str):
        scope = [scope]
    if not isinstance(scope, list):
        return False
    sym = str(symbol).upper()
    # scope entries can be exact symbol, prefix, or group tag
    groups = rule.get("symbol_groups") if isinstance(rule.get("symbol_groups"), dict) else {}
    for s in scope:
        if not isinstance(s, str):
            continue
        if s.upper() == sym:
            return True
        if s.startswith("group:"):
            g = s.split(":", 1)[1]
            members = groups.get(g, [])
            if isinstance(members, list) and sym in [str(m).upper() for m in members]:
                return True
        if s.startswith("prefix:"):
            p = s.split(":", 1)[1].upper()
            if sym.startswith(p):
                return True
    return False


def cluster_members(events: Sequence[Mapping[str, Any]], cluster_key: Tuple[str, ...]) -> List[int]:
    idxs = []
    for i, e in enumerate(events):
        if tuple(cluster_key_for_event(dict(e))) == tuple(cluster_key):
            idxs.append(i)
    return idxs


def homogeneity_check(events: Sequence[Mapping[str, Any]], member_idxs: Sequence[int],
                      rule: Mapping[str, Any], all_symbols: Sequence[str]) -> Dict[str, Any]:
    """Homogeneity test per SCAN-020 §5(a).

    Returns diagnostic dict with in_scope/out_of_scope coverage and pass flag.
    """
    in_scope = [s for s in all_symbols if rule_applies_to_symbol(rule, s)]
    out_scope = [s for s in all_symbols if not rule_applies_to_symbol(rule, s)]
    member_syms = []
    for i in member_idxs:
        e = events[i]
        s = e.get("symbol")
        if isinstance(s, str):
            member_syms.append(s.upper())
    member_set = set(member_syms)
    in_scope_hit = [s for s in in_scope if s.upper() in member_set]
    out_scope_hit = [s for s in out_scope if s.upper() in member_set]
    in_cov = (len(in_scope_hit) / len(in_scope)) if in_scope else 0.0
    out_cov = (len(out_scope_hit) / len(out_scope)) if out_scope else 0.0
    # whole-day absence or uniform early close within scope; near-zero out-of-scope
    anomaly_types = set()
    for i in member_idxs:
        anomaly_types.add(events[i].get("anomaly_type"))
    uniform_pattern = anomaly_types.issubset({"missing_session", "stub_session", "sunday_anomaly"})
    # For holiday closure: expect high in-scope coverage, near-zero out-scope
    passes = in_cov >= 0.5 and out_cov <= 0.1 and uniform_pattern
    return {
        "in_scope_total": len(in_scope),
        "in_scope_hit": len(in_scope_hit),
        "out_scope_total": len(out_scope),
        "out_scope_hit": len(out_scope_hit),
        "in_scope_coverage": in_cov,
        "out_scope_coverage": out_cov,
        "anomaly_types": sorted(str(x) for x in anomaly_types),
        "passes": passes,
    }


def attribute_clusters(events: Sequence[Mapping[str, Any]], calendar: Mapping[str, Any],
                       calendar_sha256: str, years: Sequence[int],
                       all_symbols: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    """Produce calendar_match annotations. Additive only."""
    if all_symbols is None:
        syms = []
        for e in events:
            s = e.get("symbol")
            if isinstance(s, str):
                syms.append(s)
        all_symbols = sorted(set(syms))

    rules = calendar.get("rules", [])
    if not isinstance(rules, list):
        raise ValueError("calendar.rules must be list")

    # build cluster map
    clusters: Dict[Tuple[str, ...], List[int]] = {}
    for i, e in enumerate(events):
        k = tuple(cluster_key_for_event(dict(e)))
        clusters.setdefault(k, []).append(i)

    matches: List[Dict[str, Any]] = []
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        rule_id = rule.get("rule_id")
        dates = resolve_rule_dates(rule, years)
        date_set = {d.isoformat() for d in dates}
        for k, members in clusters.items():
            # cluster key: (type, session_date, [hour])
            session_date = k[1] if len(k) > 1 else None
            if session_date not in date_set:
                continue
            # symbol scope: at least one member in scope
            in_scope_members = [i for i in members if rule_applies_to_symbol(rule, str(events[i].get("symbol", "")))]
            if not in_scope_members:
                continue
            homog = homogeneity_check(events, members, rule, all_symbols)
            matches.append({
                "rule_id": rule_id,
                "session_date": session_date,
                "cluster_key": list(k),
                "cluster_size": len(members),
                "in_scope_member_count": len(in_scope_members),
                "member_event_indices": members,
                "homogeneity": homog,
                "calendar_sha256": calendar_sha256,
                "attribution_version": CAL_ATTR_VERSION,
                "source": rule.get("source"),
                "confidence": rule.get("confidence"),
            })

    return {
        "attribution_version": CAL_ATTR_VERSION,
        "calendar_sha256": calendar_sha256,
        "rule_count": len(rules),
        "years": list(years),
        "cluster_count": len(clusters),
        "match_count": len(matches),
        "matches": matches,
    }
