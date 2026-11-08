# SISALMONI exploratory price-model test

The original model features and OLS estimator are refitted to SISALMONI EUR/kg prices only.
No Nasdaq prices are used or spliced in. The registered SSB F2 result is unchanged.

## Main result

The current model performs poorly on this short SISALMONI history. At four weeks,
78 matched forecasts cover target weeks **2025-W19 to 2026-W44**:

| Model | Mean absolute error, EUR/kg | Log-change MAE |
| --- | --- | --- |
| No change | **0.636** | **0.09708** |
| Price history and calendar | 0.991 | 0.17467 |
| Market baseline, c0 | 1.117 | 0.16307 |
| Market plus biology, c1 | 5.392 | 0.35077 |

Adding biology increases log error versus c0 by **115.1%**; the one-sided
Clark–West p-value is **0.5096**. There is no evidence of a useful improvement
from this implementation on these matched index forecasts.

The early fits have only 30–34 training observations for 29 model terms and can
be unstable. For example, the forecast for 2025-W20 is EUR 121.45/kg against an
actual index of EUR 6.42/kg, after training on 31 observations. No forecast is
clipped or removed from the reported scores. This is evidence that the current
OLS specification is unsuitable for the available short index history, not proof
that all biological information or all SISALMONI forecasting models are unhelpful.

The original registered SSB test had a much longer price-training history and a
different target/currency, so its numerical error cannot be compared directly
with this EUR/kg error. A simpler or regularized model would be a new experiment;
this test does not select or tune one from the observed scores.

## Full results

The public endpoint uses the legacy key fpiEUR for the SISALMONI 3–6kg EUR benchmark. Its fpiNOK history is not used because 2024 NOK observations include blended FPI values.

Public target history: 2024-W32 to 2026-W44, 117 weeks.
Requested evaluation targets: 2025-W01 to 2026-W44; early targets without enough training are skipped for every model.
AR lag counts are inherited from the frozen SSB run's pre-2019 selection, not selected on this index.
Training expands at each Thursday origin, retaining only labels and drivers public by that date.
The public index is released Wednesday afternoon; Thursday midnight is used conservatively, combined with SSB publication availability. Holiday release timing is approximate.

| h | Model | n | MAE log | MAE EUR/kg | MAE / no-change | First target | Last target |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2 | ar | 82 | 0.111634 | 0.724 | 1.351 | 2025-W15 | 2026-W44 |
| 2 | c0 | 82 | 0.114262 | 0.795 | 1.383 | 2025-W15 | 2026-W44 |
| 2 | c1 | 82 | 0.249962 | 3.594 | 3.026 | 2025-W15 | 2026-W44 |
| 2 | rw | 82 | 0.0826008 | 0.551 | 1 | 2025-W15 | 2026-W44 |
| 3 | ar | 80 | 0.148199 | 0.898 | 1.567 | 2025-W17 | 2026-W44 |
| 3 | c0 | 80 | 0.155538 | 1.093 | 1.644 | 2025-W17 | 2026-W44 |
| 3 | c1 | 80 | 0.278804 | 2.407 | 2.947 | 2025-W17 | 2026-W44 |
| 3 | rw | 80 | 0.0945949 | 0.625 | 1 | 2025-W17 | 2026-W44 |
| 4 | ar | 78 | 0.174668 | 0.991 | 1.799 | 2025-W19 | 2026-W44 |
| 4 | c0 | 78 | 0.163075 | 1.117 | 1.68 | 2025-W19 | 2026-W44 |
| 4 | c1 | 78 | 0.350772 | 5.392 | 3.613 | 2025-W19 | 2026-W44 |
| 4 | rw | 78 | 0.0970843 | 0.636 | 1 | 2025-W19 | 2026-W44 |
| 5 | ar | 76 | 0.2026 | 1.074 | 1.861 | 2025-W21 | 2026-W44 |
| 5 | c0 | 76 | 0.206487 | 1.355 | 1.897 | 2025-W21 | 2026-W44 |
| 5 | c1 | 76 | 0.476654 | 26.244 | 4.379 | 2025-W21 | 2026-W44 |
| 5 | rw | 76 | 0.108841 | 0.706 | 1 | 2025-W21 | 2026-W44 |
| 6 | ar | 74 | 0.208954 | 1.096 | 1.778 | 2025-W23 | 2026-W44 |
| 6 | c0 | 74 | 0.241782 | 1.667 | 2.057 | 2025-W23 | 2026-W44 |
| 6 | c1 | 74 | 0.517798 | 4.102 | 4.405 | 2025-W23 | 2026-W44 |
| 6 | rw | 74 | 0.117548 | 0.757 | 1 | 2025-W23 | 2026-W44 |
| 7 | ar | 72 | 0.195401 | 1.155 | 1.569 | 2025-W25 | 2026-W44 |
| 7 | c0 | 72 | 0.269237 | 2.475 | 2.161 | 2025-W25 | 2026-W44 |
| 7 | c1 | 72 | 0.473213 | 4.193 | 3.799 | 2025-W25 | 2026-W44 |
| 7 | rw | 72 | 0.124573 | 0.804 | 1 | 2025-W25 | 2026-W44 |
| 8 | ar | 70 | 0.191493 | 1.234 | 1.436 | 2025-W27 | 2026-W44 |
| 8 | c0 | 70 | 0.271353 | 2.455 | 2.035 | 2025-W27 | 2026-W44 |
| 8 | c1 | 70 | 1.10808 | 69285086843.848 | 8.31 | 2025-W27 | 2026-W44 |
| 8 | rw | 70 | 0.133336 | 0.862 | 1 | 2025-W27 | 2026-W44 |

