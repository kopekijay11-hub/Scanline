"""Level-proximity predicate (band-crossing) for Scanline module 1.

Pure function: given a symbol's D1 bars, its emission-timeframe bars, and the
parsed param file, returns the list of emitted events in pinned order.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

INTERVALS = {
    "M1": timedelta(minutes=1),
    "M5": timedelta(minutes=5),
    "M15": timedelta(minutes=15),
    "M30": timedelta(minutes=30),
    "H1": timedelta(hours=1),
    "H4": timedelta(hours=4),
    "D1": timedelta(days=1),
}


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


def _close_time(bar: Dict[str, Any]) -> datetime:
    tf = bar["timeframe"]
    if tf not in INTERVALS:
        raise ValueError(f"unknown timeframe {tf}")
    return _parse_ts(bar["open_ts"]) + INTERVALS[tf]


def _validate_params(params: Dict[str, Any]) -> Tuple[float, int, str, str, Dict[str, Any], str]:
    bands = params.get("proximity_bands_atr")
    if not (isinstance(bands, list) and len(bands) == 1):
        raise ValueError("proximity_bands_atr must hold exactly one band value")
    band = bands[0]
    if isinstance(band, bool) or not isinstance(band, (int, float)):
        raise ValueError("proximity_bands_atr value must be numeric")
    if params.get("atr_excludes_emission_bar") is not True:
        raise ValueError("atr_excludes_emission_bar must be true")
    if params.get("crossing_semantics") != "close_distance_band_entry":
        raise ValueError("crossing_semantics must be 'close_distance_band_entry'")
    if params.get("band_edge") != "inclusive":
        raise ValueError("band_edge must be 'inclusive'")
    if params.get("gap_through") != "fires_if_landing_inside":
        raise ValueError("gap_through must be 'fires_if_landing_inside'")
    if params.get("state_key") != "level_type+level_price+defined_at":
        raise ValueError("state_key must be 'level_type+level_price+defined_at'")
    if params.get("gap_semantics") != "array_previous":
        raise ValueError("gap_semantics must be 'array_previous'")
    atr_window = params["atr_window"]
    if isinstance(atr_window, bool) or not isinstance(atr_window, int) or atr_window <= 0:
        raise ValueError("atr_window must be a positive integer")
    atr_basis = params["atr_basis"]
    frozen_at = params["frozen_at"]
    param_version = params["param_version"]
    grid_steps = params.get("grid_steps", {}) or {}
    return float(band), int(atr_window), str(atr_basis), str(frozen_at), grid_steps, str(param_version)


class _Level:
    __slots__ = ("level_type", "price", "defined_at")

    def __init__(self, level_type: str, price: Any, defined_at: str):
        self.level_type = level_type
        self.price = price
        self.defined_at = defined_at

    @property
    def identity(self) -> Tuple[str, Any, str]:
        return (self.level_type, self.price, self.defined_at)


def _true_range(bars: List[Dict[str, Any]], i: int) -> Optional[float]:
    if i == 0:
        return None
    prev_close = bars[i - 1]["close"]
    h = bars[i]["high"]
    l = bars[i]["low"]
    return max(h - l, abs(h - prev_close), abs(l - prev_close))


def _active_d1_bar(d1_bars: List[Dict[str, Any]], t_close: datetime) -> Optional[Dict[str, Any]]:
    best = None
    best_close = None
    for b in d1_bars:
        bc = _close_time(b)
        if bc <= t_close:
            if best_close is None or bc > best_close:
                best = b
                best_close = bc
    return best


def _structural_levels(d1_bar: Dict[str, Any]) -> List[_Level]:
    ct = _close_time(d1_bar)
    defined_at = _fmt_ts(ct)
    return [
        _Level("d1_prior_high", d1_bar["high"], defined_at),
        _Level("d1_prior_low", d1_bar["low"], defined_at),
        _Level("d1_session_structure", d1_bar["close"], defined_at),
    ]


def _grid_levels(symbol: str, grid_steps: Dict[str, Any], all_prices: List[float], frozen_at: str) -> List[_Level]:
    step = grid_steps.get(symbol)
    if step is None:
        return []
    step = float(step)
    if step <= 0:
        return []
    if not all_prices:
        return []
    lo = min(all_prices)
    hi = max(all_prices)
    margin = 5.0 * step
    start = int((lo - margin) // step) * step
    # adjust float
    levels = []
    # use integer iteration count
    n_steps = int((hi + margin - start) // step) + 2
    seen = set()
    for k in range(n_steps + 1):
        price = start + k * step
        # round to avoid float drift
        if isinstance(grid_steps.get(symbol), int) and float(grid_steps.get(symbol)).is_integer():
            price = int(round(price))
        else:
            price = round(price, 10)
        key = price
        if key in seen:
            continue
        seen.add(key)
        levels.append(_Level("grid_round", price, frozen_at))
    return levels


def compute_events(d1_bars: List[Dict[str, Any]], emission_bars: List[Dict[str, Any]], params: Dict[str, Any]) -> List[Dict[str, Any]]:
    band, atr_window, atr_basis, frozen_at, grid_steps, param_version = _validate_params(params)

    d1_sorted = sorted(list(d1_bars), key=lambda b: _parse_ts(b["open_ts"]))
    em_sorted = sorted(list(emission_bars), key=lambda b: _parse_ts(b["open_ts"]))

    if not em_sorted:
        return []

    symbol = em_sorted[0].get("symbol")
    if symbol is None and d1_sorted:
        symbol = d1_sorted[0].get("symbol")
    timeframe = em_sorted[0].get("timeframe")

    # all prices for grid range
    all_prices = []
    for b in d1_sorted + em_sorted:
        for key in ("high", "low", "close", "open"):
            v = b.get(key)
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                all_prices.append(float(v))

    grid_levels = _grid_levels(symbol, grid_steps, all_prices, frozen_at)

    # true ranges for emission bars
    trs: List[Optional[float]] = [_true_range(em_sorted, i) for i in range(len(em_sorted))]

    state: Dict[Tuple, float] = {}
    events: List[Dict[str, Any]] = []

    for i, bar in enumerate(em_sorted):
        t_close = _close_time(bar)
        # atr: need atr_window preceding bars with true ranges
        start_idx = i - atr_window
        if start_idx < 0:
            # not enough preceding bars
            continue
        preceding = trs[start_idx:i]
        if any(tr is None for tr in preceding) or len(preceding) < atr_window:
            continue
        atr = sum(preceding) / float(atr_window)
        if atr == 0:
            continue

        # active D1
        d1_bar = _active_d1_bar(d1_sorted, t_close)
        if d1_bar is None:
            # no structural levels; but grid levels still active? Pseudocode: if no D1 closed, continue
            continue

        active_levels = _structural_levels(d1_bar) + list(grid_levels)
        active_ids = {lvl.identity for lvl in active_levels}

        close_price = bar["close"]
        for level in active_levels:
            d = abs(close_price - level.price) / atr
            prev = state.get(level.identity)
            if prev is not None and prev > band and d <= band:
                events.append({
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "level_type": level.level_type,
                    "level_price": level.price,
                    "defined_at": level.defined_at,
                    "distance_atr": d,
                    "atr_window": params["atr_window"],
                    "atr_basis": params["atr_basis"],
                    "param_version": params["param_version"],
                    "event_ts": _fmt_ts(t_close),
                })
            state[level.identity] = d

        # drop inactive
        state = {k: v for k, v in state.items() if k in active_ids}

    events.sort(key=lambda e: (e["event_ts"], e["level_type"], e["level_price"], e["defined_at"]))
    return events
