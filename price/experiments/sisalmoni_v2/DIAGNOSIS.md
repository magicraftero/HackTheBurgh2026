# Diagnosis before SISALMONI v2 evaluation

Inspected on 8 November 2026, before scoring any new challenger. This diagnosis
uses the existing code, source checks and saved SISALMONI experiment. It does not
use the v2 final-segment outcomes to choose models.

## Confirmed causes of instability

The old `c1` model has **29 columns**: nine calendar terms (constant, three annual
Fourier harmonics, Easter and Christmas), two price-change lags, five market
features and thirteen additional driver/lag features. Its first four-week fit has
only **30 complete training observations**. The original rule `n > columns`
checks algebraic sample size; it does not ensure full rank, adequate residual
degrees of freedom or stable out-of-sample extrapolation.

Reconstruction of existing four-week training matrices gives:

| Origin week | Issue date | Rows / columns | Rank | Raw condition number | Condition after removing constant columns and scaling |
| --- | --- | --- | --- | --- | --- |
| 2025-W15 | 2025-04-17 | 30 / 29 | 28 | 4.46e18 | 1,829 |
| 2025-W16 | 2025-04-24 | 31 / 29 | 29 | 277,127 | 2,215 |
| 2026-W09 | 2026-03-05 | 76 / 29 | 29 | 10,542 | 18.8 |

The first matrix's Easter column is entirely zero. The first two fits have only
two residual degrees of freedom. In the second fit, the correlation between the
first and second cosine terms is 0.934 and between mobile lice and its one-week
lag is 0.905. The standard deviation of nonconstant features ranges from 0.00448
to 26.11. Thus, mixed units worsen the numerical conditioning, while substantial
collinearity remains even after scaling. Scaling alone cannot resolve the small
sample and redundant predictors.

The saved model already demonstrates the practical consequence: its forecast
for 2025-W20 is EUR 121.45/kg against EUR 6.42/kg actual, after a 31-row fit.
At eight weeks, a few exponential reconstructions are vastly larger still.
`statsmodels` can return a finite least-squares log prediction from an ill-
conditioned or rank-deficient design; exponentiating it can magnify an error
dramatically. This is a high-variance model-design failure, not evidence that
the linear-algebra implementation calculated the wrong formula.

Three annual harmonics and holiday effects are especially difficult to estimate
from a partial year. The old two-lag choice was inherited from pre-2019 SSB
prices; it was not selected using SISALMONI observations. Neither that lag choice
nor the SSB model's much longer training history establishes suitability for
this short, different target.

## Target, timing and alignment checks

- The target is the **SISALMONI 3–6 kg benchmark in EUR/kg**, not the all-size
  average. The 117 local observations cover 2024-W32 through 2026-W44 without
  a gap. No Nasdaq or SSB target-price history is appended.
- The public source uses the legacy JSON key `fpiEUR`. Its 2024-W33 value 6.20
  matches the original SISALMONI EUR report. The contemporaneous NOK history
  is unsuitable as a pure-index substitute: it includes the Fish Pool blend.
  [Fish Pool's transition explanation](https://fishpool.eu/wp-content/uploads/2024/08/ABC-Fish-Pool-contracts-at-Euronext.pdf)
  distinguishes the 2024 NOK blend from the pure EUR settlement benchmark.
- [Sitagri's definition](https://www.sitagri.com/sitagri-salmon-index/) identifies
  the separate size benchmarks, EUR/NOK presentations and normal Tuesday
  calculation. The [2024-W33 original EUR report](https://salmonprice.com/fishpool/servlets/newt/public/json/files?action=download&category=eur&month=8&type=nasdaq&week=33&year=2024)
  distinguishes Tuesday subscriber delivery from Wednesday-afternoon public
  release. The inherited Thursday issue schedule is conservative for normal
  weeks. Exact historical holiday/exceptional release timestamps are unavailable;
  availability remains a reconstruction rather than a verified release archive.
- `retarget_dataset` keeps all export-volume history and makes pre-index target
  prices missing. The internal `price_nok_kg` carrier contains EUR in this separate
  experiment; the label is legacy naming, and the experiment's exported units
  are explicitly EUR/kg. No numerical NOK-to-EUR conversion is performed there.
- Directorate, FX and biological values are filtered by publication date.
  Anomalies are recomputed at the forecast origin rather than reading the stored
  full-sample anomaly columns. Weekly biology's 13-day minimum release lag means
  the current delivery week's biology is unavailable at its normal Thursday
  price issue date; the model consequently uses the prior released week.
- Target dates are calendar shifts `origin Monday + h weeks`, not positional
  row shifts. December 2025's week 1 is correctly assigned to ISO year 2026.
  No week-compression or target-substitution defect was found.
- Four weeks denotes a delivery-week-index shift: the target delivery week starts
  18 days after the normal Thursday issue, while its reconstructed public release
  is 28 days after that issue. It should not be described as predicting a delivery
  week that begins 28 days after the forecast.

The existing experiment's training-label release maximum equals, and never
exceeds, its issue date at the reconstructed origins examined. This supports the
implemented availability rule but does not prove unrecorded historical release
times or first-release vintages. Inputs and actuals are revised snapshots.

## Hypotheses that still require validation

Weak incremental biological information, changing market relationships and the
economic effects of switching from a broad export-price series to a 3–6 kg EUR
benchmark may also matter. They are modelling hypotheses, not diagnosed software
defects. Feature-group comparisons must test their contribution on common dates.
Good performance from a simpler model would establish a forecasting result for
this retrospective sample, not a causal role for any driver.

The proposed compact, scaled Ridge models directly address confirmed complexity
and conditioning problems. Their regularization and small feature set are
justified before scores are seen; improvement over no change remains unproven.
A fixed 50/50 blend with no change is a low-variance additional challenger that
does not require fitting another large model to 117 observations.

## Chronological split and interpretation safeguards

The first 93 target weeks end at **2026-W20**. The final 24 target weeks are
**2026-W21 through 2026-W44**. At horizon eight, the earliest final forecast is
issued on **2 April 2026**, so a common frozen model-selection decision may use
development validation labels only through **2026-W13**. Weeks W14–W20 form a
selection gap; their labels can enter later expanding training fits only as
they become public. Selecting configurations on development targets through
W20 and applying them to the earlier final forecast issues would leak future
validation outcomes.

Candidate preprocessing must be fitted on each training window. A chronological
development selection-policy check may use earlier validation errors only after
their actuals are public. Freeze the final candidate/configuration selection
before scoring any final-segment outcome. Final refitting may learn newly
released labels; feature and hyperparameter choices must remain fixed.

The earlier SISALMONI experiment already exposed historical scores, including
these later weeks. This is a **retrospective test**, not a fresh holdout. Compare
all models on identical final target weeks and retain every failure or extreme
forecast in coverage and error accounting. The old headline EUR 5.392/kg MAE
uses a different, longer evaluation period and is not the v2 comparison baseline.

With only 24 final weekly targets, overlapping four-week forecasts provide few
effectively independent blocks. Paired errors and block-based uncertainty are
more informative than an unqualified percentage improvement; evidence can remain
weak even when a point estimate improves by 10%.
