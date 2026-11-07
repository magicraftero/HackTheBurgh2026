# Role plan: Price (back end)

For: the coding agent working with the Price person. Read `docs/plans/00-shared.md` first, then F2 in `prereg/PASS_MARKS.md`. Your test must match F2 exactly.

## Your job

Production is the project's headline forecast, and price is the second. Build forecasts of the weekly export price of fresh salmon, 2–8 weeks ahead. Then run test F2: do the drivers (sea lice, treatments, disease, sea temperature, biomass, feed, deaths and USD/NOK) reduce 4-week-ahead error when you add them to a model that already has past prices, export volume, harvest weight and EUR/NOK? F2 is judged on a locked holdout, 2025-W01 to 2026-W44, at h = 4, with development-window results alongside. You also produce the price findings (including `backtest_h4`, the holdout forecasts against actual prices), the price charts, and the shared chart theme that every chart uses.

## Inputs

You download nothing. Every input is a file in the repo.

- **From Data, at 18:30, in `data/processed/`:**
  - `ssb_weekly.parquet`: `price_nok_kg` and `volume_t` for each ISO week, fresh salmon only;
  - `fx_daily.parquet`: daily `eurnok` and `usdnok`;
  - `directorate_area_month.parquet`: `harvest_kg` and `harvest_count` for each area and month, for the national average weight.
- **From Production:**
  - `analysis/anomalies.py` at 18:30. If it's late, write a stand-in in `price/` that does what the contract's Drivers section describes: log, `log1p` or no transform; a trailing 12-month or 52-week level; Fourier and holiday terms; and a `fit_end` argument. Switch to the real one when it lands.
  - `data/processed/weekly_national_index.parquet` at 22:30 for 2017 onward, rerun at 23:30 with Data's 2012–2016 farm data. You use `week`, `mobile_idx`, `treat_rate`, `disease_share`, `dd_below8`, `dd_8to14`, `dd_above14` and `available_at`. Only c1 needs it.
  - `data/processed/drivers_national_month.parquet` at 23:30. You use `month`, `biomass_kg`, `feed_rate`, `mortality` and `available_at_dir`. Only c1 needs it.
    - Until it lands, build the same three levels from `directorate_area_month.parquet` with the contract's national formulas, summing over areas 0–13: `biomass_kg` = Σ `biomass_kg`, `feed_rate` = Σ `feed_kg` ÷ Σ `biomass_kg`, and `mortality` = 1000 × Σ `dead` ÷ Σ `fish_stock`. Switch to Production's table when it lands.

## Who is waiting on you

- **Data, at 21:30 (Check 1):** `charts/theme.py`. Data's production charts use it, and the first one, `trap.vl.json`, is due at 00:00.
- **Front end:** `web/public/data/price.json`, with the development window by 03:00 and the holdout, `f2` and `backtest_h4` at the 04:00 freeze; and the three price chart specs in `web/public/charts/` by 04:00. The front end builds against its own mocks until then, so use the contract's keys exactly.

## Tasks, in order

### 1. Chart theme: `charts/theme.py` (by 21:30)

- `register()` registers and enables an Altair theme named `lice`, with:
  - a system sans-serif font;
  - text sizes that read on a projector;
  - a light grid;
  - `width="container"` and a height of 300.
- Export a `PALETTE` dict so colours mean the same thing everywhere. Use the contract's names as keys:
  - the models: `rw`, `ar`, `c0`, `c1`, `b0`, `b1` and `drivers`;
  - the seven driver groups from the contract's group table: `stock`, `market`, `pipeline`, `feed`, `temperature`, `losses` and `lice`;
  - `count` (fish count), `avg_kg` (average weight) and `actual` (observed values).
- If Data asks for another key, add it. Data can't edit this file.
- Keep it plain and neutral. The team decides the site's look later, so all styling must live in this one file.
- Check your Altair version: 5.5 and later use `alt.theme.register`; older versions use `alt.themes.register` and `alt.themes.enable`.
- Push early and tell your human, so Data can use the theme.

### 2. Weekly dataset: `price/dataset.py` (c0 inputs by 19:30)

