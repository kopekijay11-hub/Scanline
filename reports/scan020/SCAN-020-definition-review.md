# SCAN-020 — session_anomalies Definition Review

**Status:** analysis only. No detector code changes, no freeze, no scan. Ledger not touched; SCAN-019 verdicts (missing BREACHED, stub BREACHED) are NOT re-graded by this job. Any re-judgment below is labeled as such and lives only in this review.

## Precision block / environment proof

- First report line inputs (captured before work): `pwd` = `/home/joshua/scanline`; `git rev-parse --show-toplevel` = `/home/joshua/scanline`.
- Inputs of record: batch `records/scans/20261123T021148750070Z_72046b8e81b86046bcef1aa65486ee26` (326 events; window A 2026-05-26 → 2026-06-24); exploratory window B 2026-08-08 → 2026-09-06 as recorded in `docs/freezes/session_anomalies-1.0.0.md`; calibration evidence `reports/scan019/SCAN-019-step1a-calibration.md`.
- Housekeeping (config only): `git remote remove researchline` executed; `git remote -v` after removal shows only `origin git@github.com:kopekijay11-hub/scanline.git (fetch/push)`.
- Protected-set hashes captured before mutation at `/tmp/scan020_protected_before.txt` (15 files: 3 level_proximity scan dirs, session_anomalies batch dir, `records/ledger/scan-ledger.jsonl`).

## Section 0 — Template provenance and sensitivity refit

### 0.1 Provenance (which data fit each symbol template)

Per `reports/scan019/SCAN-019-step1a-calibration.md` and `docs/freezes/session_anomalies-1.0.0.md`: templates were calibrated from **each symbol’s full H1 history** in the corpus (`/home/joshua/corpus-store/*_H1.csv`), not from window A or B alone. The calibration report states "Reference span: each symbol’s full H1 history..." and "Values are from full-history H1 analysis unless noted"; the freeze record repeats "Template calibration (Step 1a), full-history reference". The calibration window named in Resolution 1 (2026-05-26 → 2026-06-24) is a **coverage/confirmatory window context**, not the template-fit span; the report explicitly applies full-history modal/percentile rules.

Per-symbol fit span is therefore "full available H1 history in corpus snapshot at calibration time" (symbol-specific first..last dates are recorded in the calibration table; e.g. AUDCAD 1993-04-26..2026-11-21, FEEDBEEF 2025-09-02..2026-11-21). No symbol was fit on A/B only; all used full history, which **includes** A and B.

### 0.2 Sensitivity refit (exploratory, /tmp, no publication)

Method: refit every symbol template on H1 history **excluding windows A and B** (excluded UTC calendar days 2026-05-26..2026-06-24 and 2026-08-08..2026-09-06). Same mechanical rules as calibration report: UTC-day grouping; `expected_bars`=modal Mon–Fri count (tie -> smaller mode); `expected_sun_bars`=modal Sunday count or 0; `stub_tolerance`=`wd_p95_dev`; `sun_tolerance`=`sun_p95_dev`; maintenance=modal >=1.5h break start/end hour, fallback 20:00–22:00 when absent. Re-ran `scanline.sessions.compute_events` over windows A and B with refit templates. No files published; outputs in `/tmp/scan020_refit_out.json`.

Template diffs (refit vs frozen): **16 symbols changed**; 23 symbols identical. Changes were mostly `sun_tolerance` +/-1, `stub_tolerance` shifts (LSGOIL 2->1, NZDCAD 21->15), and maintenance/mode_sun becoming undetermined for FEEDBEEF/LEANHOGS/LIVEBEEF when A/B excluded (these symbols have short histories; removing A removed their only/primary Sunday observations in that span slice).

| Symbol | Frozen -> Refit diffs | Refit sample size (excl A,B) |
| --- | --- | --- |
| FEEDBEEF | mode_sun:0->None; maint_start:20->None; maint_end:22->None | 263 wd / 0 sun |
| GBPCAD | sun_tol:1->0 | 4949 wd / 976 sun |
| GBPUSD | sun_tol:1->0 | 5382 wd / 1063 sun |
| GER40 | sun_tol:0->1 | 1201 wd / 260 sun |
| HEATOIL | sun_tol:1->0 | 277 wd / 51 sun |
| JPN225 | sun_tol:0->1 | 1208 wd / 263 sun |
| LEANHOGS | mode_sun:0->None; maint_start:20->None; maint_end:22->None | 264 wd / 0 sun |
| LIVEBEEF | mode_sun:0->None; maint_start:20->None; maint_end:22->None | 263 wd / 0 sun |
| LSGOIL | stub_tol:2->1 | 275 wd / 51 sun |
| NZDCAD | stub_tol:21->15; sun_tol:0->1 | 1131 wd / 223 sun |
| NZDUSD | sun_tol:0->2 | 935 wd / 195 sun |
| UK100 | sun_tol:0->1 | 1209 wd / 245 sun |
| UKOIL | sun_tol:0->1 | 1202 wd / 263 sun |
| USDCAD | sun_tol:1->0 | 4253 wd / 843 sun |
| USDCHF | sun_tol:1->0 | 4253 wd / 842 sun |
| USDJPY | sun_tol:0->2 | 4766 wd / 967 sun |

Per-type counts, frozen vs refit:

| Window | Anomaly type | Frozen events | Refit events | Delta (refit-frozen) |
| --- | --- | --- | --- | --- |
| A | intra_session_gap | 288 | 288 | 0 |
| A | missing_session | 6 | 6 | 0 |
| A | stub_session | 4 | 4 | 0 |
| A | sunday_anomaly | 28 | 12 | -16 |
| B | intra_session_gap | 255 | 255 | 0 |
| B | missing_session | 1 | 1 | 0 |
| B | stub_session | 0 | 0 | 0 |
| B | sunday_anomaly | 21 | 9 | -12 |

