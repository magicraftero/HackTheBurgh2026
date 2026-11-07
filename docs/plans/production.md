# Role plan: Supply (back end)

For: the coding agent working with the Supply person. Read `docs/plans/00-shared.md` first, because it defines every path, schema and deadline. Then read `prereg/PASS_MARKS.md`: your H1 and H2 code must match it exactly.

## Your job

Build the anomalies, the Lice Pressure Index and every supply finding: the trap, the count × weight split, the nowcast backtest, the H1/H2 panel and the sealed October nowcast. You do analysis only. Data turns your JSON into charts, so keep the JSON exactly to the contract.

You are the longest critical path. If a task runs late, ship the simplest correct version and tell your human.

## Inputs

From Data: `directorate_area_month.parquet` and `ssb_weekly.parquet` at 18:30; `farm_week.parquet` and `farms.parquet` (2017 onward) at 21:30; lice for 2012–2016 at 23:30. Until the lice data arrives, write and test your code on the Directorate and Statistics Norway tables.

## Tasks, in order

### 1. `analysis/anomalies.py` (by 18:30, because Price imports it)

```python
def anomaly(x: pd.Series, freq: Literal["W", "M"],
            transform: Literal["log", "log1p", "none"] = "log",
            fit_end: pd.Timestamp | None = None, K: int = 3) -> pd.Series:
```

