# SCAN-022 Calendar Fixtures v2 (Step 1 gate)

## Inputs
- calendar_v1: `config/calendars/session_anomalies.calendar.v1.json` (unchanged)
- calendar_v2: `config/calendars/session_anomalies.calendar.v2.json` (new; copy of v1 rules/content with v2 metadata; sha256 recorded below)
- calendar_v2_sha256: `d958a74296302612066a160d259de26bb6b8cbb29138594aad10c542eaffcea4`
- attribution code: `scanline/calendar_attribution.py` `CAL_ATTR_VERSION=scan022-calendar-v1`, `ATTRIBUTABLE_ANOMALY_TYPES={missing_session, stub_session}`; intra_session_gap and sunday_anomaly clusters are never calendar-attributed.
- fixture evaluation: same rules' dates, years 1993-2026, same symbol universe/params as SCAN-021; cluster/event scan over rule-occurrence dates ±1 day per symbol H1 corpus, then clusters on scanned rule-occurrence dates evaluated.

## Gate (SCAN-021 fixture evaluation rerun)
- rule_occurrence_dates: 214
- clusters_on_scanned_dates: 92
- matches_on_scanned_dates: 20
- should-attribute definition: holiday-rule closure/early-close effect on missing_session/stub_session clusters with in-scope symbol/date match
- TP: 14  FP: 0  FN: 0
- precision (holiday-rule, should-attribute): 1.0
- recall (holiday-rule, should-attribute): 1.0
- Juneteenth 2026 missing_session 2026-06-19 attributed: True
- Juneteenth 2026 stub_session 2026-06-19 attributed: True
- control days (10th weekday of each month, 2021-2026, calendar weekdays; EURUSD in-scope check applied): 72
- control false attributions: 0

## Gate result
PASS. precision >= 0.90, recall = 1.0, Juneteenth 2026 missing/stub attributed, control false attributions = 0. Freeze may proceed after Step 2 checkpoint release.

## Notes
- v1 reported 71 control days; same mechanical definition yields 72 (6 years × 12 months). No control false attributions under either count.
- v1 false positives removed by construction: intra_session_gap and sunday_anomaly excluded from attribution.
