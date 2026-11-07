# Price integration verification

## Original verification, 7 November 2026

Price was implemented on `priceRyan`. At the start this worktree contained only
plans. Source tables and Production code were read from existing local Git refs
into temporary verification folders; no teammates' files were merged or edited.

- Data snapshot: `origin/data/loaders`, commit
  `9ea1d7f787cdcfbf592050c0697c0a7fd7def09b`.
- Production snapshot: `origin/production`, commit
  `80bcad039942aa3c4d6ab9f05fb3030fedd97c6d`.
- The preregistration already appears on `origin/main` at `b213291`.

The processed Data files contain real observations: SSB prices and volumes,
Norges Bank FX, Directorate area-months, farm weeks and the farm register.
Production's temperature code in `analysis/weekly_indices.py` was inspected:
its normal is the shifted cumulative mean for the same ISO week, requires three
earlier years, and its six-week degree-day sum looks backwards. Stored
full-sample anomaly columns are not used by Price.

## Historical upstream issue

At the original snapshots, Production `build_weekly_indices()` rejected one inconsistent
area: locality **34537**, `farm_week.area=4` and `farms.area=3`. There are 1,476
unique locality/area combinations and 416 farm capacities are null. The regional
inconsistency was subsequently resolved by Data's `30bdfc7` commit, now included
on this branch. Price did not reassign any farm area. The committed Price outputs
still describe the original inputs until the authoritative-table rerun below.

For this verification, only the **national** part of Production's existing
code was run: join capacity by locality; impute unknown capacity with the
register's area median using the observation's reported area; keep reported
farm weeks; derive the disease flag with `_disease_flag`; run `_aggregate` with
`["week_start"]`, then `_finish_indices` with no group columns. This preserves
the national aggregation formulas without invoking the unrelated regional
consistency check. It produced 775 weekly rows, including 602 with temperature
bands. This temporary derived input is not shipped as a replacement for the
Production-owned index.

The development artifacts include an explicit note describing this derivation.
Their `price/provenance.json` records the exact input hashes and anomaly engine.
After Data/Production deliver the index on the integrated branch, rerun the
default backtest and chart generator with that authoritative table. Results may
change if the upstream inputs change.

## Shared install and authoritative-table rerun

Original verification used the then-separate Price requirements. New checkouts
use the shared `.venv` installed from the root `requirements.txt`:

```sh
python -m unittest discover -s price/tests -v
python -m pipeline.checks
# Once Production's weekly and monthly national tables are on main:
python -m price.backtest
python -m charts.price_charts
```

Run the backtest from an up-to-date main without `--input-note`; that removes
the original input-debugging note from the regenerated public findings. Do not
replace the committed c1 results with a preliminary c0-only run while waiting
for Production's tables. The pending work is tracked in `REVIEW-priceRyan.md`.

The stand-in and Production anomaly functions were also compared for weekly and
monthly frequencies, all three transforms, missing values and an explicit
`fit_end`; results agreed to absolute tolerance `1e-12`.

The final-run CLI was invoked before the freeze to verify that it rejects the
request without computing any real holdout predictions. Holdout inference and
NOK/kg interval conversion are tested only with labelled synthetic fixtures.
Real F2 remains unscored until the scheduled final run.

## Recorded checks

- Real development replay: **5,656 predictions**, four models on 202 matched
  origins at every horizon 2–8. The output contains no holdout prediction rows.
- Training begins `2018-W33`; first h=4 development forecast has 118 training
  rows. All horizons selected p=2 using only the pre-2019 BIC sample.
- At h=4, development MAE: rw `0.08891`, ar `0.07555`, c0 `0.07701`, c1
  `0.09764` log points. c1 did not improve on c0 in development; this is not the
  F2 decision, which requires the unscored holdout.
- Site JSON was checked against the Parquet predictions: window membership,
  matched rows, error arithmetic and all 28 scorecard MAEs agree. Seven CW
  tests and six secondary Holm-adjusted p-values are present; h=4 is primary.
- Three v5 specs compiled and rendered with `vl-convert-python`, and their PNGs
  were visually inspected. Both scorecard windows and the holdout replay were
  additionally rendered with synthetic fixtures outside the public folders.
- All 108 real Directorate months have the complete 14 areas. Missing-value
  and missing-area behavior is exercised in synthetic unit tests.
- `pip check` reports no broken dependencies in the verification environment.

No live front-end application exists on this branch. Browser mounting and
deployment belong to the Front end role; these checks verify its agreed static
inputs, not a deployed page.

## Review follow-up verification

The shared root install was tested in a fresh `.venv`: pandas 3.1.1 (also
confirmed in Data's Parquet writer metadata), NumPy 2.4.6, Altair 5.5.0,
statsmodels 0.15.0 and linearmodels 7.1. All **26 Price tests**, all Data pipeline
checks and `pip check` passed. Regression tests reject BarentsWatch releases
at 7, 9 and 12 days, accept 13 days and later, preserve SSB's Wednesday release,
and verify registration through both Altair APIs. An isolated Altair 5.3.0
installation also registered the theme and serialized all three chart specs.

At the final repository check, main remained `30bdfc7` and Production was
`e7807b0`. The weekly national index was absent from both branches, and the
monthly national table was only on Production. The authoritative-table rerun
and public-note cleanup remain pending; no real holdout was scored and no
committed findings were regenerated during this review follow-up.
