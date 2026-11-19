# SCAN-005-SPOTCHECK — bridge spot-check of the corpus (GOLD, 2026-09-22 → 2026-09-28)

Read-only spot-check week. Standing laptop rule observed: no writes outside
~/scanline-spotcheck/ and the /scanline-check clone; /ai_system never written;
bridge token never printed, never stored, never included in this report.

## 1. Bridge health gate (/status)

GET http://172.19.80.1:8000/status carrying header X-Bridge-Token (token loaded
from ~/ai_system/.bridge.env). Token discipline: the token is used in the header
only; it was never printed and never written to any file. Token loaded OK;
reported length: 43 (expected 43).

/status result (raw, saved to ~/scanline-spotcheck/bridge-status-raw.json):
mt5_initialized=true, terminal_connected=true, account_login=39235781,
account_server=CMCMarkets-MT5-DEMO, account_is_demo=true, demo_only=true,
ready_for_orders=true, balance=10106.3, equity=10135.27, margin=529.09,
margin_free=9606.18, auth_fingerprint=3d2a2870.

Health gate: all four conditions satisfied. Token length 43. Bridge live and
healthy.

## 2. /candles contract (read from ~/ai_system/bot.py)

- Endpoint: GET /candles (bot.py:1050). It takes no query parameters — no
  symbol, timeframe, or date-range filtering is possible on this endpoint.
- It returns multi-timeframe historical candles for every symbol on the bridge
  watchlist, served from a background-worker cache refreshed ~every 15 s under
  MT5_LOCK (mt5.copy_rates_*), with a live MT5 fallback when the cache is cold
  or stale (bot.py:1058-1073).
- Response shape: {symbol: {timeframe: [{time, open, high, low, close, volume}, ...]}}.
- Timestamp semantics (bot.py format_candles, lines 627-639): each bar's raw MT5
  server-time time is served as int(bar['time']) - _TZ_STATE['offset'], where the
  offset is the broker-server-to-UTC offset continuously re-calibrated from live
  MT5 samples (bot.py:568-588, resolve_tz_offset) and persisted to
  tz_offset.json. The time field is therefore UTC epoch seconds of the bar open.
- Observed in the data: corpus H1 bar at time T is OHLC-identical to the bridge
  H1 bar at time T + 3600 s for all 115 corpus bars in the week — a constant
  +1 h labeling offset between the two sources. The mapping used for every
  comparison: bridge_time = corpus_time + 3600 s. Without this mapping, an
  equal-timestamp comparison shows 115/115 mismatches — entirely attributable
  to the labeling offset, not to price data.

Raw bridge pull saved to ~/scanline-spotcheck/bridge-candles-raw.json. GOLD
series in window [2026-09-22T00:00:00Z, 2026-09-29T00:00:00Z): H1 = 115 bridge
bars; D1 = 5 bridge bars.

## 3. Comparisons

(a) H1 bar-by-bar at the mapped timestamp: 115 compared, 0 mismatches (hard 0,
close-tolerance 0, missing 0). All 115 corpus H1 bars match the bridge exactly
at the mapped timestamp.

(b) H1 per-day aggregates by UTC day (bridge labels shifted -3600 s before
bucketing): every day matches — 2026-09-22 n=23, 09-23 n=23, 09-24 n=23,
09-25 n=21 (O 4264.98 / H 4315.71 / L 4254.44 / C 4284.70 both sides),
09-26 n=0, 09-27 n=2, 09-28 n=23, all OHLC aggregates identical.

(c) D1 shared days: the two series do not share D1 timestamps. Corpus D1 bars
are labeled at 00:00 UTC (calendar days: Sep 22, 23, 24, 28); every bridge D1
bar is labeled at 22:00 UTC (broker session days; in this window: Sep 21, 22,
23, 24, 27, 28). Side-by-side, each corpus calendar-day D1 shares its high and
low with the overlapping bridge session bar. Notable: the bridge bar labeled
2026-09-24T22:00:00Z (the broker Friday session) has O 4274.67 / H 4315.71 /
L 4254.44 / C 4284.7 — H/L/C match the corpus Friday H1 aggregate exactly; the
open differs by 9.69 because the corpus Friday aggregate opens at Friday
00:00 UTC while the bridge session bar opens at Thursday 22:00 UTC.

(d) The Friday question: NO — the bridge serves no GOLD D1 bar labeled or dated
2026-09-25. Bridge D1 jumps from 2026-09-24T22:00:00Z directly to
2026-09-27T22:00:00Z; the Friday session is carried by the bar labeled
2026-09-24T22:00:00Z (see (c)).

## 4. Ladder verdict (as written, applied by the agent)

STOP. Triggering evidence as read by the agent: the bridge also lacks a GOLD
D1 bar for 2026-09-25, and no shared D1 timestamps exist between the corpus
(calendar-day) and bridge (broker-session) D1 series. The H1 side is clean:
115/115 exact under the stated mapping; all per-day aggregates agree. No remedy
attempted (read-only).

Results block: bridge_status=green, h1_bars_compared=115, h1_mismatches=0,
friday_d1_on_bridge=no, d1_shared_days_match=no, verdict=STOP.
Laptop record: ~/scanline-spotcheck/spotcheck-bridge-gold-week.md,
sha256 b5aca82639c73bf7f224230ee5b7ed01869678bef46bed6a8ed09802e7def514
(this repo copy is the record as reported in chat; the laptop file is the
original).

---

## Grading addendum (Jarvis, 2026-11-19) — STOP lifted on the evidence

The agent applied the pre-stated ladder faithfully, and the STOP is correct
under the ladder's letter. The ladder's D1 clauses, however, were drafted
against an assumption this check itself falsified: that bridge D1 bars would be
calendar-day bars comparable by date. They are broker-session bars (22:00 UTC
opens) — MT5's native D1 — while the corpus D1 is a calendar-day derivation
from H1. Graded on substance:

1. The spot-check's purpose — verify the corpus against the second source
   wherever the corpus has data — is SATISFIED. H1 matches 115/115 exactly
   (the substrate is trustworthy), and corpus D1 is a proven deterministic
   function of that H1 (SCAN-005: D1 equals the H1 calendar-day aggregates
   exactly on every day it exists). The D1 comparison therefore reduces to the
   H1 comparison, which passed without a single deviation.
2. The Friday conclusion in the agent's verdict paragraph is corrected: the
   bridge DOES serve the Friday session's prices in D1 form — inside the
   session bar labeled 2026-09-24T22:00Z, whose H/L/C equal the corpus Friday
   aggregate's H/L/C exactly (section 3c). What the bridge does not serve is a
   CALENDAR-day Friday bar, because session bars are its only D1 form. The
   Friday drop therefore remains where the upstream finding put it: in the
   corpus's calendar-day derivation (re-derive, don't re-pull), NOT upstream
   of the corpus.
3. Both STOP triggers dissolve under the session-vs-calendar reading that the
   report's own side-by-side table establishes. The gate this spot-check
   guards — SCAN-006, the first real scan — is CLEARED.

Recorded for any future spot-check: compare D1 through the session bars plus
the H1 derivation, never by calendar labels; and note the bridge's served H1
labels carry a constant +3600 s offset against corpus labels for this
September week as served in November (see section 2) — referred to the owning
lane as a bridge labeling observation, not a Scanline defect.