- One row per ISO week t, with:
  - p_t = log `price_nok_kg`;
  - v_t = log `volume_t`;
  - the weekly means of daily `eurnok` and `usdnok` (Monday to Sunday), and their weekly log changes, `eurnok_chg` and `usdnok_chg`;
  - the national average weight for each month = Σ `harvest_kg` ÷ Σ `harvest_count` over areas 0–13.
- Add the c1 inputs when Production's tables land, at 22:30 and 23:30.
- **Forecast origin:** for week t, this is the Wednesday of week t + 1, when Statistics Norway publishes week t. It equals week t's `available_at` in `ssb_weekly.parquet`. Origins are named by week t, as in `origin_week`. At that origin you may use only rows that were public by then:
  - price and volume up to week t;
  - exchange rates up to the day before;
  - the latest Directorate month with `available_at` ≤ origin. In `drivers_national_month.parquet` the column is `available_at_dir`; if it's missing, use the 20th of month m + 1;
  - BarentsWatch weeks with `available_at` ≤ origin, which in practice means up to week t − 1.
- **Anomalies, past-only.** At each origin:
  1. keep only the rows that were public by the origin date;
  2. call `anomaly()` on each level series in the table below with `fit_end` = the origin date, fitting weekly series on weekly rows and monthly series on monthly rows;
  3. for every week s up to t, take the values at the latest week or month that was public at s's own origin.

| Feature | Level column | Table | Transform | Series |
| --- | --- | --- | --- | --- |
| `v_anom` | `volume_t` | `ssb_weekly` | log | weekly |
| national average-weight anomaly (c0) | Σ `harvest_kg` ÷ Σ `harvest_count`, areas 0–13 | `directorate_area_month` | log | monthly |
| `mobile_anom` | `mobile_idx` | `weekly_national_index` | `log1p` | weekly |
| `treat_anom` | 100 × `treat_rate` | `weekly_national_index` | `log1p` | weekly |
| `biomass_anom` | `biomass_kg` | `drivers_national_month` | log | monthly |
| `feed_rate_anom` | `feed_rate` | `drivers_national_month` | log | monthly |
| `mortality_anom` | `mortality` | `drivers_national_month` | `log1p` | monthly |

- **Used as stored, with no refit:**
  - `disease_share` has no anomaly.
  - `dd_below8`, `dd_8to14` and `dd_above14` are past-only by definition: the temperature normal uses only previous years, and the 6-week sum looks back. Check once in Production's code in `analysis/` that the normal uses only earlier years. If it uses all years, tell your human before you use the bands.
- **If `disease_share` is null in every row** (BarentsWatch has no disease flags), drop it from c1. Check this when the index lands at 22:30.

### 3. Models: `price/models.py`, direct for each horizon h = 1 to 8

The target is y = p_{t+h} − p_t. Fit each model with `sm.OLS(y, X).fit()` (`import statsmodels.api as sm`), with a constant column in X, and forecast with `res.predict(X_new)`.

- **rw:** ŷ = 0.
- **ar:** OLS of y on a constant, Δp_t to Δp_{t−p+1}, sine and cosine Fourier terms (K = 3) of the target week, and Easter and Christmas dummies for the target week. Choose p (1 to 8) for each h by BIC (`res.bic`, with every p fitted on the same rows), using only origins from 2012–2018, and then keep it fixed. c0 and c1 use the same p.
- **c0:** ar plus `v_anom` at t and t − 1, plus the latest available national average-weight anomaly, plus `eurnok_chg` at t and t − 1. F2 in `prereg/PASS_MARKS.md` fixes c0, so don't add anything to it.
- **c1:** c0 plus the drivers below. L is the latest BarentsWatch week public at the origin, and M is the latest Directorate month released by then.
  - `mobile_anom` and `treat_anom` at L and L − 1;
  - `disease_share`, `dd_below8`, `dd_8to14` and `dd_above14` at L;
  - `biomass_anom`, `feed_rate_anom` and `mortality_anom` at M;
  - `usdnok_chg` at t and t − 1.
