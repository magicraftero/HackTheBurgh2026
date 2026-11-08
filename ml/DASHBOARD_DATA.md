# ML challenger data for the dashboards

Three files in `web/public/data/`, written by `python -m ml.export`. They aren't in `docs/plans/00-shared.md` yet; this file is their contract until the team adds them there. The method is fixed in `prereg/ML_PLAN.md`, and the results are in `ml/RESULTS.md`.

Every number can be `null`. Until the 04:00 freeze, `status` is `"development"`, and `scores.holdout`, `national_scores.holdout` and `current` are `null`. No row has `"window": "holdout"`, and `cockpit_ml.json` doesn't exist. Treat each of these as "coming later" for that part only.

| File | View | What it answers |
| --- | --- | --- |
| `outlook_supply.json` | 2. What should a processor expect? | Harvest tonnes, fish count and fish size by area (and nationally), 0–3 months ahead, from six models, with an 80% band and a replay of every past issue date |
| `outlook_price.json` | 3. Does the signal help a buyer? | The export price 1–8 weeks ahead (show 1, 2, 4, 8) from six models, error in NOK/kg, with a band and a replay |
| `cockpit_ml.json` | Farmer cockpit | Lever grids from the ML or blend nowcast. Use them only when `applies` is true; otherwise keep Decision Lab's linear levers |

## `outlook_supply.json`

```json
{"status": "development", "note": "...",
 "models": [{"id": "seasonal", "label": "Seasonal normal"}, {"id": "blend", "label": "Blend (linear + trees)"}],
 "horizons": [{"h": 0, "label": "Last month (not yet published)"}, {"h": 1, "label": "This month"}],
 "units": {"t": "tonnes", "count": "fish", "avg_kg": "kg per fish"},
 "groups": [{"id": "lice", "label": "Lice and treatments"}],
 "band": {"level": 0.8, "model": "blend", "method": "..."},
 "winner": {"model": "blend", "incumbent": "drivers", "challenger_wins": true, "improvement_pct": 2.02, "rule": "..."},
 "areas": {"names": {"6": "Nordmøre og Sør-Trøndelag"}, "forecast": [2, 3, 4], "not_forecast": [1, 13], "reason": "..."},
 "national_label": "Sum of areas 2-12 forecast here (areas [1, 13] excluded)",
 "issue_dates": ["2021-01-10", "..."],
 "scores": {"dev": [{"h": 0, "outcome": "log_kg", "model": "blend", "mae_log": 0.267, "mae": 2419, "unit": "tonnes",
                     "n": 506, "vs_seasonal_pct": 14.3, "coverage_80": 0.82}], "holdout": null},
 "national_scores": {"dev": ["same shape"], "holdout": null},
 "backtest": [{"area": 6, "issued": "2024-10-10", "h": 1, "target": "2024-11", "window": "dev",
               "actual": {"t": 17700, "count": 4100000, "avg_kg": 4.31},
               "pred": {"seasonal": {"t": 16900, "count": 3900000, "avg_kg": 4.5}, "blend": {"...": 0}},
               "band": {"t": [14400, 21200], "count": ["..."], "avg_kg": [4.1, 4.6]},
               "why": {"lice": 3.1, "temperature": -0.9}}],
 "national": [{"issued": "2024-10-10", "h": 1, "target": "2024-11", "window": "dev",
               "actual": {"t": 0, "count": 0}, "pred": {}, "band": {}}],
 "current": null}
```

- **Headline line:** `pred[winner.model]`, with `band` around it. Every other model is a comparison line. The dashboard plan's three series are actual, seasonal baseline (`seasonal`) and biology forecast (`winner.model`).
- **Replay:** pick any of `issue_dates`. Show the forecasts made that day (`backtest` rows with that `issued`, all h), then reveal `actual` and each model's error. One date covers h = 0–3, because a single issue date forecasts four target months.
- **`why`** is the percentage change in this area's kg forecast from that driver group being where it is rather than normal, for the headline model. "Recent harvests" is momentum in the area's own harvest.
- **`national`** sums the forecast areas only, so label it with `national_label`. Its `band` can be `null` early on, because it needs 12 months of national errors.
- **After the freeze,** `current` holds `{made_on, model, status, targets: [{h, target, publishes_around, national, areas: [...]}]}`, where `areas` rows have the `backtest` row shape with `actual` null. Show `status` wherever it appears.

## `outlook_price.json`

```json
{"status": "development",
 "models": [{"id": "rw", "label": "No change"}, {"id": "ar", "label": "Price history + season"},
            {"id": "c0", "label": "Market"}, {"id": "c1", "label": "Market + biology"},
            {"id": "ml", "label": "Gradient-boosted trees"}, {"id": "blend", "label": "Blend (linear + trees)"}],
 "horizons": [{"h": 1, "label": "This week (underway)", "shown": true}, {"h": 3, "label": "3 weeks ahead", "shown": false}],
 "winner": {"model": "ar", "challenger": "blend", "challenger_wins": false},
 "band": {"level": 0.8, "model": "ar"},
 "order_value": "A 1 NOK/kg difference on a 10-tonne order is 10,000 NOK ...",
 "history": [{"week": "2026-W44", "price_nok_kg": 74.98}],
 "scores": {"dev": [{"h": 4, "model": "ar", "mae_log": 0.0756, "mae_nok": 6.32, "ratio_rw": 0.85,
                     "hit_rate": 0.73, "coverage_80": 0.85, "n": 202}], "holdout": null},
 "backtest": [{"origin": "2021-W15", "origin_date": "2021-04-21", "h": 1, "target": "2021-W16", "window": "dev",
               "actual": 61.13, "pred": {"rw": 60.99, "ar": 60.2}, "band": [56.72, 64.05]}],
 "current": null}
```

- Every price is NOK/kg. The horizon selector shows the rows with `shown: true`. Beside the forecast, show `mae_nok` for each model at that h, on the same weeks (the rows are matched).
- **Order-value calculator:** (difference in NOK/kg) × tonnes × 1,000, labelled as a purchase scenario (see `order_value`).
- A result where biology adds nothing, or makes things worse, stays visible (dashboard plan, view 3). On the dev window, c1 is worse than "no change", and ML doesn't beat `ar`.
- **After the freeze,** `current` holds `{origin, model, status, targets: [{h, target, check_on, pred, band, why: {ml: {...}, c1: {...}}}]}`. `check_on` is the Statistics Norway release day for that week.

## `cockpit_ml.json` (after the freeze only)

```json
{"target_month": "2026-10", "model": "blend", "applies": true, "status": "...", "disclaimer": "...", "how": "...",
 "levers": [{"id": "lice", "label": "Mobile lice per fish", "unit": "lice per fish"}],
 "areas": [{"area": 6, "levers": [{"id": "lice", "feature": "mobile_anom", "current": 0.61,
            "grid": [0.12, "... 9 values ...", 0.74],
            "delta_log": {"log_kg": [-0.03, "...", 0.02], "log_count": ["..."], "log_avg_kg": ["..."]}}]}]}
```

- The lever ids, labels, units and ranges are Decision Lab's, so the same sliders work. Take the baseline from `outlook_supply.json` → `current` (h = 0, `pred[model]`), or from Decision Lab's `baseline.log` when `applies` is false.
- **Scenario:** `log_kg = log(baseline_kg) + Σ interp(value, grid, delta_log.log_kg)`, and the same for count and avg_kg. Each lever is swept with the others held at current values, so the sum is an approximation when several levers move together.
- Outside `grid`, show "outside past experience", as Decision Lab does. Lever effects are associations, not the effect of an action: keep Decision Lab's disclaimer wording.