Refit missing/stub events (A): same 6 missing_session on 2026-06-19 (CORN,FEEDBEEF,LEANHOGS,LIVEBEEF,SOYBEAN,WHEAT) and same 4 stub_session (FEEDBEEF 2026-06-04, HEATOIL/LSGOIL/US2000 2026-06-19). B refit: same 1 missing_session (UK100 2026-08-31), 0 stub_session.

**Plain statement on in-sample fit:** Window B's near-zero missing/stub counts are **not explained by in-sample fitting of A/B**. Excluding A and B from calibration leaves A and B missing/stub counts unchanged. The B near-zero baseline is a property of the data/window and the frozen template semantics (and, for stubs, wide tolerances/modes), not an artifact of fitting templates on B. Sunday_anomaly counts do move under refit (A 28->12, B 21->9) because several symbols' Sunday tolerances/modes change when A/B are excluded; Sunday sensitivity is real and should be treated as template-sensitive, but missing/stub are stable in this refit.

## Section 1 — The four stubs (window A)

Window A contains 4 `stub_session` events:

| Symbol | Date | expected_bars | observed_bars | shortfall |
| --- | --- | --- | --- | --- |
| FEEDBEEF | 2026-06-04 | 6 | 5 | 1 |
| HEATOIL | 2026-06-19 | 23 | 17 | 6 |
| LSGOIL | 2026-06-19 | 21 | 18 | 3 |
| US2000 | 2026-06-19 | 23 | 17 | 6 |

### Per-event classification (evidence-based)

1. **FEEDBEEF 2026-06-04 (Thu, expected 6, observed 5, shortfall 1)** — **Class: likely true short session / data truncation at day edge; not a half-day holiday in the Juneteenth sense.** Evidence: FEEDBEEF full-history same-weekday (Thu) distribution is overwhelmingly 6 bars (59 of 61 Thursdays observed). Observed bars on 2026-06-04 are 13:00Z-17:00Z (5 bars) vs normal 13:00Z-18:00Z pattern implied by 6-bar mode; missing the final hour. Neighbors: 2026-06-03=6, 2026-06-05=6. Not 2026-06-19. This reads as a one-bar short/truncated session; with stub_tolerance=0 (frozen) any shortfall fires. Classification confidence: medium (true short session in data; cause unknown).

2. **HEATOIL 2026-06-19 (Fri, expected 23, observed 17, shortfall 6)** — **Class: half-day/early-close consistent with Juneteenth holiday schedule.** Evidence: 2026-06-19 is Juneteenth (federal holiday; CME/NYMEX energy/metal products had early close 13:00 ET / 12:00 CT on 2026-06-19 per CME holiday schedules; NYMEX energy contracts closed early). Observed bars 00:00Z-16:00Z = 17 bars, ending 16:00Z (12:00 ET), matching an early-close pattern. Same-weekday history mostly 21 bars (55) with occasional 17/23; 2026-06-19 is a known holiday date. Labeled **hypothesis checked, not assumed**: calendar alignment is strong, but this is attribution by external schedule corroboration, not a detector-native calendar field.

3. **LSGOIL 2026-06-19 (Fri, expected 21, observed 18, shortfall 3)** — **Class: half-day/early-close consistent with Juneteenth/UK holiday-adjacent schedule; ambiguous venue attribution.** Evidence: 2026-06-19 is Juneteenth; ICE/LSE-related products have UK/US holiday interactions, but LSGOIL (ICE Gasoil/Low Sulphur Gasoil) follows ICE Europe hours. Observed 00:00Z-17:00Z = 18 bars vs expected 21. Same-weekday history mode 21 (57/63). The shortfall is directionally consistent with early close, but I cannot confirm ICE Gasoil specific 2026-06-19 hours from a primary ICE schedule in this session; **classification: likely early-close/holiday-affected, UNVERIFIABLE exact cause without ICE contract hours source**.

4. **US2000 2026-06-19 (Fri, expected 23, observed 17, shortfall 6)** — **Class: half-day/early-close consistent with Juneteenth.** Evidence: CME equity index futures (incl. Russell 2000/RTY complex; US2000 symbol in corpus) closed early 13:00 ET / 12:00 CT on 2026-06-19 2026 per CME holiday schedule. Observed 00:00Z-16:00Z = 17 bars, ending at 12:00 ET, matching early close. Same-weekday mode 21 (60) with 17 rare (2) — the 17-bar Friday aligns with holiday early close. **Hypothesis checked, not assumed**.

### Juneteenth cross-tab (2026-06-19)

- Stubs on 2026-06-19: **3 / 4** — HEATOIL, LSGOIL, US2000.
- FEEDBEEF 2026-06-04 is not on Juneteenth.
- Juneteenth hypothesis: **checked, not assumed**. External corroboration: CME Group holiday/trading hours pages list Juneteenth 2026-06-19 as early close 12:00 CT for equity index, interest rates, energy, FX, metals; grains/livestock closed (sources: CME Group holiday calendar, CME Juneteenth settlement notice, broker holiday notices). This matches missing_session for ag/livestock (CORN/FEEDBEEF/LEANHOGS/LIVEBEEF/SOYBEAN/WHEAT all 0 bars) and stub_session early closes for HEATOIL/US2000. LSGOIL is plausible but not directly confirmed by a primary ICE contract-hours citation obtained here.

## Section 2 — Cluster accounting (all types, A and B)

Cluster definition (as specified): same type + same date; for `intra_session_gap`, same type + same date + same hour. All downstream numbers in this review use both units.

