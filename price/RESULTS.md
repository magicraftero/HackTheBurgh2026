# Price results

Real-data walk-forward backtest; no demonstration observations.

## Training and availability

First complete origin: 2018-W33.
Last-starting feature: weight_anom.
Training rows for the first h=4 development target: 118.
Anomaly engine: analysis.anomalies.anomaly.
c1 added drivers: mobile_anom, treat_anom, disease_share, dd_below8, dd_8to14, dd_above14, biomass_anom, feed_rate_anom, mortality_anom, usdnok_chg.

| h | Fixed AR lag p | Pre-2019 BIC rows |
| --- | --- | --- |
| 2 | 2 | 362 |
| 3 | 2 | 361 |
| 4 | 2 | 360 |
| 5 | 2 | 359 |
| 6 | 2 | 358 |
| 7 | 2 | 357 |
| 8 | 2 | 356 |

## Measured performance

MAE is in log points; ratios compare with the random walk.

| Window | h | Model | MAE | MAE / RW | Direction hit rate |
| --- | --- | --- | --- | --- | --- |
| dev | 2 | ar | 0.058342 | 0.92101 | 0.67822 |
| dev | 2 | c0 | 0.059768 | 0.94352 | 0.67327 |
| dev | 2 | c1 | 0.067522 | 1.0659 | 0.61881 |
| dev | 2 | rw | 0.063345 | 1 | not estimable |
| dev | 3 | ar | 0.069109 | 0.88684 | 0.66337 |
| dev | 3 | c0 | 0.070598 | 0.90594 | 0.66832 |
| dev | 3 | c1 | 0.083216 | 1.0679 | 0.60891 |
| dev | 3 | rw | 0.077928 | 1 | not estimable |
| dev | 4 | ar | 0.075548 | 0.84966 | 0.73267 |
| dev | 4 | c0 | 0.077009 | 0.8661 | 0.70297 |
| dev | 4 | c1 | 0.097633 | 1.0981 | 0.67822 |
| dev | 4 | rw | 0.088915 | 1 | not estimable |
| dev | 5 | ar | 0.080943 | 0.80389 | 0.73762 |
| dev | 5 | c0 | 0.081597 | 0.81039 | 0.71287 |
| dev | 5 | c1 | 0.10745 | 1.0672 | 0.67822 |
| dev | 5 | rw | 0.10069 | 1 | not estimable |
| dev | 6 | ar | 0.086677 | 0.76321 | 0.78218 |
| dev | 6 | c0 | 0.089044 | 0.78405 | 0.74752 |
| dev | 6 | c1 | 0.11661 | 1.0268 | 0.71782 |
| dev | 6 | rw | 0.11357 | 1 | not estimable |
| dev | 7 | ar | 0.092909 | 0.74563 | 0.79208 |
| dev | 7 | c0 | 0.094922 | 0.76178 | 0.77228 |
| dev | 7 | c1 | 0.13248 | 1.0632 | 0.75743 |
| dev | 7 | rw | 0.1246 | 1 | not estimable |
| dev | 8 | ar | 0.10156 | 0.73816 | 0.80198 |
| dev | 8 | c0 | 0.099316 | 0.72183 | 0.76733 |
| dev | 8 | c1 | 0.14824 | 1.0774 | 0.77228 |
| dev | 8 | rw | 0.13759 | 1 | not estimable |
| holdout | 2 | ar | 0.06877 | 0.95723 | 0.59375 |
| holdout | 2 | c0 | 0.064937 | 0.90389 | 0.57292 |
| holdout | 2 | c1 | 0.064878 | 0.90306 | 0.61458 |
| holdout | 2 | rw | 0.071843 | 1 | not estimable |
| holdout | 3 | ar | 0.078057 | 0.94713 | 0.63542 |
| holdout | 3 | c0 | 0.077861 | 0.94476 | 0.58333 |
| holdout | 3 | c1 | 0.075374 | 0.91458 | 0.63542 |
| holdout | 3 | rw | 0.082414 | 1 | not estimable |
| holdout | 4 | ar | 0.086936 | 1.0184 | 0.5625 |
| holdout | 4 | c0 | 0.083838 | 0.98207 | 0.5625 |
| holdout | 4 | c1 | 0.081146 | 0.95054 | 0.57292 |
| holdout | 4 | rw | 0.085368 | 1 | not estimable |
| holdout | 5 | ar | 0.09556 | 1.0173 | 0.57292 |
| holdout | 5 | c0 | 0.0916 | 0.97513 | 0.59375 |
| holdout | 5 | c1 | 0.086874 | 0.92482 | 0.64583 |
| holdout | 5 | rw | 0.093936 | 1 | not estimable |
| holdout | 6 | ar | 0.10617 | 1.0009 | 0.52083 |
| holdout | 6 | c0 | 0.10193 | 0.96098 | 0.58333 |
| holdout | 6 | c1 | 0.097631 | 0.92046 | 0.64583 |
| holdout | 6 | rw | 0.10607 | 1 | not estimable |
| holdout | 7 | ar | 0.1171 | 1.0565 | 0.58333 |
| holdout | 7 | c0 | 0.11133 | 1.0044 | 0.58333 |
| holdout | 7 | c1 | 0.10917 | 0.98493 | 0.63542 |
| holdout | 7 | rw | 0.11084 | 1 | not estimable |
| holdout | 8 | ar | 0.12596 | 1.0665 | 0.53125 |
| holdout | 8 | c0 | 0.11955 | 1.0122 | 0.51042 |
| holdout | 8 | c1 | 0.12052 | 1.0204 | 0.58333 |
| holdout | 8 | rw | 0.11811 | 1 | not estimable |

