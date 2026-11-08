# Production nowcast

Install the shared dependencies and evaluate the development window from the
repository root:

```sh
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m analysis.nowcast
.venv/bin/python -m analysis.check_nowcast
```

The default command forecasts January 2021–December 2024 only, using eligible
pre-2021 training history. It does not load holdout target rows, fit holdout
forecasts or export holdout scores. October 2017–December 2024 provides 87
training/development calendar months; January 2025–September 2026 provides the
separate 21-month final test. All areas of a month stay in the same partition.

To preserve another run's output, choose a separate root:

```sh
.venv/bin/python -m analysis.nowcast --output-root runs/production-development
```

`--input-dir` selects another prepared-data directory. There are 1,404 unique
area-month observations in the source panel. The much larger vintage table
repeats those histories across forecast dates; its rows are not independent
additional observations.

## Registered model and challenger comparisons

The official model is pooled OLS, with an explicit intercept and separate
regressions for `log_kg`, `log_count` and `log_avg_kg`. Its B0, B1 and Drivers
predictors come directly from `model_features()`. Forecasts fit anomalies and
add the corresponding historical level and seasonal base back to reconstruct
the log outcome. Evaluation actuals are joined only after predictions exist.

Ridge-B1/Drivers and CatBoost-B1/Drivers are separate challengers. They receive
the same numerical predictor lists as their OLS equivalents; no family gets an
extra area identifier. Ridge standardizes predictors inside each training fold
and preserves the intercept. CatBoost can retain missing numerical predictors
in its available-data comparison, but still needs a valid reconstruction base.

Each evaluation has two training tracks:

- `common_training`: all models train on the same complete Drivers rows for
  the outcome and origin. The registered OLS comparison and `nowcast.json`
  use this track. Pairwise matched forecast rows isolate estimator differences
  and the incremental contribution of biological predictors.
- `available`: each estimator/predictor combination uses its own eligible
  training observations. These results show practical accuracy and coverage;
  differences can reflect additional usable data as well as the estimator.

The challenger JSON reports available-row losses and exact matched-row
comparisons in both tracks, plus year/area errors, training sizes and failure
reasons. A higher coverage rate does not establish lower error on common rows.
The registered F1 remains the OLS B1-versus-Drivers holdout test; Ridge and
CatBoost cannot substitute for either side of that test.

## Chronological tuning

Candidate selection uses at most the latest 12 earlier development months and
requires at least three usable validation months. Each inner fold uses that
month's own historical vintage, including its own seasonal adjustment. A scored
month's outcome cannot select that month's hyperparameters. Validation actuals
must already be published by the later selection date, and candidates are
compared on identical validation area-months.

The small fixed search is:

- Ridge `alpha`: `0.1`, `1`, `10`, `100`. The cold-start default is `10`.
- CatBoost: depth `3` with `l2_leaf_reg=10`, or depth `4` with
  `l2_leaf_reg=20`; learning rate `0.04`, maximum `200` iterations, and
  early-stopping patience `20`. Seed is `2026`, with one training thread.
  The cold-start choice is depth `3`, L2 `10`, and `100` fixed iterations.

CatBoost early stopping uses an earlier origin's own vintage and already
published labels. The final feature lists, hyperparameters, stopping iteration
counts and preferred challenger are locked using development data only.

## Outputs and the protected final run

Paths below are relative to the selected output root:

| File | Contents |
| --- | --- |
| `web/public/data/nowcast.json` | Shared-contract registered OLS forecasts and scores |
| `web/public/data/nowcast_challengers.json` | Separate family/track accuracy, matched comparisons, coverage and diagnostics |
| `data/processed/nowcast_backtest.parquet` | Registered OLS prediction rows, reconstructed values, eligibility and reasons |
| `data/processed/nowcast_challenger_backtest.parquet` | Selected predictions for every family and training track |
| `data/processed/nowcast_tuning.parquet` | Development candidate forecasts and early-stopping audit records |
| `analysis/nowcast_selection.json` | Locked configurations, feature lists and development selection history |
| `analysis/nowcast_provenance.json` | Input/code hashes, package versions, seeds and grids |
| `analysis/nowcast_reproduction.json` | Independent refit of all 42 December 2024 configurations, matching saved predictions exactly |
| `analysis/RESULTS.md` | Measured development accuracy, coverage and limitations |

Before final evaluation, `scores.holdout`, `f1` and `latest` stay null and the
backtest contains no holdout rows. Leave the real final run for the planned
**04:00 Europe/London freeze on 8 November 2026**:

```sh
# Run once at the freeze, using the same output root as the development lock.
.venv/bin/python -m analysis.nowcast --final
```

The final path checks the clock, selection lock, input/code hashes and package
versions, and refuses to replace a completed final record. It keeps challenger
configurations fixed while expanding training as earlier test outcomes become
published. It adds the OLS F1 calculation, the September 2026 worked example,
`web/public/data/drivers.json` and
`data/processed/nowcast_driver_ablations.parquet`, then records
`analysis/nowcast_final_run.json`. National predictions are unavailable unless
all areas 1–13 have valid predictions. Final-path tests use synthetic data.

Sparse harvest histories exposed an unidentified seasonal design during the
development audit. The compatible preparation correction preserves the
registered terms and marks unidentified or catastrophically ill-conditioned
adjustments unavailable; see [PREPARATION_FIX.md](PREPARATION_FIX.md).
Full-rank sparse fits can still produce extreme finite reconstructions. These
are retained and reported, without clipping. Ridge or CatBoost in the later
prediction stage cannot repair an unavailable or unstable seasonal base.