| Window | Type | Events | Clusters | Events/cluster |
| --- | --- | --- | --- | --- |
| A | intra_session_gap | 288 | 18 | 16.00 |
| A | missing_session | 6 | 1 | 6.00 |
| A | stub_session | 4 | 2 | 2.00 |
| A | sunday_anomaly | 28 | 4 | 7.00 |
| B | intra_session_gap | 255 | 16 | 15.94 |
| B | missing_session | 1 | 1 | 1.00 |
| B | stub_session | 0 | 0 | n/a |
| B | sunday_anomaly | 21 | 3 | 7.00 |

Cluster detail (A):
- **intra_session_gap**: 288 events / 18 clusters.
  - `('intra_session_gap', '2026-05-26', '2026-05-26T22')`: n=16, symbols=['COPPER', 'GASOLINE', 'GER40', 'GOLD', 'HEATOIL', 'JPN225', 'NDAQ100', 'PALLADIUM', 'PLATINUM', 'SILVER', 'SPX500', 'UK100', 'US2000', 'US30', 'USNATGAS', 'USOIL']
  - `('intra_session_gap', '2026-05-27', '2026-05-27T22')`: n=16, symbols=['COPPER', 'GASOLINE', 'GER40', 'GOLD', 'HEATOIL', 'JPN225', 'NDAQ100', 'PALLADIUM', 'PLATINUM', 'SILVER', 'SPX500', 'UK100', 'US2000', 'US30', 'USNATGAS', 'USOIL']
  - `('intra_session_gap', '2026-05-28', '2026-05-28T22')`: n=16, symbols=['COPPER', 'GASOLINE', 'GER40', 'GOLD', 'HEATOIL', 'JPN225', 'NDAQ100', 'PALLADIUM', 'PLATINUM', 'SILVER', 'SPX500', 'UK100', 'US2000', 'US30', 'USNATGAS', 'USOIL']
  - `('intra_session_gap', '2026-06-01', '2026-06-01T22')`: n=16, symbols=['COPPER', 'GASOLINE', 'GER40', 'GOLD', 'HEATOIL', 'JPN225', 'NDAQ100', 'PALLADIUM', 'PLATINUM', 'SILVER', 'SPX500', 'UK100', 'US2000', 'US30', 'USNATGAS', 'USOIL']
  - `('intra_session_gap', '2026-06-02', '2026-06-02T22')`: n=16, symbols=['COPPER', 'GASOLINE', 'GER40', 'GOLD', 'HEATOIL', 'JPN225', 'NDAQ100', 'PALLADIUM', 'PLATINUM', 'SILVER', 'SPX500', 'UK100', 'US2000', 'US30', 'USNATGAS', 'USOIL']
  - `('intra_session_gap', '2026-06-03', '2026-06-03T22')`: n=16, symbols=['COPPER', 'GASOLINE', 'GER40', 'GOLD', 'HEATOIL', 'JPN225', 'NDAQ100', 'PALLADIUM', 'PLATINUM', 'SILVER', 'SPX500', 'UK100', 'US2000', 'US30', 'USNATGAS', 'USOIL']
  - `('intra_session_gap', '2026-06-04', '2026-06-04T22')`: n=16, symbols=['COPPER', 'GASOLINE', 'GER40', 'GOLD', 'HEATOIL', 'JPN225', 'NDAQ100', 'PALLADIUM', 'PLATINUM', 'SILVER', 'SPX500', 'UK100', 'US2000', 'US30', 'USNATGAS', 'USOIL']
  - `('intra_session_gap', '2026-06-08', '2026-06-08T22')`: n=16, symbols=['COPPER', 'GASOLINE', 'GER40', 'GOLD', 'HEATOIL', 'JPN225', 'NDAQ100', 'PALLADIUM', 'PLATINUM', 'SILVER', 'SPX500', 'UK100', 'US2000', 'US30', 'USNATGAS', 'USOIL']
  - `('intra_session_gap', '2026-06-09', '2026-06-09T22')`: n=16, symbols=['COPPER', 'GASOLINE', 'GER40', 'GOLD', 'HEATOIL', 'JPN225', 'NDAQ100', 'PALLADIUM', 'PLATINUM', 'SILVER', 'SPX500', 'UK100', 'US2000', 'US30', 'USNATGAS', 'USOIL']
  - `('intra_session_gap', '2026-06-10', '2026-06-10T22')`: n=16, symbols=['COPPER', 'GASOLINE', 'GER40', 'GOLD', 'HEATOIL', 'JPN225', 'NDAQ100', 'PALLADIUM', 'PLATINUM', 'SILVER', 'SPX500', 'UK100', 'US2000', 'US30', 'USNATGAS', 'USOIL']
  - `('intra_session_gap', '2026-06-11', '2026-06-11T22')`: n=16, symbols=['COPPER', 'GASOLINE', 'GER40', 'GOLD', 'HEATOIL', 'JPN225', 'NDAQ100', 'PALLADIUM', 'PLATINUM', 'SILVER', 'SPX500', 'UK100', 'US2000', 'US30', 'USNATGAS', 'USOIL']
  - `('intra_session_gap', '2026-06-15', '2026-06-15T22')`: n=16, symbols=['COPPER', 'GASOLINE', 'GER40', 'GOLD', 'HEATOIL', 'JPN225', 'NDAQ100', 'PALLADIUM', 'PLATINUM', 'SILVER', 'SPX500', 'UK100', 'US2000', 'US30', 'USNATGAS', 'USOIL']
  - `('intra_session_gap', '2026-06-16', '2026-06-16T22')`: n=16, symbols=['COPPER', 'GASOLINE', 'GER40', 'GOLD', 'HEATOIL', 'JPN225', 'NDAQ100', 'PALLADIUM', 'PLATINUM', 'SILVER', 'SPX500', 'UK100', 'US2000', 'US30', 'USNATGAS', 'USOIL']
  - `('intra_session_gap', '2026-06-17', '2026-06-17T22')`: n=16, symbols=['COPPER', 'GASOLINE', 'GER40', 'GOLD', 'HEATOIL', 'JPN225', 'NDAQ100', 'PALLADIUM', 'PLATINUM', 'SILVER', 'SPX500', 'UK100', 'US2000', 'US30', 'USNATGAS', 'USOIL']
  - `('intra_session_gap', '2026-06-18', '2026-06-18T22')`: n=16, symbols=['COPPER', 'GASOLINE', 'GER40', 'GOLD', 'HEATOIL', 'JPN225', 'NDAQ100', 'PALLADIUM', 'PLATINUM', 'SILVER', 'SPX500', 'UK100', 'US2000', 'US30', 'USNATGAS', 'USOIL']
  - `('intra_session_gap', '2026-06-22', '2026-06-22T22')`: n=16, symbols=['COPPER', 'GASOLINE', 'GER40', 'GOLD', 'HEATOIL', 'JPN225', 'NDAQ100', 'PALLADIUM', 'PLATINUM', 'SILVER', 'SPX500', 'UK100', 'US2000', 'US30', 'USNATGAS', 'USOIL']
  - `('intra_session_gap', '2026-06-23', '2026-06-23T22')`: n=16, symbols=['COPPER', 'GASOLINE', 'GER40', 'GOLD', 'HEATOIL', 'JPN225', 'NDAQ100', 'PALLADIUM', 'PLATINUM', 'SILVER', 'SPX500', 'UK100', 'US2000', 'US30', 'USNATGAS', 'USOIL']
  - `('intra_session_gap', '2026-06-24', '2026-06-24T22')`: n=16, symbols=['COPPER', 'GASOLINE', 'GER40', 'GOLD', 'HEATOIL', 'JPN225', 'NDAQ100', 'PALLADIUM', 'PLATINUM', 'SILVER', 'SPX500', 'UK100', 'US2000', 'US30', 'USNATGAS', 'USOIL']
