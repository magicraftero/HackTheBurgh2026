# SISALMONI v2: protocol fixed before challenger validation

Date: 8 November 2026. This is a retrospective evaluation: the previous SISALMONI
experiment and its historical prices have already been inspected. It is not a
fresh independent holdout. No improvement is promised.

## Data, target and preservation

- Genuine SISALMONI 3–6 kg **EUR/kg**, `fpiEUR` from the official public yearly
  history. Only the 117 consecutive weeks 2024-W32 through 2026-W44 are used as
  price observations. No Nasdaq, SSB-price or other index splice is permitted.
- Existing raw files, original experiment, registered SSB outputs and model code
  are preserved. Source definitions, two original-report checks and the 2024 NOK
  composite issue are documented in `../sisalmoni/SOURCES.md`.
- Subscriber publication is normally Tuesday. The contemporary public report
  says Wednesday afternoon; issue dates conservatively use delivery-week Monday
  plus 10 days (Thursday of the next week), or the SSB-volume release if later.
  Historical holiday/exceptional-release dates remain approximate.
- A horizon h means the price for ISO week t+h, with origin t's index already
  published at the issue date. It is not h full weeks after the Thursday issue.
- Exogenous features use the original publication dates, including Sunday after
  the following week for BarentsWatch and next month's 20th for Directorate data.
  Each historical feature row is constructed from its own as-of snapshot.

## Chronological split and purge

- Earliest 93 target weeks: development, 2024-W32 through 2026-W20.
- Latest 24 target weeks: final retrospective test, **2026-W21 through 2026-W44**.
- The earliest final forecast among horizons 2–8 is h=8 for target 2026-W21:
  origin 2026-W13, issued **2 April 2026**. All selection outcomes must already
  have been published by that date. Consequently the last selectable development
  validation label is **2026-W13**. Development targets W14–W20 form an explicit
  gap for selection; they may become training labels later, after publication.
- For every fit, training labels must have `target_available_at <= issue_date`
  and target week no later than the origin week. Calendar-week shifts preserve
  gaps and year boundaries. At least 30 complete training observations are
  required on the common feature sample, allowing comparison with the old
  29-column model. This rule is fixed before v2 validation.
- Preprocessing is refitted on training rows only. No validation/test row enters
  scaling, target centering or fitted coefficients. Candidate parameters are
  predefined below, not optimized on later folds.
- In addition to fixed-candidate validation tables, an online development policy
  selects configurations using only prior four-week validation errors whose
  labels have been released by the current issue date; it uses no change until
  eight such errors exist. This checks the selection procedure chronologically.
- After development, write an immutable `selection.json` with configurations,
  selection, metric, dates, input/code hashes and a timestamp **before** computing
  final scores. Later final training may expand with newly public labels, but
  feature lists, hyperparameters and model choice stay frozen.

## Small model set

All models use identical forecast origins and target weeks at each horizon.

Baselines:

1. `rw`: no change.
2. `ar1`: direct OLS of the horizon's log change on a constant and latest weekly
   log return, two coefficients.
3. `old_ar`, `old_c0`, `old_c1`: the existing experiment's exact saved forecasts,
   validated against the same input/target/issue dates. Their comparison scores
   are recomputed on the new identical dates; the old 5.392 headline is not used.

Compact Ridge price inputs (six): current EUR price; latest weekly log return;
four-week log momentum; standard deviation of the latest four weekly log returns
(ddof=0); one annual sine and cosine evaluated at the known target calendar week.

Four price-only configurations: alpha **10 or 100**, with either direct **log
change** (converted using the origin price) or direct **EUR price level** as the
target. Ridge minimizes squared error plus alpha times squared coefficients,
with training-only standardization and an unpenalized intercept. Constant columns
receive scale 1. Positive alpha stabilizes correlated columns. No predictions
are clipped; nonfinite/nonpositive prices are reported as failures.

Controlled feature comparisons all use the same price-only log-change Ridge at
alpha 100, adding one group at a time:

- FX: EUR/NOK and USD/NOK weekly log changes.
- Exports: current and previous export-volume anomalies.
- Biology: mobile-lice anomaly, mortality anomaly and sum of the three temperature
  degree-day bands. No future farm report or monthly observation is included.

One additional challenger is a fixed **50/50 arithmetic average** of no change
and price-only log-change Ridge at alpha 100. It adds no fitted parameters. A tree
model is deferred because 117 observations do not justify another model search.

## Selection and objectives

- Primary horizon: **four weeks**. Primary metric: **EUR/kg MAE**.
- A feature-group variant is eligible only if its released development MAE is at
  least **2% below the same price-only alpha-100 log-change Ridge**. Other Ridge
  variants and the fixed ensemble are eligible on complete successful coverage.
- Select the eligible challenger with the lowest development four-week MAE;
  ties use a stable model-ID ordering. Separately freeze the strongest development
  baseline among no change, AR1 and the three existing-model references.
- The frozen forecast policy uses whichever of that challenger and baseline has
  lower development MAE. The test never changes this policy or candidate grid.
- Aim for at least **10% lower final four-week MAE than every eligible baseline**,
  including no change. This is an objective rather than an assumption of success.
- Practical improvement and statistical evidence are separate. Report paired
  weekly absolute-error differences for the selected challenger against no change,
  the frozen strongest development baseline and the strongest observed final
  baseline. The last comparison is descriptive, not a model-selection step.
- Circular paired block bootstrap: 10,000 replicates, deterministic seed
  `20261108 + 100 * horizon + block_length`; primary block
  length four weeks, sensitivity eight weeks. Report 95% intervals for EUR/kg MAE
  differences and percentage improvements. For secondary horizons use at least
  the horizon as the block length. The 24-week sample contains few independent
  blocks, so intervals are approximate and cannot establish broad reliability.
- Recommend the challenger only if it meets the practical objective and its
  paired difference against no change and the frozen baseline has a 95% upper
  bound below zero under both block lengths. Otherwise retain the strongest
  development baseline and describe any observed test reversal explicitly.

## Required reporting and checks

- Development and final tables: period, model, horizon, expected/scored samples,
  failures, EUR/kg MAE and RMSE, log-change MAE, direction hit rate (no-change has
  no direction call), coverage and improvements against matched baselines.
- Do not drop difficult weeks or compute apparently improved MAE only on the
  successful subset of a failing model. Ineligible/failing forecasts remain in
  prediction records and coverage diagnostics.
- Actual/predicted and forecast-error plots for the primary test, plus secondary
  horizon comparisons. No graph axes hide extreme errors.
- Focused tests: publication-date leakage, horizon/ISO alignment, preprocessing
  isolation, numerical stability, selection-label availability, the global purge,
  candidate eligibility and final freeze/overwrite guards.
- Preserve hashes of the original SSB and v1 artifacts; record source, input,
  protocol, code and runtime versions. Results and implementation remain under
  `price/experiments/sisalmoni_v2/` and dedicated `price/sisalmoni_v2*.py` modules.

Method references: [Ridge objective](https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.Ridge.html),
[chronological splits and gaps](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html),
[circular block resampling](https://bashtage.github.io/arch/bootstrap/generated/arch.bootstrap.CircularBlockBootstrap.html).
