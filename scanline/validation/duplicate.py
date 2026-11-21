"""Duplicate bar-key integrity (SCAN-017F).

Single authoritative implementation of duplicate-bar rejection. Rejects repeated
``(symbol, timeframe, open_ts)`` keys at the input boundary, including identical
and conflicting OHLCV records. No silent deduplication.

Both modules enforce through this helper:

* ``scanline/sessions.py::_core_compute`` (session-anomaly path)
* ``scanline/levels.py::compute_events`` (level-proximity path)
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

_DEFAULT_TIMEFRAME = "H1"


class DuplicateBarKeyError(ValueError):
    """Raised when a repeated (symbol, timeframe, open_ts) bar key is encountered.

    Subclasses ``ValueError`` so existing ``except ValueError`` guards keep
    working, while allowing callers to catch duplicate errors specifically.
    """

    def __init__(
        self,
        message: str,
        *,
        symbol: str,
        timeframe: str,
        open_ts: str,
        epoch_seconds: int,
        first_index: int,
        duplicate_index: int,
        source: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.symbol = symbol
        self.timeframe = timeframe
        self.open_ts = open_ts
        self.epoch_seconds = epoch_seconds
        self.first_index = first_index
        self.duplicate_index = duplicate_index
        self.source = source


def _parse_ts(ts_str: str) -> datetime:
    """Canonical UTC parse, matching existing convention in sessions/levels/scan."""
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


def _epoch_seconds(dt: datetime) -> int:
    return int(dt.timestamp())


def _canonical_symbol(value: Any, index: int) -> str:
    if value is None:
        raise ValueError(f"bar at input index {index} is missing 'symbol'")
    sym = str(value).strip().upper()
    if not sym:
        raise ValueError(f"bar at input index {index} has an empty 'symbol'")
    return sym


def _canonical_timeframe(value: Any, index: int, default: Optional[str]) -> str:
    if value is None:
        if default is None:
            raise ValueError(f"bar at input index {index} is missing 'timeframe'")
        value = default
    tf = str(value).strip().upper()
    if not tf:
        raise ValueError(f"bar at input index {index} has an empty 'timeframe'")
    return tf


def validate_unique_bar_keys(
    bars: Any,
    symbol: Optional[str] = None,
    timeframe: Optional[str] = None,
    source: Optional[str] = None,
) -> None:
    """Reject repeated ``(symbol, timeframe, open_ts)`` bar keys.

    Parameters
    ----------
    bars:
        Iterable of bar dicts. Each bar may carry ``symbol``, ``timeframe`` and
        ``open_ts``; bars missing ``symbol``/``timeframe`` fall back to the
        contextual ``symbol``/``timeframe`` arguments (timeframe defaults to
        ``"H1"``).
    symbol:
        Contextual default symbol applied to bars missing ``symbol``.
    timeframe:
        Contextual default timeframe applied to bars missing ``timeframe``
        (defaults to ``"H1"`` when absent and no argument is given).
    source:
        Optional identifier used only in error messages (e.g. a file path).

    Raises
    ------
    DuplicateBarKeyError
        On the first repeated key (left-to-right pass; the second occurrence is
        reported). Message names the key and both occurrence positions; no OHLCV
        values are included.
    ValueError
        For missing bar metadata or an unparseable ``open_ts``.

    Empty input short-circuits: no check is performed.
    """
    if bars is None:
        return

    default_timeframe = timeframe if timeframe is not None else _DEFAULT_TIMEFRAME
    seen: Dict[Tuple[str, str, datetime], int] = {}

    for index, bar in enumerate(bars):
        if not isinstance(bar, dict):
            raise ValueError(f"bar at input index {index} is not a mapping")

        sym = _canonical_symbol(bar.get("symbol") or symbol, index)
        tf = _canonical_timeframe(bar.get("timeframe"), index, default_timeframe)

        try:
            ts_raw = bar["open_ts"]
        except KeyError:
            raise ValueError(f"bar at input index {index} is missing 'open_ts'")
        try:
            dt = _parse_ts(ts_raw)
        except Exception as exc:
            raise ValueError(
                f"bar at input index {index} has an unparseable 'open_ts': {ts_raw!r}"
            ) from exc

        key = (sym, tf, dt)
        if key in seen:
            first_index = seen[key]
            message = _duplicate_message(
                sym, tf, dt, first_index, index, source
            )
            raise DuplicateBarKeyError(
                message,
                symbol=sym,
                timeframe=tf,
                open_ts=_fmt_ts(dt),
                epoch_seconds=_epoch_seconds(dt),
                first_index=first_index,
                duplicate_index=index,
                source=source,
            )
        seen[key] = index

    return None


def _duplicate_message(
    sym: str, tf: str, dt: datetime, first_index: int, dup_index: int, source: Optional[str]
) -> str:
    iso = _fmt_ts(dt)
    epoch = _epoch_seconds(dt)
    parts = [
        f"duplicate bar key: symbol={sym}, timeframe={tf}, open_ts={iso} (epoch {epoch})",
        f"first occurrence at input index {first_index}",
        f"duplicate at input index {dup_index}",
    ]
    if source:
        parts.append(f"(source: {source})")
    return "; ".join(parts)