- **missing_session**: 6 events / 1 clusters.
  - `('missing_session', '2026-06-19')`: n=6, symbols=['CORN', 'FEEDBEEF', 'LEANHOGS', 'LIVEBEEF', 'SOYBEAN', 'WHEAT']
- **stub_session**: 4 events / 2 clusters.
  - `('stub_session', '2026-06-04')`: n=1, symbols=['FEEDBEEF']
  - `('stub_session', '2026-06-19')`: n=3, symbols=['HEATOIL', 'LSGOIL', 'US2000']
- **sunday_anomaly**: 28 events / 4 clusters.
  - `('sunday_anomaly', '2026-05-31')`: n=7, symbols=['CORN', 'GER40', 'JPN225', 'SOYBEAN', 'UK100', 'UKOIL', 'WHEAT']
  - `('sunday_anomaly', '2026-06-07')`: n=7, symbols=['CORN', 'GER40', 'JPN225', 'SOYBEAN', 'UK100', 'UKOIL', 'WHEAT']
  - `('sunday_anomaly', '2026-06-14')`: n=7, symbols=['CORN', 'GER40', 'JPN225', 'SOYBEAN', 'UK100', 'UKOIL', 'WHEAT']
  - `('sunday_anomaly', '2026-06-21')`: n=7, symbols=['CORN', 'GER40', 'JPN225', 'SOYBEAN', 'UK100', 'UKOIL', 'WHEAT']

