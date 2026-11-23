"""Pre-registration arithmetic for session_anomalies (SCAN-021).

Cluster-based exact conditional ceiling test. Pure, deterministic, tested.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


@dataclass(frozen=True)
class CeilingResult:
    k_b: int
    k_a: int
    e_b: float
    e_a: float
    alpha: float
    r: float
    p: float
    ceiling: int
    breach: bool
    rho_floor: Optional[float] = None
    rate_a: Optional[float] = None
    material: Optional[bool] = None

    def as_dict(self) -> Dict[str, Any]:
        d = {
            "k_B": self.k_b,
            "k_A": self.k_a,
            "E_B": self.e_b,
            "E_A": self.e_a,
            "alpha": self.alpha,
            "r": self.r,
            "p": self.p,
            "C": self.ceiling,
            "breach": self.breach,
        }
        if self.rho_floor is not None:
            d["rho_floor"] = self.rho_floor
        if self.rate_a is not None:
            d["rate_A"] = self.rate_a
        if self.material is not None:
            d["material"] = self.material
        return d


def _validate_nonneg_int(name: str, value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be int")
    if value < 0:
        raise ValueError(f"{name} must be >= 0")
    return value


def _validate_positive_float(name: str, value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be numeric")
    v = float(value)
    if not math.isfinite(v) or v <= 0:
        raise ValueError(f"{name} must be finite and > 0")
    return v


def _validate_alpha(alpha: Any) -> float:
    a = _validate_positive_float("alpha", alpha)
    if not (0.0 < a < 1.0):
        raise ValueError("alpha must be in (0,1)")
    return a


def binom_pmf(n: int, k: int, p: float) -> float:
    if k < 0 or k > n:
        return 0.0
    if p == 0.0:
        return 1.0 if k == 0 else 0.0
    if p == 1.0:
        return 1.0 if k == n else 0.0
    return math.comb(n, k) * (p ** k) * ((1.0 - p) ** (n - k))


def binom_sf(n: int, k: int, p: float) -> float:
    """P(X >= k), X~Binomial(n,p)."""
    if k <= 0:
        return 1.0
    if k > n:
        return 0.0
    # sum smaller tail
    upper = n - k
    lower = k - 1
    if upper < lower:
        # P(X >= k) = sum_{j=k}^{n} pmf
        s = 0.0
        for j in range(k, n + 1):
            s += binom_pmf(n, j, p)
        return s
    # P(X >= k) = 1 - P(X <= k-1)
    s = 0.0
    for j in range(0, k):
        s += binom_pmf(n, j, p)
    return 1.0 - s


def exposure_ratio(e_b: float, e_a: float) -> float:
    eb = _validate_positive_float("E_B", e_b)
    ea = _validate_positive_float("E_A", e_a)
    return ea / eb


def conditional_p(r: float) -> float:
    r = _validate_positive_float("r", r)
    return r / (1.0 + r)


def cluster_ceiling(k_b: Any, r: Any, alpha: Any) -> int:
    """Exact conditional ceiling C.

    C = max{ c >= 0 : P(Binomial(k_B + c, p) >= c) > alpha }.
    """
    kb = _validate_nonneg_int("k_B", k_b)
    a = _validate_alpha(alpha)
    p = conditional_p(r)

    # Search upward until tail probability is <= alpha and cannot rise in a
    # way that matters? For Binomial(k+c,p) the tail P(X>=c) is monotone enough
    # for practical small counts, but we do a safe search: compute while prob > alpha
    # or until a conservative upper bound. For this use case k_b small.
    c = 0
    last_ok = 0
    # hard cap: impossible to need more than k_b + large margin; use safe bound.
    # P(Binomial(n, p) >= c) <= E[X choose?]. Use Chernoff-like stop: if c > n it's 0.
    # n = k_b + c => condition c <= k_b+c always true; tail becomes small as c grows.
    # We scan c from 0 upward until c > k_b + 20000? No, too big. Instead stop when
    # c > k_b + 10*ceil(-ln(alpha)/min(p,1-p)+1) and also prob very small. Better:
    # iterate c upward; track max c with prob>alpha. Once c > n? no. Use bound:
    # for c >= 1, P(Binomial(k_b+c,p)>=c) decreases eventually; but to be exact, scan
    # until n=k_b+c makes c > n impossible? never. So scan until prob <= alpha and c>k_b
    # and we have passed region where it can return above alpha only extremely rarely.
    # For exactness with small alpha/p, compute by increasing c while c <= k_b + 1000 or
    # until prob <= alpha for a sustained run. Simpler and safe: find first c_after where
    # for all c'>=c_after prob<=alpha by checking up to c_after + k_b + 64.
    limit = kb + 5000
    ok = -1
    prob_leq_streak = 0
    for cc in range(0, limit + 1):
        n = kb + cc
        prob = binom_sf(n, cc, p)
        if prob > a:
            ok = cc
            prob_leq_streak = 0
        else:
            prob_leq_streak += 1
            # once well below alpha and cc sufficiently beyond kb, tail won't come back above
            # for this binomial conditional form in practical ranges; verify with extra guard.
            if prob_leq_streak > max(64, kb + 16) and cc > kb:
                break
    if ok < 0:
        return 0
    # verify no larger c within extended bound has prob>alpha
    extended = max(limit, ok + kb + 512)
    for cc in range(ok + 1, extended + 1):
        n = kb + cc
        prob = binom_sf(n, cc, p)
        if prob > a:
            ok = cc
    return ok


def ceiling_breach(k_b: Any, k_a: Any, e_b: Any, e_a: Any, alpha: Any,
                   rho_floor: Optional[Any] = None) -> CeilingResult:
    kb = _validate_nonneg_int("k_B", k_b)
    ka = _validate_nonneg_int("k_A", k_a)
    eb = _validate_positive_float("E_B", e_b)
    ea = _validate_positive_float("E_A", e_a)
    a = _validate_alpha(alpha)
    r = ea / eb
    p = r / (1.0 + r)
    c = cluster_ceiling(kb, r, a)
    breach = ka > c
    rate_a = None
    material = None
    rf = None
    if rho_floor is not None:
        rf = _validate_positive_float("rho_floor", rho_floor)
        rate_a = ka / ea
        material = rate_a > rf
        breach = breach and material
    return CeilingResult(kb, ka, eb, ea, a, r, p, c, breach, rf, rate_a, material)


def zero_baseline_min_exposure(alpha: Any, rho_floor: Any) -> float:
    a = _validate_alpha(alpha)
    rf = _validate_positive_float("rho_floor", rho_floor)
    return -math.log(a) / rf


# ---- cluster counting ----

def cluster_key_for_event(event: Dict[str, Any]) -> Tuple[str, ...]:
    """Cluster key per SCAN-020 §5(a)/§2: type+date; gap: type+date+hour."""
    if not isinstance(event, dict):
        raise TypeError("event must be dict")
    atype = event.get("anomaly_type")
    session_date = event.get("session_date")
    if not isinstance(atype, str) or not atype:
        raise ValueError("event missing anomaly_type")
    if not isinstance(session_date, str) or not session_date:
        raise ValueError("event missing session_date")
    if atype == "intra_session_gap":
        event_ts = event.get("event_ts")
        if not isinstance(event_ts, str) or len(event_ts) < 13:
            raise ValueError("intra_session_gap event missing event_ts hour")
        hour = event_ts[:13]  # YYYY-MM-DDTHH
        return (atype, session_date, hour)
    return (atype, session_date)


def count_clusters(events: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Count clusters over a batch's events.

    Returns total event count, cluster count, per-type counts, and cluster details.
    """
    clusters: Dict[Tuple[str, ...], List[Dict[str, Any]]] = {}
    for e in events:
        k = cluster_key_for_event(e)
        clusters.setdefault(k, []).append(e)

    by_type: Dict[str, Dict[str, Any]] = {}
    for k, members in clusters.items():
        atype = k[0]
        info = by_type.setdefault(atype, {"events": 0, "clusters": 0, "cluster_sizes": []})
        info["events"] += len(members)
        info["clusters"] += 1
        info["cluster_sizes"].append(len(members))

    # stable summary
    per_type = {}
    for atype in sorted(by_type):
        info = by_type[atype]
        per_type[atype] = {
            "events": info["events"],
            "clusters": info["clusters"],
            "events_per_cluster": (info["events"] / info["clusters"]) if info["clusters"] else None,
        }
    return {
        "events": len(events),
        "clusters": len(clusters),
        "per_type": per_type,
    }
