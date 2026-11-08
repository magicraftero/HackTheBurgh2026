# ML challenger: plan fixed before any ML run

Committed before any ML model was fitted to real outcome data. Nobody edits this file after that commit. It adds an **exploratory** challenger and changes nothing in `prereg/PASS_MARKS.md`: F1, F2, M1 and M2 are judged exactly as written there.

```text
ML challenger: fixed before any ML results were looked at.

PURPOSE
Exploratory. Add a gradient-boosted challenger beside the pre-registered linear models, at the
horizons the dashboards need: production h = 0-3 months and price h = 1-8 weeks (shown at 1, 2, 4
and 8). No pass mark. F1 and F2 are unaffected.

WINDOWS AND THE HOLDOUT
The same windows as PASS_MARKS, set by the target period:
Production dev Jan 2021 - Dec 2024, holdout Jan 2025 - Sep 2026.
Price dev 2021-W01 - 2024-W52, holdout 2025-W01 - 2026-W44.
A warm-up run (production targets from Jul 2019; price targets from 2019-W40) only seeds the
uncertainty bands and is never scored.
Default runs score dev only. --final runs once, after the 04:00 freeze on 8 Nov 2026 and after
Production's and Price's own --final runs. No hyperparameter or feature is changed after
--final.

MODELS (direct, one fit per horizon, refitted at every issue date / origin)
ml:  sklearn HistGradientBoostingRegressor(loss="absolute_error", max_depth=3,
     learning_rate=0.05, max_iter=300, min_samples_leaf=20, l2_regularization=1.0,
     early_stopping=False, random_state=0). Production marks area as categorical.
     These hyperparameters are fixed here and not tuned.
blend: production = mean of drivers and ml; price = mean of c0 and ml (in the model's own
     target space).
Linear comparators come from the existing code: production seasonal (level + season only),
b0, b1 and drivers; price rw, ar, c0 and c1. All models train and score on the same rows.

PRODUCTION (area 1-13 x target month T x horizon h = 0..3)
Issue date D = the 10th of month T - h + 1. Latest Directorate month known: M = T - h - 1.
Target: anomaly of log kg, log count and log avg_kg, with anomalies refitted at fit_end = M,
exactly as in analysis/nowcast.py; level and season are added back.
Features as of D. Directorate anomalies (biomass, fish stock, smolt pipeline, feed rate,
mortality) at M. Weekly BarentsWatch anomalies (mobile lice, treatments, disease share, the
three degree-day bands) for month T - h and T - h - 1, from weeks public by D. Export-volume
anomaly for month T - h. At h = 0 this is exactly the Drivers model.
ml adds the lagged outcome anomalies (kg, count, avg_kg) at M, M - 1 and T - 12; the log
avg_kg level at M; the mean sea temperature level for month T - h; the target month's sin and
cos; and the area.
Training rows: area-months whose actuals were published by D and whose Drivers features are
complete (the same sample rule as the nowcast).

PRICE (origin week t x horizon h = 1..8)
Origins, targets, the as-of feature frame, the BIC-fixed AR lag and the matched-sample rule
are Price's (price/dataset.py, price/models.py, price/backtest.py). Target p(t+h) - p(t).
ml uses the c1 columns, dp lags 0-7, and the price gap = p(t) minus the mean of p over the
previous 52 weeks.

UNCERTAINTY BANDS (every model, every horizon)
80% band from rolling conformal quantiles: q10 and q90 of that model's errors at that
horizon whose actuals were public by the issue date, from the previous 36 months (production)
or 156 weeks (price). At least 12 months / 52 weeks of errors, otherwise no band. The holdout
coverage of the band is reported.

WHY (per forecast)
For each driver group, set its features to normal and record the change in the prediction.
Normal = 0 for anomaly features; for level features (temperature, avg_kg, disease share), the
area's median over that fit's training rows. Groups follow docs/plans/00-shared.md, plus
"recent harvest" (lagged outcome anomalies and the avg_kg level).

WINNER RULE (which model drives the headline numbers)
Processor view and farmer cockpit: ml or blend (whichever is lower) replaces drivers only if
its dev MAE on log kg at h = 0 is at least 2% below drivers'.
Buyer view: ml or blend replaces the best of ar, c0 and c1 only if its dev MAE at h = 4 is at
least 2% below that model's.
Decided on the dev window before --final. The holdout result is shown either way; a reversal
on the holdout is shown, never re-picked.

REPORTING
MAE in log points plus tonnes, kg per fish and NOK/kg; n forecasts; improvement against
seasonal (production) or rw (price), for every horizon and window. If ml's dev MAE is below
0.8 x the best linear model, the run is checked for leakage before anything is published.
```