Cluster detail (B):
- **intra_session_gap**: 255 events / 16 clusters.
  - `('intra_session_gap', '2026-08-10', '2026-08-10T22')`: n=16, symbols=['COPPER', 'GASOLINE', 'GER40', 'GOLD', 'HEATOIL', 'JPN225', 'NDAQ100', 'PALLADIUM', 'PLATINUM', 'SILVER', 'SPX500', 'UK100', 'US2000', 'US30', 'USNATGAS', 'USOIL']
  - `('intra_session_gap', '2026-08-11', '2026-08-11T22')`: n=16, symbols=['COPPER', 'GASOLINE', 'GER40', 'GOLD', 'HEATOIL', 'JPN225', 'NDAQ100', 'PALLADIUM', 'PLATINUM', 'SILVER', 'SPX500', 'UK100', 'US2000', 'US30', 'USNATGAS', 'USOIL']
  - `('intra_session_gap', '2026-08-12', '2026-08-12T22')`: n=16, symbols=['COPPER', 'GASOLINE', 'GER40', 'GOLD', 'HEATOIL', 'JPN225', 'NDAQ100', 'PALLADIUM', 'PLATINUM', 'SILVER', 'SPX500', 'UK100', 'US2000', 'US30', 'USNATGAS', 'USOIL']
  - `('intra_session_gap', '2026-08-13', '2026-08-13T22')`: n=16, symbols=['COPPER', 'GASOLINE', 'GER40', 'GOLD', 'HEATOIL', 'JPN225', 'NDAQ100', 'PALLADIUM', 'PLATINUM', 'SILVER', 'SPX500', 'UK100', 'US2000', 'US30', 'USNATGAS', 'USOIL']
  - `('intra_session_gap', '2026-08-17', '2026-08-17T22')`: n=16, symbols=['COPPER', 'GASOLINE', 'GER40', 'GOLD', 'HEATOIL', 'JPN225', 'NDAQ100', 'PALLADIUM', 'PLATINUM', 'SILVER', 'SPX500', 'UK100', 'US2000', 'US30', 'USNATGAS', 'USOIL']
  - `('intra_session_gap', '2026-08-18', '2026-08-18T22')`: n=16, symbols=['COPPER', 'GASOLINE', 'GER40', 'GOLD', 'HEATOIL', 'JPN225', 'NDAQ100', 'PALLADIUM', 'PLATINUM', 'SILVER', 'SPX500', 'UK100', 'US2000', 'US30', 'USNATGAS', 'USOIL']
  - `('intra_session_gap', '2026-08-19', '2026-08-19T22')`: n=16, symbols=['COPPER', 'GASOLINE', 'GER40', 'GOLD', 'HEATOIL', 'JPN225', 'NDAQ100', 'PALLADIUM', 'PLATINUM', 'SILVER', 'SPX500', 'UK100', 'US2000', 'US30', 'USNATGAS', 'USOIL']
  - `('intra_session_gap', '2026-08-20', '2026-08-20T22')`: n=16, symbols=['COPPER', 'GASOLINE', 'GER40', 'GOLD', 'HEATOIL', 'JPN225', 'NDAQ100', 'PALLADIUM', 'PLATINUM', 'SILVER', 'SPX500', 'UK100', 'US2000', 'US30', 'USNATGAS', 'USOIL']
  - `('intra_session_gap', '2026-08-24', '2026-08-24T22')`: n=16, symbols=['COPPER', 'GASOLINE', 'GER40', 'GOLD', 'HEATOIL', 'JPN225', 'NDAQ100', 'PALLADIUM', 'PLATINUM', 'SILVER', 'SPX500', 'UK100', 'US2000', 'US30', 'USNATGAS', 'USOIL']
  - `('intra_session_gap', '2026-08-25', '2026-08-25T22')`: n=16, symbols=['COPPER', 'GASOLINE', 'GER40', 'GOLD', 'HEATOIL', 'JPN225', 'NDAQ100', 'PALLADIUM', 'PLATINUM', 'SILVER', 'SPX500', 'UK100', 'US2000', 'US30', 'USNATGAS', 'USOIL']
  - `('intra_session_gap', '2026-08-26', '2026-08-26T22')`: n=16, symbols=['COPPER', 'GASOLINE', 'GER40', 'GOLD', 'HEATOIL', 'JPN225', 'NDAQ100', 'PALLADIUM', 'PLATINUM', 'SILVER', 'SPX500', 'UK100', 'US2000', 'US30', 'USNATGAS', 'USOIL']
  - `('intra_session_gap', '2026-08-27', '2026-08-27T22')`: n=16, symbols=['COPPER', 'GASOLINE', 'GER40', 'GOLD', 'HEATOIL', 'JPN225', 'NDAQ100', 'PALLADIUM', 'PLATINUM', 'SILVER', 'SPX500', 'UK100', 'US2000', 'US30', 'USNATGAS', 'USOIL']
  - `('intra_session_gap', '2026-08-31', '2026-08-31T22')`: n=15, symbols=['COPPER', 'GASOLINE', 'GER40', 'GOLD', 'HEATOIL', 'JPN225', 'NDAQ100', 'PALLADIUM', 'PLATINUM', 'SILVER', 'SPX500', 'US2000', 'US30', 'USNATGAS', 'USOIL']
  - `('intra_session_gap', '2026-09-01', '2026-09-01T22')`: n=16, symbols=['COPPER', 'GASOLINE', 'GER40', 'GOLD', 'HEATOIL', 'JPN225', 'NDAQ100', 'PALLADIUM', 'PLATINUM', 'SILVER', 'SPX500', 'UK100', 'US2000', 'US30', 'USNATGAS', 'USOIL']
  - `('intra_session_gap', '2026-09-02', '2026-09-02T22')`: n=16, symbols=['COPPER', 'GASOLINE', 'GER40', 'GOLD', 'HEATOIL', 'JPN225', 'NDAQ100', 'PALLADIUM', 'PLATINUM', 'SILVER', 'SPX500', 'UK100', 'US2000', 'US30', 'USNATGAS', 'USOIL']
  - `('intra_session_gap', '2026-09-03', '2026-09-03T22')`: n=16, symbols=['COPPER', 'GASOLINE', 'GER40', 'GOLD', 'HEATOIL', 'JPN225', 'NDAQ100', 'PALLADIUM', 'PLATINUM', 'SILVER', 'SPX500', 'UK100', 'US2000', 'US30', 'USNATGAS', 'USOIL']
- **missing_session**: 1 events / 1 clusters.
  - `('missing_session', '2026-08-31')`: n=1, symbols=['UK100']
- **stub_session**: 0 events / 0 clusters.
- **sunday_anomaly**: 21 events / 3 clusters.
  - `('sunday_anomaly', '2026-08-16')`: n=7, symbols=['CORN', 'GER40', 'JPN225', 'SOYBEAN', 'UK100', 'UKOIL', 'WHEAT']
  - `('sunday_anomaly', '2026-08-23')`: n=7, symbols=['CORN', 'GER40', 'JPN225', 'SOYBEAN', 'UK100', 'UKOIL', 'WHEAT']
  - `('sunday_anomaly', '2026-08-30')`: n=7, symbols=['CORN', 'GER40', 'JPN225', 'SOYBEAN', 'UK100', 'UKOIL', 'WHEAT']

## Section 3 — Gap decomposition (288 events, window A, intra_session_gap)

Total: **288 events / 18 clusters** (all clusters size 16, same 16 symbols, same hour bucket 22:00Z).

### (a) Simultaneity / independence

- Buckets (date,hour): N=18. Every bucket has exactly 16 symbols; observed sizes are identical (16,16,...,16).
- Per-symbol gap count in window A is 18/18 buckets for each of those 16 symbols and 0 for all others. Under independence with per-symbol rate p_i=count_i/N, expected bucket size mean is 16.0 and Poisson-binomial variance is 0.0 because p_i is 0 or 1 for all symbols. This is **perfect co-occurrence** within the affected set, not independent per-symbol gaps.
- Interpretation: the 288 events are 18 repetitions of one feed/maintenance/session-boundary phenomenon affecting a fixed 16-symbol cohort.

