# Shared contract: read this first

For: every coding agent on the team (Data, Production, Price, Front end). Your human also gives you one role plan from this folder. This file is the single source of truth for paths, schemas, driver definitions, the holdout rule and deadlines. If your role plan disagrees with it, this file wins; tell your human.

## The project

HackTheBurgh XIII, Edinburgh: a 24-hour hackathon ending on Sunday 8 November 2026, with submissions assumed around 11:00 and judging on Sunday. The theme is "make something previously invisible visible, and predict something".

Norway farms just over half the world's Atlantic salmon and publishes almost everything that happens in its sea cages. We use that public data to forecast two things:

1. **Production, the headline.** Monthly harvest in each of Norway's 13 production areas: volume (kg), split into fish count × average weight. The key forecast is a nowcast of the month just ended, made on the 10th of the next month, before the Directorate of Fisheries publishes it around the 20th.
2. **Price, secondary.** The weekly export price of fresh salmon (Statistics Norway table 03024), 2–8 weeks ahead, against a random walk.

The forecasts use many drivers: stock (biomass, fish numbers), the smolt pipeline, growth (feed, sea temperature), losses (deaths, disease), sea lice and treatments, and the market (export volume, exchange rates). We also measure which drivers matter.

Why the count × weight split matters: fast growth gives more and bigger fish, while early harvests forced by lice, disease or deaths give more but smaller fish. Only the split tells the two apart.

**The proof is a backtest judges can see on Sunday.** It replays real time from 2021, keeps a locked holdout that is scored once at 04:00, and shows September 2026 (the newest published month) as a worked example. Nothing in this project depends on figures published after the event.

What we ship: a hosted static website that shows the findings, plus this public repo. There's no live server; everything is precomputed into files under `web/public/`.

The pre-registered tests are in `prereg/PASS_MARKS.md`. They are F1 (production forecast, primary), F2 (price forecast), the mechanism tests M1 and M2 (with M3 exploratory) and an exploratory driver ranking. That file is committed before any model runs on real outcome data, and nobody edits it afterwards.

## Roles and ownership

| Role | Owns | Role plan |
| --- | --- | --- |
| Data | `pipeline/`, `charts/__init__.py`, `charts/production_charts.py`, the Data tables in `data/processed/`, `web/public/data/farms.json`, `web/public/data/farm_weeks/`, the production chart specs, `README.md`, `requirements.txt`, `.gitignore`, `.env.example` | `data.md` |
| Production | `analysis/`, the Production tables in `data/processed/`, `web/public/data/{area_month,trap,channels,nowcast,drivers}.json` | `production.md` |
| Price | `price/`, `charts/theme.py`, `charts/price_charts.py`, `data/processed/price_backtest.parquet`, `web/public/data/price.json`, the price chart specs | `price.md` |
| Front end | `web/`, except the back-end files in `web/public/data/` and `web/public/charts/`; `web/public/data/_mock/` belongs to the front end | `frontend.md` |

Edit only what your role owns. If you need a change elsewhere, stop and tell your human, who will ask the owner. One exception: if you need a Python package that isn't in `requirements.txt`, add one line in its own commit and tell your human.

## Repo layout

```
docs/designs/          the team's design doc
docs/plans/            this file and the four role plans
prereg/PASS_MARKS.md   pre-registered tests (never edit)
pipeline/              Data: fetchers and cleaning
analysis/              Production: anomalies, driver tables, production findings
price/                 Price: price models and tests
charts/                Altair chart code (theme.py, production_charts.py, price_charts.py)
data/raw/              downloads (git-ignored)
data/processed/        cleaned tables as Parquet (committed)
web/                   the site (Front end)
web/public/data/       findings JSON (back end writes, front end reads)
web/public/charts/     Vega-Lite chart specs (back end writes, front end reads)
```

## Conventions

