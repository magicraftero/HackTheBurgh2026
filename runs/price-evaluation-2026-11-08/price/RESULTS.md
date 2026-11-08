# Price results

Real-data walk-forward backtest; no demonstration observations.

## Training and availability

First complete origin: 2018-W33.
Last-starting feature: weight_anom.
Training rows for the first h=4 development target: 118.
Anomaly engine: Price stand-in (Production anomaly module absent).
c1 added drivers: unavailable.

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
| dev | 2 | ar | 0.058393 | 0.92637 | 0.66827 |
| dev | 2 | c0 | 0.059316 | 0.94101 | 0.66346 |
| dev | 2 | rw | 0.063034 | 1 | not estimable |
| dev | 3 | ar | 0.06938 | 0.88696 | 0.67308 |
| dev | 3 | c0 | 0.071248 | 0.91085 | 0.66346 |
| dev | 3 | rw | 0.078222 | 1 | not estimable |
| dev | 4 | ar | 0.076561 | 0.84769 | 0.74038 |
| dev | 4 | c0 | 0.07846 | 0.86872 | 0.69712 |
| dev | 4 | rw | 0.090317 | 1 | not estimable |
| dev | 5 | ar | 0.081548 | 0.79725 | 0.74519 |
| dev | 5 | c0 | 0.083174 | 0.81314 | 0.71154 |
| dev | 5 | rw | 0.10229 | 1 | not estimable |
| dev | 6 | ar | 0.087165 | 0.75325 | 0.79808 |
| dev | 6 | c0 | 0.091476 | 0.7905 | 0.75481 |
| dev | 6 | rw | 0.11572 | 1 | not estimable |
| dev | 7 | ar | 0.094173 | 0.73795 | 0.78846 |
| dev | 7 | c0 | 0.096648 | 0.75735 | 0.75962 |
| dev | 7 | rw | 0.12761 | 1 | not estimable |
| dev | 8 | ar | 0.10245 | 0.72665 | 0.82212 |
| dev | 8 | c0 | 0.10097 | 0.7161 | 0.76923 |
| dev | 8 | rw | 0.141 | 1 | not estimable |

| Window | h | CW statistic | One-sided p | Holm p (secondary horizons) |
| --- | --- | --- | --- | --- |

## F2

Not recorded: holdout unscored. Development results are not the F2 decision.

## Matched-sample coverage

| Window / horizon | Scored | Missing features | Too little training | Missing actual |
| --- | --- | --- | --- | --- |
| dev/h8 | 208 | 0 | 0 | 0 |
| dev/h7 | 208 | 0 | 0 | 0 |
| dev/h6 | 208 | 0 | 0 | 0 |
| dev/h5 | 208 | 0 | 0 | 0 |
| dev/h4 | 208 | 0 | 0 | 0 |
| dev/h3 | 208 | 0 | 0 | 0 |
| dev/h2 | 208 | 0 | 0 | 0 |

## Limitations

- Actuals are latest revised data, not archived first releases.
- Publication lags reconstruct historical availability; holiday release dates are approximate.
- Monthly driver levels built from Directorate national sums (areas 0–13).
- c1 unavailable: weekly_national_index.parquet has not landed; preliminary rw/ar/c0 only.
- Errors and MAE are in log price-change points; prices are NOK/kg.
- All models use matched origins and expanding training rows; lags fixed by 2012–2018 BIC.
- Anomaly engine: Price stand-in (Production anomaly module absent).
- The 80% interval uses development errors and is not a calibrated coverage guarantee.
- Holdout unscored and locked until the analysis freeze (8 Nov 2026, 04:00 Europe/London).