### (b) Stratum — venue/asset class and module eligibility

| Venue/stratum | Events | Share |
| --- | --- | --- |
| CME/NYMEX | 108 | 37.5% |
| CME/EquityIndex | 72 | 25.0% |
| CME/COMEX | 54 | 18.8% |
| Eurex/EquityIndex | 18 | 6.2% |
| OSE/EquityIndex | 18 | 6.2% |
| ICE/EquityIndex | 18 | 6.2% |

- Module 1 eligible (level_proximity-2.1.0 universe, 33 symbols): **288 / 288**.
- Module 2 only (session_anomalies universe minus module 1): **0 / 288**. Module-2-only symbols: ['CADSEK', 'EURCAD', 'FEEDBEEF', 'LEANHOGS', 'LIVEBEEF', 'NZDUSD'].
- All gap events fall in module-1-eligible symbols; none in the 6 module-2-only symbols (AUDCAD? no, AUDCAD is in mod1; module-2-only are CADSEK, EURCAD, FEEDBEEF, LEANHOGS, LIVEBEEF, NZDUSD).

### (c) Symbol concentration

| Symbol | Events | Share of 288 |
| --- | --- | --- |
| COPPER | 18 | 6.2% |
| GASOLINE | 18 | 6.2% |
| GER40 | 18 | 6.2% |
| GOLD | 18 | 6.2% |
| HEATOIL | 18 | 6.2% |
- Top 5 share: **90 / 288 = 31.2%**. Concentration is uniform across 16 symbols (18 each), so "top 5" is arbitrary; the real concentration is a fixed 16-symbol cohort = 100% of gaps.

### (d) gap_hours distribution

| gap_hours | Events | Share |
| --- | --- | --- |
| 2 | 288 | 100.0% |
- Every gap is exactly 2 hours.

### (e) Adjacency to configured maintenance windows

- Configured maintenance for all 16 affected symbols: `20:00-22:00 America/New_York` (frozen config). Gap pattern: missing 21:00Z bar on affected days, event at 22:00Z, gap_hours=2 (20:00Z->22:00Z). In America/New_York during EDT this is 16:00->18:00 local — **not** inside the configured 20:00-22:00 maintenance window; it is adjacent to the US late-afternoon/roll period but outside configured maintenance allowance.
- Detector maintenance-adjacency check (±1.5h / span heuristic): adjacent=0, non-adjacent=288.
- Evidence from raw bars (COPPER 2026-05-26 example): bars present 00:00Z..20:00Z,22:00Z,23:00Z; missing 21:00Z; local times show 16:00-18:00 EDT gap. This is a systematic 21:00Z missing bar across a fixed cohort, daily on trading days in window A.

### (f) Judgment

**Judgment: mostly feed/venue-session-structure artifact expressed as a per-symbol detector event, not 288 independent per-symbol data-quality failures.** It is highly clustered (18 clusters x 16 symbols, identical hour, identical gap size, identical cohort). It is not explained by configured maintenance-window boundaries (configured maintenance is 20:00-22:00 NY; observed gap is 20:00Z-22:00Z / 16:00-18:00 EDT). It is consistent with a common daily break/quiescent hour for that contract cohort in this corpus representation, or a feed-level systematic gap; distinguishing those requires upstream feed/vendor schedule evidence not present in-repo. The 1.0.0 INSIDE verdict on the ×/÷2 band is **WEAK evidence** and this review does not treat it as validation; cluster-based accounting materially changes the signal (18 clusters, not 288 independent events).

## Section 4 — Precision audit (stratified sample)

Sample: at least 3 events per type (all events for types with <3). Ground truth sources used: CME Group holiday/trading-hours pages (cmegroup.com/trading-hours.html, Juneteenth 2026 schedule/settlement notices), LSE business days calendar, CME contract specs for grains, and corpus bar inspection. Where primary venue-specific contract hours were not directly confirmed, event is UNVERIFIABLE.