| Window | h | CW statistic | One-sided p | Holm p (secondary horizons) |
| --- | --- | --- | --- | --- |
| dev | 2 | 0.013769 | 0.49451 | 1 |
| dev | 3 | -0.35985 | 0.64052 | 1 |
| dev | 4 | -0.54453 | 0.70696 | not estimable |
| dev | 5 | -0.61312 | 0.7301 | 1 |
| dev | 6 | -0.4268 | 0.66524 | 1 |
| dev | 7 | -0.68795 | 0.75426 | 1 |
| dev | 8 | -0.81802 | 0.79333 | 1 |
| holdout | 2 | 1.4689 | 0.070928 | 0.16429 |
| holdout | 3 | 2.3795 | 0.0086691 | 0.043345 |
| holdout | 4 | 2.588 | 0.0048269 | not estimable |
| holdout | 5 | 2.4476 | 0.0071915 | 0.043149 |
| holdout | 6 | 1.955 | 0.025292 | 0.10117 |
| holdout | 7 | 1.6003 | 0.054763 | 0.16429 |
| holdout | 8 | 1.1364 | 0.1279 | 0.16429 |

## F2

Holdout result: False. MAE c0=0.083838, c1=0.081146; CW p=0.0048269.

Adding biology reduces four-week holdout MAE by **3.21%**, below the registered
**5%** minimum. The Clark–West requirement passes, but F2 requires both conditions.
The development result is weaker: c1 has higher error than c0 (0.09763 vs 0.07701).

Four-week holdout errors in the price's natural units, on the same 96 origins:

| Model | Mean absolute error (NOK/kg) |
| --- | --- |
| No change (random walk) | 7.23 |
| Price history and calendar (ar) | 7.31 |
| Market baseline (c0) | 7.12 |
| Market plus biology (c1) | 6.70 |

The registered decision uses log price-change MAE, not NOK/kg MAE.

## Matched-sample coverage

| Window / horizon | Scored | Missing features | Too little training | Missing actual |
| --- | --- | --- | --- | --- |
| dev/h8 | 202 | 6 | 0 | 0 |
| dev/h7 | 202 | 6 | 0 | 0 |
| dev/h6 | 202 | 6 | 0 | 0 |
| dev/h5 | 202 | 6 | 0 | 0 |
| dev/h4 | 202 | 6 | 0 | 0 |
| dev/h3 | 202 | 6 | 0 | 0 |
| dev/h2 | 202 | 6 | 0 | 0 |
| holdout/h8 | 96 | 0 | 0 | 0 |
| holdout/h7 | 96 | 0 | 0 | 0 |
| holdout/h6 | 96 | 0 | 0 | 0 |
| holdout/h5 | 96 | 0 | 0 | 0 |
| holdout/h4 | 96 | 0 | 0 | 0 |
| holdout/h3 | 96 | 0 | 0 | 0 |
| holdout/h2 | 96 | 0 | 0 | 0 |

## Limitations

- Actuals are latest revised data, not archived first releases.
- Publication lags reconstruct historical availability; holiday release dates are approximate.
- Errors and MAE are in log price-change points; prices are NOK/kg.
- All models use matched origins and expanding training rows; lags fixed by 2012–2018 BIC.
- Anomaly engine: analysis.anomalies.anomaly.
- The 80% interval uses development errors and is not a calibrated coverage guarantee.
- The 2025–2026 period had already been scored by the ML price pipeline before this run. This completes the registered-model evaluation on an exposed historical holdout; it is not a new independent validation sample.

## Run verification, 8 November 2026

- Ran `python -m price.backtest --final` with the existing model specification and authoritative weekly and monthly national input tables, then `python -m charts.price_charts`.
- Generated 8,344 predictions: four models, seven horizons, 202 development origins and 96 holdout origins per horizon. No holdout origins were skipped.
- All 26 Price unit tests passed before the real-data run. Input hashes, matched rows, error arithmetic, saved scores, F2 and the 96-week replay were checked against the generated Parquet predictions.
- Runtime: CPython 3.13.5, pandas 2.3.3, NumPy 2.4.6, statsmodels 0.15.0 and Altair 5.5.0, using the existing `/private/tmp/htb-price-venv` environment. This differs from the repository's pandas 3.1.1 pin; no dependency pins or model code were changed. Runtime versions are also recorded in the provenance sidecars.