- **`c1_drivers`:** the list for `price.json`. Give c1's added columns by their contract names, each once, without lag suffixes, in the order above: `["mobile_anom", "treat_anom", "disease_share", "dd_below8", "dd_8to14", "dd_above14", "biomass_anom", "feed_rate_anom", "mortality_anom", "usdnok_chg"]`. If you dropped `disease_share`, leave it out. Also add a line to `price.json` → `notes` saying so. Say it in `price/RESULTS.md` too.
- **Training window:** all models share one expanding window. It starts at the first origin where every c1 feature exists.
  - The weekly BarentsWatch features exist from about 2015, because temperature normals need three previous years. Between 22:30 and the 23:30 rerun the index starts in 2017, so develop c1 on later years.
  - The Directorate features start later. c0's average weight and c1's three monthly drivers come from Directorate data that begins in October 2017, and each anomaly needs a trailing 12-month level. So the first complete origin will be late 2017 at the earliest, and more likely late 2018 or after, which is why the development window starts at 2021-W01.
  - Until the c1 inputs land, develop rw, ar and c0 from the first origin where every c0 feature exists. Tell your human that date as soon as you have it.
  - After the 23:30 rerun, print the first complete origin, the feature that starts last, and the number of h = 4 training rows for the first development forecast (target week 2021-W01), and tell your human. The windows are already fixed in PASS_MARKS, so carry on without waiting.

### 4. Walk-forward backtest: `price/backtest.py` (development window by 03:00; full run at 04:00)

- **Windows,** set by the target week t + h: development 2021-W01 to 2024-W52, holdout 2025-W01 to 2026-W44. Use the target week, not the origin, so no development score uses a 2025 price.
- By default the script forecasts and scores only development rows. `python -m price.backtest --final` runs the full window. Run it once, at the 04:00 freeze. Before then, don't compute, print or plot any holdout row.
- At origin t, train only on rows s with s + h ≤ t, because each row's target, p_{s+h} − p_s, must already be published.
- Use the same rows for every model. Train on rows where every c1 feature exists. If a c1 feature is null at a scored origin, skip that origin for every model and count the skips in `price/RESULTS.md`. Never fill a missing feature with zero.
- Refit at every origin, since OLS is fast. If that's too slow, refit every 4 weeks and say so in `price/RESULTS.md`.
- Save every prediction and error to `data/processed/price_backtest.parquet`, with the columns `origin_week`, `h`, `model`, `window` (`"dev"` or `"holdout"`), `y`, `y_hat` and `error`, where `error` = `y` − `y_hat`.

### 5. Metrics and tests: `price/evaluate.py`

- **MAE:** in log points, for each window, model and h. `mae_ratio` = MAE ÷ the random walk's MAE.
- **`hit_rate`:** the share of origins where sign(ŷ) = sign(y), skipping ŷ = 0. It's null for the random walk.
- **Clark–West, c1 against c0** (c0 is nested in c1), in each window, at each h from 2 to 8:
  - f = e_c0² − (e_c1² − (ŷ_c0 − ŷ_c1)²), with the rows in origin order;
  - `res = sm.OLS(f, np.ones(len(f))).fit(cov_type="HAC", cov_kwds={"maxlags": h - 1})`, which gives Newey–West errors with h − 1 lags;
  - the one-sided p-value is 1 − Φ(t), computed as `scipy.stats.norm.sf(res.tvalues[0])`.
- **F2 is judged on the holdout.** It passes only if both hold on the holdout at h = 4: MAE_c1 ≤ 0.95 × MAE_c0, *and* the unadjusted Clark–West p < 0.05. Report the development-window numbers alongside. `f2` stays `null` until the `--final` run.
  - Mark the h = 4 row in `cw` with `primary: true`. On the holdout, its unadjusted `p` decides F2.
  - h = 4 is the primary test, and its unadjusted p-value decides F2. In each window, Holm-adjust the p-values of the other horizons (2, 3, 5, 6, 7 and 8) together with `statsmodels.stats.multitest.multipletests(p, method="holm")[1]`, put each in `p_holm`, and leave `p_holm` null at h = 4.
  - h = 1 is used only by the optional current forecast in task 8.
- **By year:** the MAE of c0 and c1 at h = 4 for each year the run scores (the ISO year of the target week).
- Only if there's time: a Pesaran–Timmermann test on the direction calls.

### 6. Holdout forecasts against actual prices: `backtest_h4` (at the 04:00 freeze)