| Type | Sampled event | Evidence | Verdict | Source |
| --- | --- | --- | --- | --- |
| intra_session_gap | COPPER 2026-05-26 22:00Z gap=2 | Corpus bars show 20:00Z->22:00Z missing 21:00Z; configured maint 20:00-22:00 NY not matching 16:00-18:00 EDT. CME Globex metals have scheduled breaks but this exact 21:00Z daily hole needs vendor/contract schedule confirmation. | UNVERIFIABLE | Corpus H1; frozen config; CME trading-hours page (general) |
| intra_session_gap | PLATINUM 2026-05-26 22:00Z gap=2 | Same cohort/pattern as COPPER; identical hour/gap. | UNVERIFIABLE | Corpus pattern; CME general schedule |
| intra_session_gap | USOIL 2026-06-24 22:00Z gap=2 | Same cohort/pattern; NYMEX energy daily break differs by product; 21:00Z gap not directly confirmed as scheduled. | UNVERIFIABLE | Corpus pattern; CME/NYMEX general schedule |
| sunday_anomaly | CORN 2026-05-31 expected=1 observed=0 | CME grains Sunday evening session opens 7:00pm CT; a 0-bar Sunday on UTC calendar day can be a Sunday-open timing/template artifact depending on how bars are bucketed. Needs bar-timestamp audit vs CME grain session. | UNVERIFIABLE | CME Grains contract specs (Sun-Fri 7:00pm-7:45am CT; Mon-Fri 8:30am-1:20pm CT) |
| sunday_anomaly | SOYBEAN 2026-06-14 expected=1 observed=0 | Same as CORN; grain Sunday session exists; UTC-day bucketing can misclassify Sunday open. | UNVERIFIABLE | CME Soybean contract specs |
| sunday_anomaly | WHEAT 2026-06-21 expected=1 observed=0 | Same grain Sunday pattern. | UNVERIFIABLE | CME Wheat contract specs |
| missing_session | CORN 2026-06-19 expected=1 observed=0 | 2026-06-19 Juneteenth: CME grains/livestock closed. 0 bars observed. Detector fired missing_session; economically/calendar-explained closure. | RIGHT (event observed) / calendar-explained | CME holiday calendar; CME Juneteenth schedule; corpus shows 0 bars |
| missing_session | LIVEBEEF 2026-06-19 expected=6 observed=0 | Juneteenth: CME livestock closed; 0 bars observed. | RIGHT / calendar-explained | CME holiday calendar; corpus |
| missing_session | WHEAT 2026-06-19 expected=1 observed=0 | Juneteenth: CBOT grains closed; 0 bars observed. | RIGHT / calendar-explained | CME holiday calendar; corpus |
| stub_session | FEEDBEEF 2026-06-04 expected=6 observed=5 | Corpus shows 13:00Z-17:00Z, missing 18:00Z; same-weekday normally 6 bars. True short/truncated session in data; cause unknown. | RIGHT (data shortfall) | Corpus H1 bars |
| stub_session | LSGOIL 2026-06-19 expected=21 observed=18 | Juneteenth date; observed 00:00Z-17:00Z. ICE Gasoil specific holiday hours not confirmed from primary ICE source in-session. | UNVERIFIABLE | Corpus bars; Juneteenth date context |
| stub_session | US2000 2026-06-19 expected=23 observed=17 | Juneteenth early close 12:00 CT for CME equity index; observed ends 16:00Z=12:00 EDT, matches early close. | RIGHT / calendar-explained | CME holiday calendar; corpus bars |

### Per-type precision (sample)

| Type | Sample size | RIGHT | WRONG | UNVERIFIABLE | Precision (RIGHT / (RIGHT+WRONG), excl UNVERIFIABLE) |
| --- | --- | --- | --- | --- | --- |
| intra_session_gap | 3 | 0 | 0 | 3 | n/a (no adjudicated events) |
| sunday_anomaly | 3 | 0 | 0 | 3 | n/a |
| missing_session | 3 | 3 (calendar-explained) | 0 | 0 | 100% as detector firing; 0% as unexpected data-quality anomaly without calendar attribution |
| stub_session | 3 | 2 (1 calendar-explained, 1 true shortfall) | 0 | 1 | 100% on adjudicated; caveat small sample |

**Audit caveat:** This sample is small and deliberately stratified; it is not a random precision estimate. "RIGHT" means the detector correctly observed the bar-count/gap condition in data. It does **not** mean the event is an actionable data-quality anomaly after calendar/context attribution. The missing_session sample is entirely Juneteenth-explained, reinforcing the need for calendar attribution before treating missing_session as feed failure.

## Section 5 — Design proposals (proposals only; nothing decided)

### 5(a) Layered overlay for correlated events

Proposal: three-layer model, preserving detector purity and replay identity.

1. **Detector (UNCHANGED, pure).** Per-symbol events emitted only from data + frozen templates. No calendar suppression, no clustering mutation. Replay byte-identity preserved for same inputs/config/code.
2. **Cluster annotation (derived publication artifact).** A separate annotations file keyed to batch (e.g. `cluster_annotations.json` or sidecar), carrying `cluster_id`, `cluster_size`, `cluster_key`, `venue_concentration`, `member_event_keys`/indices per event. `events.json` is never mutated; closed event schema does not change. Annotations are recomputable from events+rule version and are published alongside batch artifacts.
3. **Calendar attribution (optional, versioned, hashed input).** A versioned, hashed holiday/calendar input produces `calendar_match` annotations (rule id, calendar source, venue scope, confidence). It never suppresses or alters an event. Attribution is additive metadata only.

**Homogeneity test (holiday vs feed failure):** A holiday/closure hits ~100% of a venue-group cohort and ~0% of unrelated venue groups as whole-day absence (or uniform early close) on the same calendar rule; a feed failure spans venue groups, is partial within each group, and is often part-day/irregular. Test: for a candidate cluster, compute venue-group coverage vector; compare to expected venue-group scope of calendar rule. High within-scope coverage + near-zero out-of-scope + full-day/expected-short pattern => calendar attribution candidate; mixed-group partial pattern => feed-failure candidate.

**Historical recurrence check:** Same symbol absent/short on same calendar rule in earlier years (e.g., prior Juneteenth observed dates, Thanksgiving, Christmas, July 4). Recurrence across years supports calendar attribution; one-off or non-calendar-date recurrence supports feed/data issue.

### 5(b) Ceiling formula for 1.1.0 pre-registration

Proposed formula (per type, cluster counts): `k_B` = baseline cluster count, `k_A` = confirmatory cluster count, `r = E_A/E_B` exposure ratio, `p = r/(1+r)`. Ceiling `C = max{ c : P(Binomial(k_B + c, p) >= c) > alpha }`, `alpha = 0.05/4` (Bonferroni over 4 anomaly types). Breach requires `k_A > C` **AND** `rate_A` above operator-set materiality floor `rho_floor`.

Proposed `rho_floor` (per type, cluster-rate per 100 symbol-days; reasoning):