- `x` is indexed by period start (the Monday for weeks, the 1st for months), sorted, on a regular grid with gaps as NaN.
- Set y = `transform(x)`.
- The level L_t is the mean of y over the previous 52 weeks (or 12 months), excluding t. It needs at least 75% of those values present; otherwise it's NaN.
- Set r_t = y_t − L_t.
- **Season:** fit an OLS of r on a constant, sin and cos of 2πk·d/365.25 for k = 1..K, and the holiday dummies. Fit only on rows dated on or before `fit_end` (all rows if it's None). Here d is the day of the year of the week's Thursday, or of the 15th of the month.
- **Holidays** (use `dateutil.easter.easter`):
  - Weekly series: Easter is the ISO weeks containing Good Friday or Easter Monday, and Christmas is the ISO weeks containing 24 December to 1 January.
  - Monthly series: Easter is the month containing Easter Sunday. There's no Christmas term, because December is already covered by the season.
- Return r minus the fitted season.
- **Tests:**
  - On a synthetic series of trend + sine + noise, the anomaly has no trend and no seasonal cycle left.
  - Changing data after `fit_end` doesn't change the fitted season.
- Push, and tell your human that Price can import it.

### 2. Area-month anomalies (start by 21:30; `area_month.json` by 23:30)

- `analysis/build_area_month.py`, using `directorate_area_month` for areas 1–13 only.
- `count_anom` = `anomaly(harvest_count, "M", "log1p")` and `weight_anom` = `anomaly(avg_kg, "M", "log")`. Compute `biomass_anom` and `fish_stock_anom` the same way with `"log"`.
- Fit each area separately on its full sample, because this panel is for in-sample inference.
- Months with zero harvest have a null `avg_kg`. Count how many there are and tell your human.
- After task 3, join the lice columns and write `area_month_panel.parquet` and `area_month.json`.

### 3. Lice Pressure Index: `analysis/lice_index.py` (national weekly to Price by 22:30)

- **Weights:** `capacity_t`, or the area's median capacity when it's null.
- **Area-week values:**
  - `mobile_idx`: the capacity-weighted mean of `mobile` over farms that reported.
  - `treat_rate`: the share of reporting farm-weeks with `treated`.
  - `temp_c`: the capacity-weighted mean of `sea_temp_c`.
  - `n_reporting`.
- **National week:** the same formulas over all reporting farms in Norway, capacity-weighted. This is not a biomass-weighted average of areas, because the Directorate's area data only starts in Oct 2017 and Price trains from 2012.
- **Temperature:**
  - `normal_c` for an area and ISO week number is the mean of `temp_c` in the same week across all *previous* years. It needs at least 3 such years, otherwise it's NaN. This makes it past-only by construction, so it's safe for forecasting.
  - `dd_anom` = the rolling 6-week sum of 7 × (`temp_c` − `normal_c`).
  - The bands depend on the current week's `temp_c`. `dd_below8` equals `dd_anom` when `temp_c` < 8 and is 0 otherwise. `dd_8to14` and `dd_above14` work the same way for 8 ≤ `temp_c` < 14 and for `temp_c` ≥ 14. `dd_below14` = `dd_below8` + `dd_8to14`.
- **Months:** the mean of the weekly values over ISO weeks whose Thursday falls in that month.
- **Anomalies:** `mobile_anom` = `anomaly(mobile_idx, transform="log1p")` and `treat_anom` = `anomaly(100 × treat_rate, transform="log1p")`. Make weekly and monthly versions, fitted on the full sample; Price and your nowcast refit them past-only.
- `available_at` = the latest `available_at` among the inputs.
- **Rerun after 23:30.** Your first run only has lice from 2017, so temperature normals only start in 2020. Rerun the whole index when the 2012–2016 lice lands, before the bins, the nowcast and the panel.
- **Check:** plot the national `treat_rate` for 2024–2025. If it jumps at 2024-W46 (when the lice-report format changed), tell your human before using treatments after that date.
- Write `lice_area_week`, `lice_national_week` and `lice_area_month`, with the contract's columns.

### 4. The trap: `analysis/trap.py` → `trap.json` (by 23:30)

- Use the national weekly series from 2017-W01, with `lice` = `log1p(mobile_idx)` and `price` = `log(price_nok_kg)`.
- `raw_r` is the Pearson correlation of the two raw series. `anom_r` is the correlation of their anomalies, fitted on the full sample, over the same weeks.
- Report whatever the numbers are. The expected story is a large raw correlation and a much smaller anomaly correlation, but don't tune toward it.

### 5. Count × weight bins: `channels.json` → `bins` (by 01:30)

- Use area-months for areas 1–13.
- **Lice:** split `mobile_anom` at month t into terciles. The outcome is the mean of `count_anom` and `weight_anom` over months t to t+3, the H1 window.
- **Temperature:** split `dd_below14` at month t into terciles. The outcome is the mean over t+1 to t+3, the H2 window.
- Write one row per driver (lice, temp) and tercile (1–3), with the window, `count_anom`, `weight_anom` and `n`.

### 6. Nowcast backtest: `analysis/nowcast.py` → `nowcast.json` (by 01:30)

- The unit is area a (1–13) and target month m.
- The forecast date D(m) is the 10th of month m + 1. Use BarentsWatch and Statistics Norway rows with `available_at` ≤ D(m), and Directorate months up to m − 1.
- Work in anomaly space with past-only fits (`fit_end` = month m − 1). Then add back L_m and the season to get log predictions.
- **Models** (pooled OLS across areas, with statsmodels):
  - **B0:** `biomass_anom` and `fish_stock_anom` at m − 1.
  - **B1:** B0 plus the national export-volume anomaly for month m. That's the sum of fresh `volume_t` over ISO weeks whose Thursday falls in m, as a monthly anomaly with `fit_end` = m − 1.
  - **Bio:** B1 plus `mobile_anom`, `treat_anom`, `dd_below8`, `dd_8to14` and `dd_above14` at m and m − 1, all at area level.
- **Walk forward:** run m from 2021-01 to 2026-09, refitting everything each month and training on all area-months before m.
- **Outcomes:** log `harvest_count` and log `avg_kg`.
- **Scores:** the MAE of the log outcomes per model, pooled across all areas, per area, and for the national total (the sum of the area predictions). Note in the JSON that the actuals are today's revised data, not first releases.

### 7. H1/H2 panel: `analysis/channels.py` → `channels.json` → `panel` (01:30–03:30)

- Use `area_month_panel` from Oct 2017 to Sep 2026, areas 1–13. Take lags within each area.
- **H1 model:** `count_anom` (and, separately, `weight_anom`) on:
  - `mobile_anom` at lags 0–3;
  - `treat_anom` at lags 0–3;
  - `dd_below8`, `dd_8to14` and `dd_above14` at lags 0–3;
  - controls: `biomass_anom` and `fish_stock_anom` at t − 4.
- **H2 model (temperature only):** the same outcome on `dd_below14` and `dd_above14` at lags 0–3, plus the same controls, with no lice or treatment terms.
- **Effects:** `PanelOLS(y, X, time_effects=True, other_effects=<area × calendar-month code>, drop_absorbed=True)` from linearmodels, indexed by (area, month as a timestamp).
- **Errors:** `.fit(cov_type="kernel", kernel="bartlett", bandwidth=12)`, which gives Driscoll–Kraay errors.
- **Each tested sum:** s is the sum of the coefficients over the lag window and se = sqrt(1ᵀ V 1) from the matching covariance block. The 95% interval is s ± 1.96 se.
- **Pass rules,** exactly as in `prereg/PASS_MARKS.md`:
  - H1 passes only if the mobile-lice sum over lags 0–3 is above zero for count *and* below zero for weight, with both intervals excluding zero.
  - H2 passes if the `dd_below14` sum over lags 1–3 is above zero for weight, with its interval excluding zero.
- **Also report, without a pass mark:** the treatment sums and H2's count result.
- **Only if there's time,** and labelled as sensitivity checks: adult females instead of mobile lice; a smolt-release control (it cuts the sample to Oct 2019 onward); a wild cluster bootstrap by area.

### 8. Sealed October nowcast (by 03:45)

- Run the nowcast for m = 2026-10 with D = now. That means Directorate data to 2026-09, lice to the latest week available, and Statistics Norway to 2026-W44.
- **Model rule, fixed now:** for each outcome, use Bio if its backtest MAE is lower than B1's, otherwise B1.
- **Intervals:** the 10th and 90th percentiles of that model's pooled walk-forward errors, applied in log space.
- **Write `predictions/2026-10_harvest_by_area.json`** with:
  - `target`;
  - `made_at` (ISO format, Europe/London time);
  - `model` for each outcome;
  - `areas`: a list of {`area`, `count`, `count_lo`, `count_hi`, `avg_kg`, `avg_kg_lo`, `avg_kg_hi`};
  - `national`: summed counts and the harvest-weighted average weight.
- Commit that file on its own and push. Then put that commit's hash (`git rev-parse HEAD` straight after the commit) into `nowcast.json` → `sealed`, and push again. All of this before 04:00.

### 9. Freeze at 04:00

Write pass or fail into `channels.json`, and write `analysis/RESULTS.md` with each hypothesis, its numbers and whether it passed. Push, and tell your human. After that, only fix bugs that break files.

## Who is waiting on you

| What | Who | By |
| --- | --- | --- |
| `analysis/anomalies.py` | Price | 18:30 |
| `lice_national_week.parquet` | Price | 22:30 |
| `area_month.json`, `trap.json` | Data (charts), Front end | 23:30 |
| `channels.json` bins, `nowcast.json` backtest | Data (charts), Front end | 01:30 |
| `channels.json` panel, sealed October nowcast | Data, Front end | 04:00 |

## Ask your human when

- something would change a pass mark (never change one yourself);
- the anomalies still show a trend or a season;
- the treatment series breaks at 2024-W46;
- the panel won't fit, for example because a regressor is fully absorbed by the effects. Report it rather than redesigning the test.
