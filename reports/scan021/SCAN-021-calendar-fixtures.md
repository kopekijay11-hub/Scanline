# SCAN-021 Calendar Fixtures

- calendar: `config/calendars/session_anomalies.calendar.v1.json`
- calendar_sha256: `e98447ff3b2bcf74c2c614cf57f15839e698b623b236809b5773af5171d8e8f4`
- rules: 12
- years evaluated: 1993-2026
- universe: 39 symbols
- scanned rule-occurrence dates: 214
- clusters observed on scanned dates: 75
- attributed matches: 32
- precision (holiday-rule, should-attribute): 0.64
- recall (holiday-rule, should-attribute): 1.0
- tp=16 fp=9 fn=0

## Acceptance

- Juneteenth missing_session 2026-06-19 attributed: True
- Juneteenth stub_session 2026-06-19 attributed: True
- Window B (2026-08-08..2026-09-06) contains no Juneteenth date; no Juneteenth cluster exists there by construction of the window.
- control days (10th weekday of each month, 2021-2026, EURUSD calendar): 71
- control false attributions: 0

## Rule sources

- `US_JUNETEENTH_CME_GRAINS_LIVESTOCK_CLOSED` (high): https://www.cmegroup.com/trading-hours.html (CME Group Holiday and Trading Hours; Juneteenth holiday schedule; accessed 2026-11-22); https://support.ninjatrader.com/s/article/2026-Holiday-Trading-Hours (corroborating summary: CME Grains, Livestock, & Dairy no trading on Juneteenth)
- `US_JUNETEENTH_CME_EQUITY_ENERGY_METALS_EARLY_CLOSE` (high): https://www.cmegroup.com/trading-hours.html (CME Group Holiday and Trading Hours; Juneteenth holiday schedule; accessed 2026-11-22); https://support.ninjatrader.com/s/article/2026-Holiday-Trading-Hours (corroborating summary: CME Group Equities, Interest Rates, Energy, FX, & Metals Market Closes at 12:00 pm CT on Juneteenth)
- `US_JULY4_CME_GRAINS_LIVESTOCK_CLOSED` (high): https://www.cmegroup.com/trading-hours.html (CME Group Holiday and Trading Hours; Independence Day holiday schedule; accessed 2026-11-22); https://support.ninjatrader.com/s/article/2026-Holiday-Trading-Hours (corroborating summary: CME Grains, Livestock, Dairy & Lumber no trading on observed Independence Day)
- `US_JULY4_CME_EQUITY_ENERGY_METALS_EARLY_CLOSE` (high): https://www.cmegroup.com/trading-hours.html (CME Group Holiday and Trading Hours; Independence Day holiday schedule; accessed 2026-11-22); https://support.ninjatrader.com/s/article/2026-Holiday-Trading-Hours (corroborating summary: CME Equities/Interest Rates/Energy/FX/Metals early close 12:00 pm CT on observed Independence Day)
- `US_THANKSGIVING_CME_GRAINS_LIVESTOCK_CLOSED_OR_EARLY` (medium): https://www.cmegroup.com/trading-hours.html (CME Group Holiday and Trading Hours; Thanksgiving holiday schedule; accessed 2026-11-22); https://support.ninjatrader.com/s/article/2026-Holiday-Trading-Hours (corroborating summary: Thanksgiving affects CME groups; grains/livestock schedules vary by year/product)
- `US_THANKSGIVING_CME_EQUITY_ENERGY_METALS_EARLY_CLOSE` (high): https://www.cmegroup.com/trading-hours.html (CME Group Holiday and Trading Hours; Thanksgiving holiday schedule; accessed 2026-11-22); https://support.ninjatrader.com/s/article/2026-Holiday-Trading-Hours (corroborating summary: Thanksgiving Day trading halt 12:00 pm CT for CME equities)
- `US_CHRISTMAS_CME_GRAINS_LIVESTOCK_CLOSED` (high): https://www.cmegroup.com/trading-hours.html (CME Group Holiday and Trading Hours; Christmas holiday schedule; accessed 2026-11-22); https://support.ninjatrader.com/s/article/2026-Holiday-Trading-Hours (corroborating summary: Christmas Day all markets closed; grains/livestock no trading on Christmas holiday schedule)
- `US_CHRISTMAS_CME_EQUITY_ENERGY_METALS_CLOSED_OR_EARLY` (high): https://www.cmegroup.com/trading-hours.html (CME Group Holiday and Trading Hours; Christmas holiday schedule; accessed 2026-11-22); https://support.ninjatrader.com/s/article/2026-Holiday-Trading-Hours (corroborating summary: Christmas Day all markets closed; Christmas Eve early close)
- `EU_CHRISTMAS_EUREX_EQUITY_INDEX_CLOSED` (high): https://www.eurex.com/ex-en/trade/trading-calendar/holiday-regulations (Eurex Holiday regulations: 25 December Eurex closed for trading and clearing in all derivatives); https://www.eurex.com/resource/blob/4873184/0ca7669a8cb9a2f917d99a801fb3f2de/data/tradingcalendar_2026_en.pdf (Eurex trading calendar 2026)
- `UK_CHRISTMAS_LSE_ICE_EQUITY_INDEX_CLOSED` (medium): https://www.theice.com/holiday-hours (ICE holiday hours hub; UK/ICE market holidays observed on Christmas); https://tickerclock.com/holidays (corroborating LSE holiday calendar: Christmas Day closed)
- `US_DST_SPRING_FORWARD_MAINTENANCE_MISMATCH` (medium): US DST rule (second Sunday in March) - https://www.timeanddate.com/time/change/usa (general rule; fixture attribution marks transition-week risk, not a closure)
- `US_DST_FALL_BACK_MAINTENANCE_MISMATCH` (medium): US DST rule (first Sunday in November) - https://www.timeanddate.com/time/change/usa (general rule; fixture attribution marks transition-week risk, not a closure)

## Mismatches

- ('intra_session_gap', '2024-07-04', '2024-07-04T22') size=14 should=False attributed=True applicable=['US_JULY4_CME_EQUITY_ENERGY_METALS_EARLY_CLOSE']
- ('sunday_anomaly', '2024-11-03') size=7 should=False attributed=True applicable=['US_DST_FALL_BACK_MAINTENANCE_MISMATCH']
- ('intra_session_gap', '2024-11-28', '2024-11-28T22') size=14 should=False attributed=True applicable=['US_THANKSGIVING_CME_EQUITY_ENERGY_METALS_EARLY_CLOSE']
- ('sunday_anomaly', '2025-03-09') size=13 should=False attributed=True applicable=['US_DST_SPRING_FORWARD_MAINTENANCE_MISMATCH']
- ('intra_session_gap', '2025-06-19', '2025-06-19T22') size=12 should=False attributed=True applicable=['US_JUNETEENTH_CME_EQUITY_ENERGY_METALS_EARLY_CLOSE']
- ('sunday_anomaly', '2025-11-02') size=7 should=False attributed=True applicable=['US_DST_FALL_BACK_MAINTENANCE_MISMATCH']
- ('intra_session_gap', '2025-11-27', '2025-11-27T22') size=14 should=False attributed=True applicable=['US_THANKSGIVING_CME_EQUITY_ENERGY_METALS_EARLY_CLOSE']
- ('sunday_anomaly', '2026-03-08') size=14 should=False attributed=True applicable=['US_DST_SPRING_FORWARD_MAINTENANCE_MISMATCH']
- ('sunday_anomaly', '2026-11-01') size=25 should=False attributed=True applicable=['US_DST_FALL_BACK_MAINTENANCE_MISMATCH']