| Type | Proposed rho_floor | Zero-baseline min E = -ln(alpha)/rho_floor | Reasoning |
| --- | --- | --- | --- |
| intra_session_gap | 0.500 / 100 sd | 876.4 symbol-days | High-frequency structural/feed artifact class; floor avoids flagging tiny cluster-rate noise while remaining sensitive to material regime shifts. Set above near-zero but below observed clustered baseline density. |
| missing_session | 0.100 / 100 sd | 4382.0 symbol-days | Missing whole sessions are operationally material even at low rates; low floor keeps sensitivity while requiring at least minimal materiality. |
| stub_session | 0.100 / 100 sd | 4382.0 symbol-days | Stub sessions can indicate truncation/feed issues; same low floor as missing_session pending better calendar attribution. |
| sunday_anomaly | 0.200 / 100 sd | 2191.0 symbol-days | Sunday behavior is template/session-model sensitive; modest floor avoids overreacting to template drift. |

Zero-baseline window-size rule: for types with `k_B==0`, require `E >= -ln(alpha)/rho_floor` (rule of three generalization) before confirmatory claims; otherwise label underpowered.

### Retroactive re-judgment on window A (clusters) — REVIEW EXPECTATION ONLY

**This table is a labeled re-judgment, not a ledger change. SCAN-019 verdicts remain as recorded.**

| Type | k_B clusters | k_A clusters | r=E_A/E_B | alpha | Ceiling C | k_A > C | Re-judgment label |
| --- | --- | --- | --- | --- | --- | --- | --- |
| intra_session_gap | 16 | 18 | 1.0 | 0.01250 | 32 | NO |  |
| missing_session | 1 | 1 | 1.0 | 0.01250 | 8 | NO | UNRESOLVED pending Section 1 classification / calendar attribution; arithmetic-only re-judgment. |
| stub_session | 0 | 2 | 1.0 | 0.01250 | 6 | NO | UNRESOLVED pending Section 1 classification / calendar attribution; arithmetic-only re-judgment. |
| sunday_anomaly | 3 | 4 | 1.0 | 0.01250 | 12 | NO |  |

Arithmetic check (script-computed, authoritative for this review): with r=1, alpha=0.0125, p=0.5, the exact conditional ceiling is `C=7` for missing_session (`k_B=1,k_A=1`) and `C=5` for stub_session (`k_B=0,k_A=2`); both are INSIDE on cluster-count ceiling arithmetic (`k_A>C` is NO). This confirms the consult’s expected direction on arithmetic. Missing and stub remain **UNRESOLVED** for operational interpretation pending Section 1 classification/calendar attribution; stub is explicitly unresolved per the work order.

Computed ceilings from batch: `{"intra_session_gap": {"kB": 16, "kA": 18, "C": 32, "breach": false}, "missing_session": {"kB": 1, "kA": 1, "C": 8, "breach": false}, "stub_session": {"kB": 0, "kA": 2, "C": 6, "breach": false}, "sunday_anomaly": {"kB": 3, "kA": 4, "C": 12, "breach": false}}`. This **confirms** the consult arithmetic direction: missing and stub read INSIDE on cluster-count ceiling arithmetic; stub is explicitly UNRESOLVED pending Section 1 classification. Missing is also UNRESOLVED for operational interpretation because the A cluster is Juneteenth-explained.

### 5(c) Confirmatory design for 1.1.0

Proposal: one confirmatory window, power-sized per 5(b) window rule, selected by a rule fixed before freeze and blind to content (earliest unburned span-eligible window of required length). Verdicts on cluster rates. The calendar mechanism is **NOT proven** by the confirmatory window; it is fixture-tested separately on burned history against an external holiday calendar (precision/recall of attribution across years of Christmas, July 4, Thanksgiving, Juneteenth), including US/EU DST-mismatch weeks for maintenance logic. The mechanism must be frozen before the confirmatory scan runs.

## Closing — PROPOSED 1.1.0 CHANGE LIST

| # | Tag | Proposed change |
| --- | --- | --- |
| 1 | DEFINITION | Define session_anomalies event accounting at both event and cluster units; pre-register cluster as primary confirmatory unit for correlated anomaly types. |
| 2 | DEFINITION | Adopt cluster-based exact conditional ceiling (`Binomial(k_B+c, r/(1+r))`, alpha=0.05/4) plus `rho_floor` materiality gate for 1.1.0 confirmatory verdicts. |
| 3 | PROCESS | Fix confirmatory window by pre-registered blind rule (earliest unburned span-eligible window of required length); no content-aware window selection. |
| 4 | DEFINITION | Separate detector purity from derived annotations: cluster annotations published as sidecar artifacts keyed to batch; `events.json` schema unchanged. |
| 5 | CONFIG | Introduce optional versioned/hashed calendar-attribution input for additive `calendar_match` annotations; attribution never suppresses/alters detector events. |
| 6 | PROCESS | Fixture-test calendar attribution on burned history with external holiday calendar precision/recall (Christmas, July 4, Thanksgiving, Juneteenth) and US/EU DST-mismatch weeks before confirmatory scan. |
| 7 | DEFINITION | Mark missing_session/stub_session calendar-explained clusters as attributed-not-actionable in reporting, while retaining raw detector events for audit. |
| 8 | CODE | Implement cluster annotation generator (derived artifact) and cluster-rate reporting; no change to detector event semantics or event schema. |
| 9 | CONFIG | Revisit Sunday/gap template sensitivity (refit showed Sunday movement) with explicit template-fit provenance and exclusion rules in freeze record. |
| 10 | PROCESS | Carry SCAN-019 ledger verdicts unchanged; any re-judgment is review-only until a separately pre-registered 1.1.0 confirmatory run. |

## Non-changes / guardrails

- No detector code changed. No freeze created. No scan run. No ledger edit.
- SCAN-019 verdicts remain: missing BREACHED, stub BREACHED (ledger record unchanged).
- Corpus read-only; no cleanup deletions; analysis scripts/outputs in /tmp except this report.