- **Python:** 3.11 or newer, with one virtualenv at `.venv`, installed with `pip install -r requirements.txt`. Run scripts from the repo root as modules, for example `python -m pipeline.fetch_directorate`. Every script can be rerun and overwrites its own outputs.
- **Weeks:** ISO weeks written `YYYY-Www` (for example `2026-W44`). Use `date.isocalendar()` and `date.fromisocalendar()`. A week belongs to the month that contains its Thursday. 2020 and 2026 have a week 53.
- **Months:** written `YYYY-MM`.
- **Dates:** store date columns in Parquet as pandas `datetime64[ns]` at midnight.
- **Areas:** integers 1–13. Area `0` is the Directorate's `(null)` row of suppressed data. Include it in national totals and exclude it from anything done by area.
- **Publication dates.** Every processed table except `farms.parquet` (a static lookup) has an `available_at` date: the first day the row was public. A forecast made on date D may only use rows with `available_at <= D`.
  - BarentsWatch farm data for week w: the Sunday ending week w + 1.
  - Statistics Norway week w: the Wednesday of week w + 1.
  - Directorate month m: the 20th of month m + 1.
  - Exchange rates for day d: d + 1.
- **Holdout rule.** Production's backtest develops on 2021-01 to 2024-12, with a holdout of 2025-01 to 2026-09. Price's develops on 2021-W01 to 2024-W52, with a holdout of 2025-W01 to 2026-W44.
  - Backtest code scores only the development window by default.
  - A `--final` flag runs the full window. It is run once, at the 04:00 freeze.
  - Nobody computes or looks at holdout results before then.
  - F1 and F2 are judged on the holdout.
- **Missing farm weeks stay missing, never zero.** Below 4 °C, lice are counted only every second week.
- **Site JSON:** UTF-8. Write `NaN` as `null` by converting it to `None`, then calling `json.dump(..., allow_nan=False)`. Round lice and temperature to 2 decimals, and other measured values to 4 significant figures. Never round IDs, area numbers or years.
- **Charts:** use Altair 5, saved as Vega-Lite v5 JSON with the data inlined (`alt.data_transformers.disable_max_rows()`, then `chart.to_json()`) at `web/public/charts/<name>.vl.json`. Build charts only from the findings JSON, so the charts and the site always agree, and use the theme in `charts/theme.py`.
- **Secrets:** the BarentsWatch credentials exist only in `.env` on the Data laptop. Never commit `.env`, tokens or `data/raw/`.
- **Sources:** download only from the sources named in the role plans. Ask your human before adding any other source.

## Drivers: one definition for everyone

`anomaly(x, freq, transform="log", fit_end=None, K=3)` lives in `analysis/anomalies.py` (owned by Production; `freq` is `"W"` or `"M"`, `transform` is `"log"`, `"log1p"` or `"none"`). It takes logs (or `log1p`, or no transform), subtracts a trailing 12-month level (52 weeks for weekly series), then removes Fourier seasonality and holiday terms.

