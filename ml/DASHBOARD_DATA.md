# Harvest model data for the site

Two files in `web/public/data/`, written by `python -m ml.export`. They aren't in `docs/plans/00-shared.md`; this file is their contract. The model is described in `ml/README.md` and fixed in `prereg/ML_PLAN.md`, and its scores are in `ml/RESULTS.md`.

Every number can be `null`.

| File | What it answers |
| --- | --- |
| `outlook_supply.json` | Harvest tonnes, fish count and fish size by area and for Norway, 0–3 months ahead, with an 80% band and a replay of every past issue date |
| `cockpit_ml.json` | Farmer cockpit: how the model's nowcast moves when one lever (lice, treatments, temperature, disease) changes |

## `outlook_supply.json`

```json
{"status": "final", "note": "...", "model": "blend",
 "models": [{"id": "seasonal", "label": "Seasonal normal"}, {"id": "blend", "label": "Harvest model (linear + trees)"}],
 "horizons": [{"h": 0, "label": "Last month (not yet published)"}, {"h": 1, "label": "This month"},
              {"h": 2, "label": "Next month"}, {"h": 3, "label": "In two months"}],
 "units": {"t": "tonnes", "count": "fish", "avg_kg": "kg per fish"},
 "groups": [{"id": "lice", "label": "Lice and treatments"}],
 "windows": {"dev": ["2021-01", "2024-12"], "holdout": ["2025-01", "2026-09"]},
 "band": {"level": 0.8, "model": "blend", "method": "..."},
 "areas": {"names": {"6": "Nordmøre og Sør-Trøndelag"}, "forecast": [1, 2, 3], "not_forecast": [13], "reason": "..."},
 "national_label": "Sum of areas 2-12, the areas forecast every month (areas [1, 13] excluded)",
 "issue_dates": ["2021-01-10", "..."],
 "scores": {"dev": [{"h": 0, "outcome": "log_kg", "model": "blend", "mae_log": 0.267, "mae": 2419, "unit": "tonnes",
                     "n": 506, "vs_seasonal_pct": 14.3, "coverage_80": 0.82}], "holdout": ["same shape"]},
 "national_scores": {"dev": ["same shape"], "holdout": ["same shape"]},
 "backtest": [{"area": 6, "issued": "2024-12-10", "h": 2, "target": "2025-01", "window": "holdout",
               "actual": {"t": 15320, "count": 3361000, "avg_kg": 4.558},
               "pred": {"seasonal": {"t": 18600, "count": 3987000, "avg_kg": 4.665},
                        "blend": {"t": 17510, "count": 3787000, "avg_kg": 4.637}},
               "band": {"t": [11680, 26580], "count": [2530000, 5769000], "avg_kg": [3.993, 5.182]},
               "why": {"stock": -7.8, "lice": -0.9, "temperature": 1.5}}],
 "national": [{"issued": "2024-12-10", "h": 2, "target": "2025-01", "window": "holdout",
               "actual": {"t": 109700, "count": 23670000},
               "pred": {"seasonal": {"t": 111600, "count": 23420000}, "blend": {"t": 113900, "count": 23890000}},
               "band": {"t": [105200, 126200], "count": [22030000, 27050000]}}],
 "current": {"made_on": "2026-11-08", "model": "blend", "status": "unverifiable until the Directorate publishes each month",
             "targets": [{"h": 2, "target": "2026-12", "publishes_around": "2027-01-20",
                          "national": {"pred": {"blend": {"t": 137800}}, "band": {"t": [129600, 158600]}},
                          "areas": ["backtest row shape, actual null"]}]}}
```

- **Forecast line:** `pred[model]` (`"blend"`), with `band` around it. `pred.seasonal` is the reference line: a normal month for that area and time of year.
- **Replay:** pick any of `issue_dates`. Show the forecasts made that day (`backtest` rows with that `issued`, all h), then reveal `actual` and the error. One date covers h = 0–3, because a single issue date forecasts four target months.
- **`why`:** the percentage change in this area's tonnes forecast from that driver group being where it is rather than normal. "Recent harvests" is momentum in the area's own harvest.
- **`national`:** sums the areas forecast every month, so label it with `national_label`. Its band is too narrow on 2025–26 (it held the real figure 48–71% of the time, not 80%), so show it with a caution or not at all.
- **`current`:** forecasts made on `made_on` for months not yet published. `areas` rows have the `backtest` row shape with `actual` null. Show `status` wherever it appears.

## `cockpit_ml.json`

```json
{"target_month": "2026-10", "made_on": "2026-11-08", "model": "blend", "status": "...", "disclaimer": "...", "how": "...",
 "levers": [{"id": "lice", "label": "Mobile lice per fish", "unit": "lice per fish"}],
 "areas": [{"area": 6, "levers": [{"id": "lice", "feature": "mobile_anom", "current": 0.739,
            "grid": [0.1881, "... 9 values ...", 1.162],
            "delta_log": {"log_kg": [-0.038, "...", 0.037], "log_count": ["..."], "log_avg_kg": ["..."]}}]}]}
```

- The lever ids, labels, units and ranges are Decision Lab's, so the same sliders work.
- **Baseline:** `outlook_supply.json` → `current`, the h = 0 target, `pred.blend`.
- **Scenario:** `log_kg = log(baseline_kg) + Σ interp(value, grid, delta_log.log_kg)`, and the same for count and avg_kg. Each lever is swept with the others held at their current values, so the sum is an approximation when several levers move together.
- Areas 1 and 13 are listed with empty `delta_log` (the model doesn't forecast them): hide them.
- Outside `grid`, show "outside past experience". Lever effects are associations, not the effect of an action, so keep the disclaimer wording.
