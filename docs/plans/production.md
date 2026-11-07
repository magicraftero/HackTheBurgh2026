# Role plan: Production (back end)

For: the coding agent working with the Production person. Read `docs/plans/00-shared.md` first, because it defines every path, schema, driver definition and deadline, plus the holdout rule. Then read `prereg/PASS_MARKS.md`: your F1, M1 and M2 code must match it exactly.

## Your job

Build the anomaly function, the driver tables, the weekly farm indices and every production finding:

- the seasonality trap;
- the count × weight split;
- the nowcast backtest (F1), with its locked holdout and the September 2026 worked example;
- the driver ranking;
- the M1/M2 panel.

You do analysis only. Data turns your JSON into charts, so keep the JSON exactly to the contract.

You are the longest critical path. If a task runs late, ship the simplest correct version and tell your human. See "If you're behind" for what to cut.

## Inputs

From Data:

- 18:30: `directorate_area_month.parquet`, `ssb_weekly.parquet`
- 21:30: `farm_week.parquet` and `farms.parquet`, 2017 onward
- 23:30: the 2012–2016 farm data

Until the farm data arrives, build and test everything on the Directorate and Statistics Norway tables.

## Tasks, in order

### 1. `analysis/anomalies.py` (by 18:30; Price imports it)

```python
def anomaly(x: pd.Series, freq: Literal["W", "M"],
            transform: Literal["log", "log1p", "none"] = "log",
            fit_end: pd.Timestamp | None = None, K: int = 3) -> pd.Series:
```