- Write the code before the freeze and test it on development rows. Fill `backtest_h4` from the `--final` run.
- For every holdout target week T, take the c0 and c1 forecasts made 4 weeks earlier, at origin t = T − 4. Convert to NOK/kg: `pred_c0` = exp(p_t + ŷ_c0) and `pred_c1` = exp(p_t + ŷ_c1). `actual` is week T's `price_nok_kg`.
- `band_model` is c1 if F2 passed, otherwise c0. This rule is fixed now.
- **Band:** q10 and q90 = `np.quantile(error, [0.1, 0.9])` over `band_model`'s development-window rows at h = 4. Then `p10` = exp(p_t + ŷ + q10) and `p90` = exp(p_t + ŷ + q90), where ŷ is `band_model`'s forecast.

### 7. `price.json` and the price charts (by 04:00)

- Write `web/public/data/price.json` exactly as in the contract: `history` from 2017, `c1_drivers`, `windows`, `scorecard`, `cw`, `by_year`, `f2`, `backtest_h4` and `current`. The full schema is in `docs/plans/00-shared.md`.
  - By 03:00, write the development window, with `f2`, `backtest_h4` and `current` set to `null`.
  - At the freeze, add the holdout rows to `scorecard` and `cw`, and fill `f2` and `backtest_h4`. Leave `current` as `null` unless you do task 8.
- `charts/price_charts.py`, run as `python -m charts.price_charts`, builds each chart only from `price.json`, with the theme from task 1. It writes to `web/public/charts/`:
  - `price_scorecard.vl.json`: MAE relative to the random walk by horizon for ar, c0 and c1, for each window, with a reference line at 1.0.
  - `price_by_year.vl.json`: c0 against c1 error at 4 weeks, by year.
  - `price_backtest.vl.json`: actual price against the c0 and c1 forecasts over the holdout, with the 80% band, all from `backtest_h4`.
- Write `price/RESULTS.md` with the numbers, the first origin of the training window, the c1 drivers used (and whether `disease_share` was dropped), and whether F2 passed. Push, and tell your human.

### 8. Tier 3, only if ahead: price driver ranking and current forecast

- Start only when tasks 1–7 work on the development window. Cut whatever isn't ready when the 04:00 `--final` run starts.
- **Current forecast (optional):** from the latest week, 2026-W44, forecast h = 1 to 8 with `band_model`, with bands from its development-window errors at each h, converted as in task 6. Put it in `price.json` → `current`, labelled as unverifiable before the event ends, and draw it in `price_fan.vl.json`. It never replaces the backtest. The contract gives no shape for `current`, so ask your human for one first.
- **Driver ranking:** in `price/ranking.py`, for each group in the contract's group table, drop that group's columns from c1, rerun the walk-forward at h = 4 on the development window only, and record `mae_without` and `increase_pct` = 100 × (`mae_without` − MAE_c1) ÷ MAE_c1.
- Drop only columns that are in `c1_drivers`, with all their lags. `market` and `pipeline` have no column in c1, so skip them. c0's columns stay in every run, and so does `usdnok_chg`, which is in no group.
- The ranking is exploratory, with no pass mark. Write its table to `price/RESULTS.md` only. `price.json` has no key for it, so ask your human before it goes on the site.

## Gotchas

- Export price is value ÷ volume, so more small fish lower it by arithmetic alone. That's why the average-weight term is in c0.
- The anomaly columns stored in Production's tables (`mobile_anom`, `treat_anom`, `biomass_anom`, `feed_rate_anom`, `mortality_anom` and the rest) are full-sample fits for in-sample work. Never put them in a model; recompute them as in task 2.
- Never use future EUR/NOK or USD/NOK, and never use a Directorate month before its release on the 20th of the next month.
- On a one-row `X_new`, `sm.add_constant` skips the constant, because every column looks constant. Use `sm.add_constant(X, has_constant="add")`, or add the column yourself.
- The holdout is locked. Never run `--final`, or score any target week from 2025-W01 on, before 04:00.
- Holiday weeks can move Statistics Norway's release day. The `available_at` rule is close enough.
- 2020 and 2026 have a week 53.

## Ask your human when

- something would change F2 or its pass mark;
- `anomalies.py`, `weekly_national_index.parquet` or `drivers_national_month.parquet` is late enough to block c1;
- the first complete training origin is later than 2020-W01, which leaves less than a year of training before the development window starts;
- results look too good (for example, an MAE ratio well below 0.8 at 4 weeks). Check for leakage first;
- you want the price driver ranking on the site, because `price.json` has no key for it.