## Prepare and verify inputs

Build all inputs from the existing cleaned source tables, then audit the saved files:

```sh
.venv/bin/python -m analysis.prepare --as-of 2026-11-08
.venv/bin/python -m analysis.checks
.venv/bin/python -m pip install -r analysis/requirements-test.txt
.venv/bin/python -m pytest tests/production -q
.venv/bin/python -m unittest discover -s price/tests -v
```

The first command prepares data only. It does not train the nowcast, compute
forecast errors, or score the holdout. Use `--input-dir`, `--output-dir`, and
`--site-dir` to build into another folder. `--through-month` defaults to
September 2026. Publication dates are enforced even when source tables already
contain an incomplete future reporting week. Rebuild with an explicit `--as-of`
date for reproducibility. Every run preserves the original source tables.

## Files in `data/processed/`

| File | Purpose |
| --- | --- |
| `weekly_area_index.parquet` | Regular area/week grid: weighted lice and temperature, treatment/disease shares, temperature bands, reporting counts and publication dates |
| `weekly_national_index.parquet` | The same formulas across individual farms nationally, usable by Price |
| `drivers_area_month.parquet` | Stock, smolt pipeline, feed, mortality and monthly farm-health drivers for areas 1–13 |
| `drivers_national_month.parquet` | National ratios of sums including area 0, national farm-health means, and complete-month export volumes |
| `area_month_panel.parquet` | Harvest kg, count, average weight and all area drivers, including descriptive anomalies |
| `nowcast_vintages.parquet` | Every forecast month's historical training rows and target rows, with adjustment refitted using that vintage's published levels |
| `nowcast_features.parquet` | Target rows from those vintages, with calendar lags and readiness flags for B0, B1 and Drivers |
| `nowcast_targets.parquet` | Separate evaluation labels with publication dates and explicit zero-harvest flags |
| `production_preparation.json` | Input hashes, package versions, missingness, coverage and quality notes |
| `PRODUCTION_DATA_REPORT.md` | Human-readable coverage and limitations |

`web/public/data/area_month.json` follows the shared display contract. The build
reuses preparation modules from the locally available Production ref
`a61f406a87416cd7c19d58a6559498a9418196f1`, with stricter validation, publication
filtering, calendar alignment, and dated forecast inputs added here.

## Use the dated training data

```python
import pandas as pd
from analysis.nowcast_inputs import model_features

vintages = pd.read_parquet("data/processed/nowcast_vintages.parquet")
vintage = vintages.loc[vintages.forecast_month == "2024-09"]
features = model_features(include_disease=True)["drivers"]
train = vintage.loc[~vintage.is_target].dropna(subset=features + ["log_kg_anom"])
predict = vintage.loc[vintage.is_target].dropna(subset=features + ["log_kg_base"])
# Fit on train[features] and train.log_kg_anom, with an explicit intercept.
# Predicted log kg = predicted anomaly + predict.log_kg_base.
# Join nowcast_targets by area/month only AFTER prediction for evaluation.
```

Each vintage is made on the 10th of the following month. Directorate levels
stop at the preceding month and must already be published. Weekly levels and
exports must be public by the forecast date. Monthly seasonal fits stop at
the preceding month; weekly fits exclude weeks whose Thursday belongs to the
target month. Target harvest labels are null in every vintage. Use each
vintage's training rows, rather than concatenating target rows from different
seasonal fits into one training sample. Predictor flags describe completeness;
the chosen outcome also needs a non-null base, sufficient training rows and an
identified regression. Match model samples when comparing their performance.

Stored anomaly columns in `drivers_*`, `weekly_*` and `area_month_panel` are
full-sample descriptive fits for the planned panel analysis. They must never
be used directly in the nowcast. The dated input builder ignores them and
also recalculates temperature normals from public temperature observations.

## Missingness and source limitations

- Missing farm reports are never imputed to zero. Zero-report index rows retain
  missing values and a publication date. Disease stays unknown before 2014.
- Missing capacity uses the registered area's median capacity only for the
  aggregation weights. The original 416 missing source capacities stay null.
  Capacity history is unavailable, so weights use the current farm register.
- Zero harvest is a real observation. Average weight and ordinary log targets
  remain null, rather than inventing a positive harvest. The 83 zero-harvest
  area-months are in areas 1 and 13. Area 13 has too few usable residuals to
  estimate the descriptive weight anomaly with the registered seasonal terms.
- The smolt pipeline requires all 12 calendar months from m−23 through m−12;
  anomalies then require their own trailing history. No partial sums are used.
- Temperature normals need three previous years for the same ISO week; six
  consecutive usable weeks are needed for degree days. Sparse ISO week 53
  history can remove predictors in subsequent weeks/months. These gaps remain
  explicit in the reports instead of being filled with fabricated zeros.
- Complete national Directorate totals require areas 0–13. Monthly exports
  require every Thursday-assigned week; partial export totals remain null.
- The treatment format changed in 2024-W46. The report compares the same season
  a year apart. This diagnostic cannot establish that reporting is unchanged.
- Sources contain latest revised data; first-release vintages are unavailable.
  Publication dates reconstruct historical access and approximate holidays.

