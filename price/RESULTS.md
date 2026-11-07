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
| dev | 2 | c1 | 0.067525 | 1.066 | 0.61881 |
| dev | 2 | rw | 0.063345 | 1 | not estimable |
| dev | 3 | ar | 0.069109 | 0.88684 | 0.66337 |
| dev | 3 | c0 | 0.070598 | 0.90594 | 0.66832 |
| dev | 3 | c1 | 0.083224 | 1.068 | 0.60891 |
| dev | 3 | rw | 0.077928 | 1 | not estimable |
| dev | 4 | ar | 0.075548 | 0.84966 | 0.73267 |
| dev | 4 | c0 | 0.077009 | 0.8661 | 0.70297 |
| dev | 4 | c1 | 0.097635 | 1.0981 | 0.67822 |
| dev | 4 | rw | 0.088915 | 1 | not estimable |
| dev | 5 | ar | 0.080943 | 0.80389 | 0.73762 |
| dev | 5 | c0 | 0.081597 | 0.81039 | 0.71287 |
| dev | 5 | c1 | 0.10746 | 1.0673 | 0.67822 |
| dev | 5 | rw | 0.10069 | 1 | not estimable |
| dev | 6 | ar | 0.086677 | 0.76321 | 0.78218 |
| dev | 6 | c0 | 0.089044 | 0.78405 | 0.74752 |
| dev | 6 | c1 | 0.11662 | 1.0269 | 0.71782 |
| dev | 6 | rw | 0.11357 | 1 | not estimable |
| dev | 7 | ar | 0.092909 | 0.74563 | 0.79208 |
| dev | 7 | c0 | 0.094922 | 0.76178 | 0.77228 |
| dev | 7 | c1 | 0.1325 | 1.0634 | 0.75743 |
| dev | 7 | rw | 0.1246 | 1 | not estimable |
| dev | 8 | ar | 0.10156 | 0.73816 | 0.80198 |
| dev | 8 | c0 | 0.099316 | 0.72183 | 0.76733 |
| dev | 8 | c1 | 0.14827 | 1.0776 | 0.77228 |
| dev | 8 | rw | 0.13759 | 1 | not estimable |

| Window | h | CW statistic | One-sided p | Holm p (secondary horizons) |
| --- | --- | --- | --- | --- |
| dev | 2 | 0.012067 | 0.49519 | 1 |
| dev | 3 | -0.36149 | 0.64114 | 1 |
| dev | 4 | -0.54591 | 0.70744 | not estimable |
| dev | 5 | -0.61426 | 0.73048 | 1 |
| dev | 6 | -0.42798 | 0.66567 | 1 |
| dev | 7 | -0.6886 | 0.75446 | 1 |
| dev | 8 | -0.81774 | 0.79325 | 1 |

## F2

Not recorded: holdout unscored. Development results are not the F2 decision.

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

## Limitations

- Actuals are latest revised data, not archived first releases.
- Publication lags reconstruct historical availability; holiday release dates are approximate.
- Monthly driver levels built from Directorate national sums (areas 0–13).
- Verification inputs: Data branch 9ea1d7f; Production branch 80bcad0. National index built using Production national aggregation helpers because the combined area builder rejects locality 34537 (weekly area 4; register area 3). No farm area was reassigned. Rebuild from the delivered Production national table after integration.
- Errors and MAE are in log price-change points; prices are NOK/kg.
- All models use matched origins and expanding training rows; lags fixed by 2012–2018 BIC.
- Anomaly engine: analysis.anomalies.anomaly.
- The 80% interval uses development errors and is not a calibrated coverage guarantee.
- Holdout unscored and locked until the analysis freeze (8 Nov 2026, 04:00 Europe/London).