| h | c1 improvement over c0 | Clark–West p | Secondary Holm p |
| --- | --- | --- | --- |
| 2 | -118.763% | 0.740512 | 1 |
| 3 | -79.252% | 0.819567 | 1 |
| 4 | -115.099% | 0.509613 | primary |
| 5 | -130.840% | 0.0904056 | 0.542434 |
| 6 | -114.159% | 0.90214 | 1 |
| 7 | -75.761% | 0.767392 | 1 |
| 8 | -308.352% | 0.898879 | 1 |

## Limits

- This is an exploratory target-change experiment, not a new pre-registered F2 decision or independent confirmation.
- The target series starts in 2024; its short training history can make the high-dimensional OLS model unstable. No hyperparameters, feature lists, forecasts or start dates were tuned after seeing results.
- Actuals and exogenous inputs are today's revised observations; historical availability is reconstructed.
- All models are scored on identical origin rows at each horizon, using the original rule n_train > number of c1 columns.
- Every pre-index price and missing index week is NaN. Older SSB export volumes remain available as predictors, but SSB prices are never used as target substitutes.
- Any natural-price overflow is counted and its EUR/kg MAE is explicitly unavailable rather than dropping the forecast.
- Rank deficiency, conditioning and forecast extrema are recorded in metrics.json; forecasts are never clipped or removed for instability.
- Matrix rank and condition diagnostics refer to the largest c1 design used for the common sample rule, including when repeated on another model's score row.

## Sources and reproduction

- [Public weekly index history](https://salmonprice.com/fishpool/public/priceHistory)
- [Index definition and publication time](https://www.sitagri.com/sitagri-salmon-index/)

`python -m price.sisalmoni --raw-dir data/raw/sisalmoni`

The raw response, input and lag-selection hashes and runtime versions are in provenance.json.

## Skipped targets

```json
{
  "8": {
    "missing_features": 0,
    "insufficient_training": 26,
    "missing_actual": 0,
    "scored": 70
  },
  "7": {
    "missing_features": 0,
    "insufficient_training": 24,
    "missing_actual": 0,
    "scored": 72
  },
  "6": {
    "missing_features": 0,
    "insufficient_training": 22,
    "missing_actual": 0,
    "scored": 74
  },
  "5": {
    "missing_features": 0,
    "insufficient_training": 20,
    "missing_actual": 0,
    "scored": 76
  },
  "4": {
    "missing_features": 0,
    "insufficient_training": 18,
    "missing_actual": 0,
    "scored": 78
  },
  "3": {
    "missing_features": 0,
    "insufficient_training": 16,
    "missing_actual": 0,
    "scored": 80
  },
  "2": {
    "missing_features": 0,
    "insufficient_training": 14,
    "missing_actual": 0,
    "scored": 82
  }
}
```