| Columns | Definition | Levels | Source |
| --- | --- | --- | --- |
| `biomass_kg`, `biomass_anom` | Standing biomass; anomaly of its log | area-month, national-month | Directorate |
| `fish_stock`, `fish_stock_anom` | Fish in the sea; anomaly of its log | area-month, national-month | Directorate |
| `smolt_pipe`, `smolt_pipe_anom` | `log1p` of smolt released over months m − 23 to m − 12; its anomaly (no extra transform) | area-month, national-month | Directorate |
| `feed_rate`, `feed_rate_anom` | `feed_kg / biomass_kg`; anomaly of its log | area-month, national-month | Directorate |
| `mortality`, `mortality_anom` | Deaths per 1,000 fish (`1000 × dead / fish_stock`); anomaly of its `log1p` | area-month, national-month | Directorate |
| `mobile_idx`, `mobile_anom` | Capacity-weighted mean mobile lice per fish over reporting farms; anomaly of its `log1p` | area-week, national-week, monthly means | BarentsWatch |
| `treat_rate`, `treat_anom` | Share of reporting farm-weeks with a delousing treatment (a farm-week with any treatment counts once; this is the pass marks' "treatments per active farm-week"); anomaly of `log1p(100 × rate)` | the same | BarentsWatch |
| `disease_share` | Share of reporting sites flagged with ISA or PD that week (suspected and confirmed both count); no anomaly. Null everywhere if BarentsWatch has no disease flags | the same | BarentsWatch |
| `temp_c`, `dd_anom`, `dd_below8`, `dd_8to14`, `dd_above14`, `dd_below14` | Capacity-weighted sea temperature, the degree-day anomaly and its bands, exactly as in `prereg/PASS_MARKS.md` | the same | BarentsWatch |
| `export_vol`, `export_vol_anom` | Fresh export tonnes summed over ISO weeks whose Thursday is in the month; anomaly of its log. The weekly version `v_anom`, built by Price from `volume_t` | national-month | Statistics Norway |
| `eurnok_chg`, `usdnok_chg` | Weekly log change of the weekly mean rate (built by Price) | national-week | Norges Bank |

- **National Directorate drivers** are ratios of national sums (for example, the sum of `feed_kg` divided by the sum of `biomass_kg`) over areas 0–13.
- **National BarentsWatch indices** are capacity-weighted over all reporting farms in Norway, not averages of areas.
- **Stored anomaly columns are full-sample fits, for in-sample analysis only** (the trap, the bins, M1, M2). Forecasting code (the nowcast and the price models) must recompute anomalies from the level columns, with `fit_end` set to the forecast date.

**Driver groups,** used by the driver ranking:

| Group | Columns |
| --- | --- |
| stock | `biomass_anom`, `fish_stock_anom` |
| market | `export_vol_anom` (Price's optional ranking adds `usdnok_chg` here) |
| pipeline | `smolt_pipe_anom` |
| feed | `feed_rate_anom` |
| temperature | `dd_below8`, `dd_8to14`, `dd_above14` |
| losses | `mortality_anom`, `disease_share` |
| lice | `mobile_anom`, `treat_anom` |

## Git rules

- Work on `main`. Run `git pull --rebase` before every push, and commit small and often.
- Commit `data/processed/*.parquet` so the others can use them. Keep each file under about 50 MB, and never commit `data/raw/`.
- No model runs on real outcome data until `prereg/PASS_MARKS.md` is on GitHub. Check with `git log origin/main -- prereg/PASS_MARKS.md`.

## Processed tables (`data/processed/`, Parquet)

| File | Owner | Due | Columns |
| --- | --- | --- | --- |
| `directorate_area_month.parquet` | Data | 18:30 | `area` int 0–13, `month` str, `harvest_count` int, `harvest_kg` float, `avg_kg` float (null when there's no harvest), `biomass_kg` float, `fish_stock` int, `smolt_released` int, `dead` int, `feed_kg` float, `available_at` date |
| `ssb_weekly.parquet` | Data | 18:30 | `week` str, `week_start` date (Monday), `price_nok_kg` float, `volume_t` float, `available_at` date. Fresh salmon only |
| `fx_daily.parquet` | Data | 18:30 | `date` date, `eurnok` float, `usdnok` float, `available_at` date |
| `farms.parquet` | Data | 21:30 | `locality_no` int, `name` str, `lat` float, `lon` float, `area` int 1–13, `capacity_t` float (null if unknown) |
| `farm_week.parquet` | Data | 21:30 for 2017 onward; 23:30 for 2012–2016 | `locality_no` int, `week` str, `week_start` date, `area` int, `reported` bool, `adult_female` float, `mobile` float, `stationary` float, `treated` bool, `treat_types` str (as reported, comma-separated), `sea_temp_c` float (cleaned), `fallow` bool, `isa` bool, `pd` bool (null if not available), `available_at` date |
| `drivers_area_month.parquet` | Production | 21:30 for the Directorate drivers; 23:30 complete | `area`, `month`, the level and anomaly columns for every driver above, `available_at_dir`, `available_at_bw` |
| `drivers_national_month.parquet` | Production | 23:30 | `month`, the same columns at national level (including `available_at_dir` and `available_at_bw`), plus `export_vol` and `export_vol_anom` |
| `weekly_area_index.parquet` | Production | 22:30; rerun at 23:30 | `area`, `week`, `mobile_idx`, `mobile_anom`, `treat_rate`, `treat_anom`, `disease_share`, `temp_c`, `dd_anom`, `dd_below8`, `dd_8to14`, `dd_above14`, `dd_below14`, `n_reporting`, `available_at` |
| `weekly_national_index.parquet` | Production | 22:30; rerun at 23:30 | `week`, plus the same columns as `weekly_area_index` |
| `area_month_panel.parquet` | Production | 23:30 | `area`, `month`, `harvest_count`, `harvest_kg`, `avg_kg`, `count_anom`, `weight_anom`, `volume_anom`, plus every column of `drivers_area_month` |
| `price_backtest.parquet` | Price | 03:00 (development window); 04:00 (full) | `origin_week`, `h`, `model`, `window`, `y`, `y_hat`, `error` |

## Findings for the site (`web/public/data/`)

All numbers in these examples are placeholders, not expected results.

**`farms.json`** (Data, 21:30)

```json
[{"id": 12345, "name": "Example site", "lat": 63.1, "lon": 8.2, "area": 6, "capacity_t": 3120}]
```

**`farm_weeks/index.json` and `farm_weeks/{year}.json`**, one per year 2019–2026 (Data, 21:30)

- In each year file, `mobile[i][j]` is week `weeks[i]` at farm `ids[j]`.
- `null` means no report.
- `disease` is included only if BarentsWatch has the flags: 1 = ISA or PD (suspected or confirmed), 0 = neither, `null` = no report.

```json
{"years": [2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026]}
```

```json
{"year": 2024,
 "weeks": ["2024-W01", "2024-W02"],
 "ids": [12345, 23456],
 "mobile": [[0.42, null], [0.51, 0.08]],
 "treated": [[0, null], [1, 0]],
 "disease": [[0, null], [0, 1]],
 "temp": [[7.85, null], [7.6, 6.9]]}
```

**`area_month.json`** (Production, 23:30)

```json
[{"area": 6, "month": "2024-09", "kg": 17700000, "count": 4100000, "avg_kg": 4.31,
  "volume_anom": 0.07, "count_anom": 0.12, "weight_anom": -0.05,
  "mobile_idx": 0.61, "dd_anom": 14.2, "feed_rate_anom": 0.03, "mortality_anom": 0.1}]
```

**`trap.json`** (Production, 23:30)

- For each weekly national driver, `raw_r` is its correlation with log price, and `anom_r` is the correlation of their anomalies.
- `series` is for the `highlight` driver.

```json
{"from": "2017-W01", "to": "2026-W44", "highlight": "mobile_idx",
 "drivers": [{"driver": "mobile_idx", "label": "Mobile lice per fish", "raw_r": -0.6, "anom_r": -0.1},
             {"driver": "temp_c", "label": "Sea temperature", "raw_r": -0.7, "anom_r": 0.05}],
 "series": [{"week": "2024-W36", "driver": 0.9, "price": 4.2, "driver_anom": 0.1, "price_anom": -0.03}]}
```

**`channels.json`** (Production: `bins` by 01:30, `panel` by 04:00)

- Bin drivers: `lice`, `temp`, `feed`, `mortality`.
- Panel rows with `"pass": null` are reported without a pass mark.

```json
{"bins": [{"driver": "lice", "tercile": 3, "window": "0-3", "count_anom": 0.04, "weight_anom": -0.02, "n": 310}],
 "panel": [{"test": "M1", "outcome": "log_count", "driver": "mobile_lice", "lags": "0-3",
            "coef_sum": 0.03, "lo": 0.01, "hi": 0.05, "pass": true}]}
```

**`nowcast.json`** (Production: the development window by 01:30; the holdout, `f1` and `latest` at the 04:00 freeze). Before the freeze, `scores.holdout`, `f1` and `latest` are `null`, and there are no holdout rows in `backtest`.

```json
{"models": ["b0", "b1", "drivers"],
 "windows": {"dev": ["2021-01", "2024-12"], "holdout": ["2025-01", "2026-09"]},
 "backtest": [{"area": 6, "month": "2024-09", "window": "dev", "made_on": "2024-10-10",
               "actual": {"kg": 17700000, "count": 4100000, "avg_kg": 4.31},
               "pred": {"b0": {"kg": 16900000, "count": 3900000, "avg_kg": 4.5},
                        "b1": {"kg": 17200000, "count": 4000000, "avg_kg": 4.45},
                        "drivers": {"kg": 17500000, "count": 4050000, "avg_kg": 4.36}}}],
 "scores": {"dev": {"log_kg": {"b0": 0.2, "b1": 0.17, "drivers": 0.15},
                    "log_count": {"b0": 0.21, "b1": 0.18, "drivers": 0.17},
                    "log_avg_kg": {"b0": 0.06, "b1": 0.06, "drivers": 0.05}},
            "holdout": null,
            "actuals": "latest revised data, not first releases"},
 "f1": null,
 "latest": null,
 "current": null}
```

After the freeze:

```json
{"f1": {"window": "holdout", "mae_b1": 0.17, "mae_drivers": 0.15, "improvement_pct": 11.8,
        "cw_stat": 2.1, "cw_p": 0.02, "pass": true},
 "latest": {"month": "2026-09", "made_on": "2026-10-10", "model": "drivers",
            "national": {"pred_kg": 180000000, "actual_kg": 184000000, "error_pct": -2.2},
            "areas": [{"area": 6, "pred_kg": 17500000, "actual_kg": 17700000, "error_pct": -1.1}]}}
```

National figures (in `latest` and in national charts) are sums over areas 1–13. The `(null)` row is left out, and chart labels say so.

`current` is optional (Tier 3): an October 2026 nowcast made from data available now, labelled as unverifiable before the event ends.

**`drivers.json`** (Production, 04:00). This is the driver ranking for the Drivers model: the rise in walk-forward MAE over 2021-01 to 2026-09 when each group is left out, computed at the freeze.

```json
{"outcome": "log_kg", "window": "2021-01 to 2026-09", "full_mae": 0.15,
 "groups": [{"group": "lice", "label": "Lice and treatments", "columns": ["mobile_anom", "treat_anom"],
             "mae_without": 0.16, "increase_pct": 6.7}],
 "by_outcome": {"log_count": [{"group": "lice", "increase_pct": 8.0}],
                "log_avg_kg": [{"group": "lice", "increase_pct": 3.1}]}}
```

**`price.json`** (Price: the development window by 03:00; the holdout, `f2` and `backtest_h4` at the 04:00 freeze)

```json
{"history": [{"week": "2026-W44", "price_nok_kg": 70.0}],
 "c1_drivers": ["mobile_anom", "treat_anom", "dd_below8", "biomass_anom"],
 "windows": {"dev": ["2021-W01", "2024-W52"], "holdout": ["2025-W01", "2026-W44"]},
 "notes": ["disease_share dropped from c1: no disease flags in BarentsWatch"],
 "scorecard": [{"window": "dev", "h": 4, "model": "c1", "mae": 0.06, "mae_ratio": 0.97, "hit_rate": 0.55}],
 "cw": [{"window": "dev", "h": 4, "stat": 1.2, "p": 0.11, "p_holm": null, "primary": true}],
 "by_year": [{"year": 2024, "mae_c0": 0.07, "mae_c1": 0.068}],
 "f2": null,
 "backtest_h4": null,
 "current": null}
```

After the freeze, holdout rows are added to `scorecard` and `cw`, and:

```json
{"f2": {"window": "holdout", "mae_c0": 0.063, "mae_c1": 0.061, "cw_p": 0.11, "pass": false},
 "backtest_h4": [{"week": "2025-W10", "actual": 85.0, "pred_c0": 83.0, "pred_c1": 84.0,
                  "band_model": "c0", "p10": 78.0, "p90": 90.0}]}
```

- `backtest_h4` gives, for every holdout target week, the forecasts made four weeks earlier, in NOK/kg.
- `p10` and `p90` come from the development-window errors of `band_model`: c1 if F2 passed, otherwise c0.
- `current` (optional, Tier 3) is the next 8 weeks from the latest week, labelled as unverifiable before the event ends.

## Chart specs (`web/public/charts/`)

| File | Owner | Due | Shows |
| --- | --- | --- | --- |
| `trap.vl.json` | Data | 00:00 | Each driver's raw and anomaly correlation with price, plus the highlighted driver's series |
| `channels_bins.vl.json` | Data | 02:00 | Count and weight anomalies by tercile, for lice, temperature, feed and deaths |
| `nowcast_backtest.vl.json` | Data | 02:00 for the development window; 05:00 with the holdout | Error by model in each window for volume, count and weight; national actual against the Drivers nowcast over time, with the holdout marked and September 2026 called out |
| `drivers_importance.vl.json` | Data | 05:00 | The rise in nowcast error without each driver group |
| `channels_panel.vl.json` | Data | 05:00 | M1 and M2 coefficient sums with 95% intervals |
| `price_scorecard.vl.json` | Price | 04:00 | Error relative to the random walk by horizon, for each window |
| `price_by_year.vl.json` | Price | 04:00 | c0 against c1 error by year, at 4 weeks |
| `price_backtest.vl.json` | Price | 04:00 | Actual price against the 4-week-ahead forecasts over the holdout, with an 80% band |
| `price_fan.vl.json` | Price | Optional | The current 8-week forecast (Tier 3) |

## The September 2026 example and current forecasts

- `nowcast.json` → `latest` is the worked example for judges. It shows the September 2026 nowcast as it would have been made on 10 October 2026, set against the Directorate's published figure, nationally and by area. It's part of the holdout, so it's filled in at the freeze.
- Current forecasts are optional Tier 3, in the `current` keys: the October 2026 harvest and the next 8 weeks of price. They can't be checked before judging, so they never replace the backtest.

## Timeline (local time, Saturday 7 to Sunday 8 November)

| Time | What must exist |
| --- | --- |
| 18:00 | `prereg/PASS_MARKS.md` on GitHub |
| 18:30 | Directorate, Statistics Norway and exchange-rate tables; `analysis/anomalies.py`; an empty hosted site |
| 21:30 | **Check 1:** `farm_week.parquet` from 2017 with temperature and treatments; `farms.json` and `farm_weeks/`; the chart theme; the Directorate drivers in `drivers_area_month.parquet` |
| 22:30 | Weekly national and area indices, for Price |
| 23:30 | 2012–2016 farm data; indices rerun; complete driver tables; `area_month.json` and `trap.json` |
| 01:30 | **Check 2:** findings 1–4 on the development window: `channels.json` bins and the `nowcast.json` backtest as JSON. Their charts follow by 02:00 |
| 04:00 | **Analysis freeze:** each backtest runs once with `--final` (holdout included). F1, F2, M1 and M2 are recorded as pass or fail, plus `drivers.json` and `nowcast.json` → `latest` |
| 08:00 | **Code freeze:** the hosted site shows every finding that exists |
| 10:30 | Submitted |

After the analysis freeze, results don't change. Only fix bugs that break files.

## Ask your human when

- anything would change this contract or a pass mark;
- a data source fails, or a field the contract needs doesn't exist;
- you're about to miss a deadline in the timeline;
- a decision about how the site looks comes up, because the team decides that.