- `x` is indexed by period start (the Monday for weeks, the 1st for months), sorted, on a regular grid, with gaps as NaN.
- Set y = `transform(x)`.
- The level L_t is the mean of y over the previous 52 weeks (or 12 months), excluding t. It needs at least 75% of those values present; otherwise it's NaN.
- Then r_t = y_t − L_t.
- Season: fit OLS of r on a constant, sin and cos of 2πk·d/365.25 for k = 1..K, and the holiday dummies. Fit only on rows dated on or before `fit_end` (all rows if it's None). Here d is the day of year of the week's Thursday, or of the 15th for months.
- Holidays, using `dateutil.easter.easter`:
  - Weekly series: Easter marks the ISO weeks containing Good Friday or Easter Monday. Christmas marks the ISO weeks containing 24 December to 1 January.
  - Monthly series: Easter marks the month containing Easter Sunday, and there's no Christmas term.
- Return r minus the fitted season.
- Tests:
  - On a synthetic trend + sine + noise series, the anomaly has no trend and no seasonal cycle left.
  - Changing data after `fit_end` doesn't change the fitted season.
- Push, then tell your human that Price can import it.

### 2. Directorate drivers → `drivers_area_month.parquet` (by 21:30)

- `analysis/drivers.py` reads `directorate_area_month`. Build areas 1–13, plus a national version from sums over areas 0–13.
- Levels, exactly as in the contract:
  - `biomass_kg`, `fish_stock`;
  - `smolt_pipe` = `log1p` of the sum of `smolt_released` over months m − 23 to m − 12;
  - `feed_rate` = `feed_kg / biomass_kg`;
  - `mortality` = `1000 × dead / fish_stock`.
- Full-sample anomalies, fitted for each area separately:
  - `biomass_anom` and `fish_stock_anom` with `"log"`;
  - `smolt_pipe_anom` with `"none"`;
  - `feed_rate_anom` with `"log"`;
  - `mortality_anom` with `"log1p"`.
- Set `available_at_dir` = the 20th of month m + 1.
- Push by 21:30. The BarentsWatch columns are filled in at task 4.

### 3. Weekly farm indices → `weekly_area_index.parquet`, `weekly_national_index.parquet` (by 22:30, rerun at 23:30)

- Weights: `capacity_t`, or the area's median capacity when it's null.
- Area-week values:
  - `mobile_idx`: the capacity-weighted mean of `mobile` over farms with `reported`.
  - `treat_rate`: the share of reporting farm-weeks with `treated`. A farm-week counts once.
  - `disease_share`: the share of reporting sites with `isa` or `pd` true. Suspected and confirmed both count. If Data reports no disease flags, it's null throughout.
  - `temp_c`: the capacity-weighted mean of `sea_temp_c`.
  - `n_reporting`.
- National week: the same formulas over all reporting farms in Norway, not an average of areas.
- Temperature:
  - `normal_c` for an area (or the nation) and an ISO week number is the mean `temp_c` in that week across all *previous* years. It needs at least 3 such years; otherwise it's NaN.
  - `dd_anom` = the rolling 6-week sum of 7 × (`temp_c` − `normal_c`).
  - The bands follow the current week's `temp_c`: `dd_below8`, `dd_8to14`, `dd_above14` (each equals `dd_anom` inside its band and 0 outside), and `dd_below14` = `dd_below8` + `dd_8to14`.
- Full-sample anomalies:
  - `mobile_anom` = `anomaly(mobile_idx, "W", "log1p")`;
  - `treat_anom` = `anomaly(100 × treat_rate, "W", "log1p")`.
- `available_at` = the latest `available_at` among the inputs.
- Push the national file by 22:30, because Price needs it.
- **Rerun when the 2012–2016 data lands (about 23:30).** Temperature normals need three previous years.
- Check: plot the national `treat_rate` for 2024–2025. If it jumps at 2024-W46 (the lice-report format change), tell your human before using treatments after that date.

### 4. Complete the driver tables and the panel (by 23:30)

- `drivers_area_month`: add the monthly means of the weekly area values over ISO weeks whose Thursday falls in the month. That's `mobile_idx`, `mobile_anom`, `treat_rate`, `treat_anom`, `disease_share`, `temp_c`, `dd_anom` and the bands, with `available_at_bw`.
- `drivers_national_month` gets:
  - the national Directorate ratios;
  - the national weekly monthly means;
  - `export_vol` (fresh `volume_t` summed over ISO weeks whose Thursday is in the month);
  - `export_vol_anom` (`"log"`);
  - `available_at_dir` and `available_at_bw`.
- `area_month_panel` gets:
  - `harvest_count`, `harvest_kg`, `avg_kg`;
  - `count_anom` = `anomaly(harvest_count, "M", "log1p")`;
  - `weight_anom` = `anomaly(avg_kg, "M", "log")`;
  - `volume_anom` = `anomaly(harvest_kg, "M", "log1p")`;
  - every column of `drivers_area_month`.
- Write `area_month.json` in the contract's shape.
- Count the area-months with zero harvest (null `avg_kg`) and tell your human.

### 5. The seasonality trap → `trap.json` (by 23:30)

- Use national weekly series from 2017-W01 to 2026-W44, with price = log `price_nok_kg`.
- Drivers and their transforms:
  - `mobile_idx`: `log1p`;
  - `treat_rate`: `log1p(100 × rate)`;
  - `disease_share`: none, and skip it if null;
  - `temp_c`: none;
  - export volume: log of `volume_t`.
- `raw_r` = the Pearson correlation of the transformed driver with log price. `anom_r` = the correlation of their anomalies, using the same transforms with full-sample fits. Use the same weeks for both.
- `highlight` = `"mobile_idx"`, with its `series`.
- Report whatever the numbers are, and don't tune them toward the expected story.

### 6. Count × weight bins → `channels.json` → `bins` (by 01:30)

- Use area-months for areas 1–13. Take terciles of the driver at month t. The outcome is the mean of `count_anom` and `weight_anom` over the window.
- Drivers and windows:
  - lice: `mobile_anom`, window 0–3;
  - temp: `dd_below14`, window 1–3;
  - feed: `feed_rate_anom`, window 1–3;
  - mortality: `mortality_anom`, window 0–3.

### 7. Nowcast backtest and F1: `analysis/nowcast.py` → `nowcast.json` (development window by 01:30; holdout at 04:00)

- **Unit and timing:** area a (1–13) and target month m. The forecast date D(m) is the 10th of month m + 1.
  - Use Directorate months up to m − 1 only.
  - Use BarentsWatch and Statistics Norway rows with `available_at` ≤ D(m).
- **Outcomes:** log `harvest_kg` (F1's outcome), log `harvest_count` and log `avg_kg`.
  - Work in anomaly space. Recompute every anomaly from its level column with `fit_end` = month m − 1.
  - Then add back L_m and the season to get log predictions.
- **Models** (pooled OLS across areas with statsmodels), exactly as in PASS_MARKS:
  - **B0:** `biomass_anom` and `fish_stock_anom` at m − 1.
  - **B1:** B0 plus `export_vol_anom` at m.
  - **Drivers:** B1 plus `smolt_pipe_anom`, `feed_rate_anom` and `mortality_anom` at m − 1, plus `mobile_anom`, `treat_anom`, `disease_share`, `dd_below8`, `dd_8to14` and `dd_above14` at m and at m − 1. Leave out `disease_share` if it's null, and record that in `analysis/RESULTS.md`.
- **Walk forward:** for each m, refit everything on area-months before m.
- **Holdout rule:**
  - By default, `python -m analysis.nowcast` runs m from 2021-01 to 2024-12 only.
  - `python -m analysis.nowcast --final` runs 2021-01 to 2026-09, once, at 04:00.
  - Never compute or print holdout scores before then.
- **Scores:** the MAE of each log outcome for each model, pooled over areas, per window. Write `scores.dev` by 01:30 and `scores.holdout` at the freeze. Note in the JSON that actuals are today's revised data.
- **F1** (holdout only, at the freeze):
  - On log kg, `improvement_pct` = 100 × (1 − MAE_drivers / MAE_b1).
  - Clark–West: for each area-month, f = e_B1² − (e_D² − (ŷ_B1 − ŷ_D)²). Average f across areas each month, then regress the monthly series on a constant with `sm.OLS(f, np.ones(len(f))).fit(cov_type="HAC", cov_kwds={"maxlags": 3})`. The one-sided p is 1 − Φ(t).
  - It passes only if `improvement_pct` ≥ 5 **and** p < 0.05.
- **`latest`** (at the freeze): September 2026, the last holdout month, as made on 2026-10-10.
  - Use the Drivers model, or B1 if B1 beat Drivers on the holdout, and say which in `model`.
  - National values are sums over areas 1–13.
  - `error_pct` = 100 × (pred − actual) / actual.
- **Optional (Tier 3):** a `current` October 2026 nowcast from data available now, labelled as unverifiable.

### 8. Driver ranking → `drivers.json` (at the freeze, as part of `--final`)

- For each group in the contract's group table, rerun the full walk-forward (2021-01 to 2026-09) with that group's columns removed from the Drivers model.
- Report `mae_without` and `increase_pct` = 100 × (`mae_without` / `full_mae` − 1) on log kg. Report count and avg_kg under `by_outcome`.
- This is exploratory, with no pass mark.

### 9. M1/M2 panel: `analysis/channels.py` → `channels.json` → `panel` (01:30–03:30)

- **Data:** `area_month_panel`, Oct 2017 – Sep 2026, areas 1–13, using the full-sample anomaly columns and lags within each area.
- **M1 model:** `count_anom` (and, separately, `weight_anom`) on:
  - `mobile_anom` at lags 0–3;
  - `treat_anom` at lags 0–3;
  - `dd_below8`, `dd_8to14` and `dd_above14` at lags 0–3;
  - controls: `biomass_anom` and `fish_stock_anom` at t − 4.
- **M2 model (temperature only):** the same outcome on `dd_below14` and `dd_above14` at lags 0–3, with the same controls and no lice or treatment terms.
- **Effects:** `PanelOLS(y, X, time_effects=True, other_effects=<area × calendar-month code>, drop_absorbed=True)` from linearmodels, indexed by (area, month as a timestamp).
- **Errors:** `.fit(cov_type="kernel", kernel="bartlett", bandwidth=12)` (Driscoll–Kraay).
- **Each tested sum:** s = the sum of the coefficients over the lag window, and se = sqrt(1ᵀ V 1) from the covariance block. The 95% interval is s ± 1.96 se.
- **Pass rules,** exactly as in PASS_MARKS:
  - M1 passes only if the mobile-lice sum over lags 0–3 is above zero for count **and** below zero for weight, with both intervals excluding zero.
  - M2 passes if the `dd_below14` sum over lags 1–3 is above zero for weight, with its interval excluding zero.
- **Rows:** use `"test": "M1"` or `"M2"`. Also report the treatment sums and M2's count result with `"pass": null`.
- **Sensitivity checks, only if there's time,** labelled as such: disease share as an extra control; adult females instead of mobile lice; a wild cluster bootstrap by area.

### 10. Freeze at 04:00

- Run `python -m analysis.nowcast --final` once, which includes the driver ranking.
- Write `scores.holdout`, `f1`, `latest` and `drivers.json`.
- Record pass or fail for F1, M1 and M2 in `analysis/RESULTS.md`, with the development-window results alongside.
- Push, and tell your human.
- After that, only fix bugs that break files.

## If you're behind

Cut in this order:

1. `by_outcome` in the driver ranking;
2. the sensitivity checks;
3. the feed and mortality bins.

Never cut F1, M1 or M2.

## Who is waiting on you

| What | Who | By |
| --- | --- | --- |
| `analysis/anomalies.py` | Price | 18:30 |
| `weekly_national_index.parquet` | Price | 22:30, rerun 23:30 |
| `drivers_national_month.parquet` | Price | 23:30 |
| `area_month.json`, `trap.json` | Data (charts), Front end | 23:30 |
| `channels.json` bins, `nowcast.json` development window | Data (charts), Front end | 01:30 |
| `channels.json` panel; `nowcast.json` holdout, `f1` and `latest`; `drivers.json` | Data (charts), Front end | 04:00 |

## Ask your human when

- something would change a pass mark (never change one yourself);
- the anomalies still show a trend or a season;
- the treatment series breaks at 2024-W46;
- the panel won't fit, for example because a regressor is absorbed by the effects. Report it rather than redesigning the test;
- anyone asks for holdout numbers before 04:00. The answer is no.
