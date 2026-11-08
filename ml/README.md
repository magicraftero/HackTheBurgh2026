# Harvest model

This branch (`ml/harvest-model`) keeps one model, the one with the best results, plus everything it needs: the data pipeline, the feature code, its tests and its two site files. It was cut down from `ml/challenger`; "What was removed" is at the end.

## What it predicts

Harvest in each of Norway's production areas, and for Norway as a whole: tonnes, number of fish and average fish size. Each issue date (the 10th of the month) forecasts four months:

| h | Month forecast | Issued 10 Nov, it forecasts |
| --- | --- | --- |
| 0 | Last month, before the Directorate publishes it (around the 20th) | October |
| 1 | This month | November |
| 2 | Next month | December |
| 3 | In two months | January |

## The model

The mean of two halves, both refitted at every issue date on data published by then:

- **Linear half:** Production's Drivers model (stock, smolt pipeline, feed, deaths, disease, lice, treatments, temperature and exports).
- **Tree half:** gradient-boosted trees (scikit-learn `HistGradientBoostingRegressor`) on the same drivers, plus recent harvests, the area, the month and the sea temperature.

The settings are fixed in `prereg/ML_PLAN.md` and were never tuned. The seasonal normal (a normal month for that area and time of year) is kept as the reference line.

## Why this model

It was picked on 2021–24 with a rule fixed in advance (`prereg/ML_PLAN.md`), then checked on 2025–26, which no fit ever saw. Average miss for last month's harvest per area, from `ml/challenger`'s run (log points, roughly a % error):

| Model | 2021–24 | 2025–26 |
| --- | --- | --- |
| Seasonal normal | 0.312 | 0.298 |
| Stock only (B0) | 0.270 | 0.244 |
| Stock + exports (B1) | 0.269 | 0.241 |
| Linear, all drivers | 0.273 | 0.234 |
| Trees alone | 0.279 | 0.222 |
| **This model (linear + trees)** | **0.267** | **0.222** |

For fish size, it's within 1% of the trees alone and well ahead of every linear model. The trees improve as data builds up: they were 11% worse than B1 in 2021 (about 115 rows to learn from) and 10% better by 2026 (about 765).

## How accurate it is (2025–26, never seen in training)

| What | Usually off by | Within 10% |
| --- | --- | --- |
| Norway total, last month | about 5% (8,300 t of a 142,000 t month) | 7 months in 10 |
| Norway total, next month | about 7–8% (11,000 t) | 2 months in 3 |
| One area, last month | about 18% (2,500 t of a 13,000 t month) | 1 in 3 |
| One area, next month | about 20% (2,600 t) | 1 in 3 |
| Fish size, one area, last month | about 6% (0.34 kg of 4.9 kg) | 3 in 4 |

"Usually off by" is the median miss; the full scores are in `ml/RESULTS.md`. The 80% band holds the real figure about 80% of the time for single areas, but only 48–71% of the time for the Norway total in 2025–26, so national bands are too narrow.

## How it was checked

- **Walk-forward:** every forecast is refitted only on data published by its issue date (`available_at`), and the data is never shuffled.
- **No peeking:** tests prove that changing data published after the issue date changes no forecast (`tests/test_ml_supply.py`).
- **Reproducible:** on 8 Nov 2026, a clean environment re-ran the original `ml/challenger` code and matched its committed backtest to about 1e-14. This branch's cut-down code then matched that run exactly (0 differences in 85,811 site values).

## Run it

```bash
pip install -r requirements.txt
python -m analysis.weekly_indices   # weekly lice and temperature tables (also committed here)
python -m ml.supply --final         # backtest 2019-07 to 2026-09, plus the current outlook (about a minute)
python -m ml.export                 # outlook_supply.json, cockpit_ml.json and ml/RESULTS.md
python -m pytest tests
```

`--final` refuses to run while `ml/final_supply.json` exists (delete it to re-run). Before 04:00 on 8 Nov 2026 it also needs `--confirm-freeze`.

## What was removed (compared with `ml/challenger`)

- Price: `price/`, the ML price model, `price.json`, `outlook_price.json`, the price charts and `charts/`.
- The lice-mechanism tests (M1/M2: `analysis/channels.py`, `channels.json`) and the seasonality trap (`analysis/trap.py`).
- The extra comparison models (B0 and B1) and the winner rule, from the ML code and the site files.

Left as they were: `pipeline/` (whole, including its exchange-rate loader), the parts of `analysis/` the model imports, `docs/` and `prereg/`. `analysis/nowcast.py` still contains Production's B0, B1 and F1 code, because the model's features and its linear half come from that module; nothing on this branch runs those parts.

Don't merge this branch into `main` as it is: it would delete the removed work there too.
