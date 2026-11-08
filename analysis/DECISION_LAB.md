# `decision_lab.json`: data for the farmer decision cockpit

Production writes `web/public/data/decision_lab.json` with `python -m analysis.decision_lab`. It isn't in `docs/plans/00-shared.md` yet; this file is its contract until the team adds it there.

## What the cockpit shows

For each production area, the file has:

- the nowcast for the month after the latest Directorate release (October 2026 today), with an 80% range;
- why the forecast differs from a normal month, by driver group;
- levers (lice, treatments, sea temperature, and disease if the data has it) that the user can move to see how the forecast changes;
- the latest signals, with warning flags;
- the last 24 months of actual harvests.

The forecast can't be checked until the Directorate publishes the month (`publishes_around`). Show `status` and `disclaimer` wherever the forecast appears. Lever effects are predictive associations, not the effect of an action: say "areas with more lice have tended to harvest…", never "treating will cause…".

## Recomputing a scenario in the browser

The model is linear in anomalies, so the site recomputes any scenario instantly:

```ts
const T = (transform: string, v: number) => (transform === "log1p" ? Math.log1p(v) : v);

function scenarioLog(area, levers, outcome /* "log_kg" | "log_count" | "log_avg_kg" */, values /* {leverId: newValue} */) {
  let y = area.baseline.log[outcome];
  for (const meta of levers) {
    const lever = area.levers.find((l) => l.id === meta.id);
    const v = values[meta.id];
    if (v === undefined || lever.current === null || lever.coef[outcome] === null) continue;
    y += lever.coef[outcome] * (T(meta.transform, meta.scale * v) - T(meta.transform, meta.scale * lever.current));
  }
  return y;
}
// kg = Math.exp(scenarioLog(...,"log_kg",...)); range = [kg * Math.exp(model.interval.log_kg[0]), kg * Math.exp(model.interval.log_kg[1])]
```

With every lever at `current`, this returns `baseline.log` exactly. Keep sliders inside `range` (the area's 5th to 95th percentile). Outside it, show an "outside past experience" warning rather than blocking. A lever with `current: null` or `coef: null` is unavailable for that area.

## Shape

Every number can be `null`. All numbers are 4 significant figures, except `baseline.log`, which has 6 decimals.

```json
{
  "target_month": "2026-10",
  "made_on": "2026-11-07",
  "publishes_around": "2026-11-20",
  "status": "unverifiable until the Directorate publishes this month",
  "disclaimer": "Scenario forecasts from a model trained on public data. …",
  "formula": "forecast_log[o] = baseline.log[o] + …",
  "model": {
    "name": "drivers",
    "features": ["biomass_anom_l1", "…"],
    "n_train": {"log_kg": 820, "log_count": 820, "log_avg_kg": 820},
    "interval": {"level": 0.8, "source": "development-window walk-forward errors",
                 "log_kg": [-0.21, 0.18], "log_count": [-0.22, 0.2], "log_avg_kg": [-0.05, 0.05]},
    "dev_mae": {"log_kg": 0.15, "log_count": 0.16, "log_avg_kg": 0.04}
  },
  "levers": [
    {"id": "lice", "label": "Mobile lice per fish", "unit": "lice per fish", "transform": "log1p", "scale": 1,
     "evidence": {"ranking_increase_pct": 6.7, "mechanism_tests": [{"test": "M1", "pass": true, "…": "…"}]}}
  ],
  "national": {"label": "Areas 2-12 (areas 1 and 13 harvest too irregularly to forecast)",
               "areas": [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
               "kg": 180000000, "count": 39000000, "avg_kg": 4.6,
               "kg_range": [150000000, 210000000]},
  "areas": [{
    "area": 6, "name": "Nordmøre og Sør-Trøndelag",
    "baseline": {"log": {"log_kg": 16.69, "log_count": 15.17, "log_avg_kg": 1.52},
                 "kg": 17700000, "kg_range": [14400000, 21200000],
                 "count": 3900000, "count_range": [3100000, 4800000],
                 "avg_kg": 4.55, "avg_kg_range": [4.3, 4.8]},
    "why": [{"group": "lice", "label": "Lice and treatments", "kg_pct": 3.1, "count_pct": 4.0, "avg_kg_pct": -0.9}],
    "levers": [{"id": "lice", "current": 0.61, "percentile": 82, "range": [0.12, 0.74], "band": null,
                "coef": {"log_kg": 0.09, "log_count": 0.11, "log_avg_kg": -0.02}},
               {"id": "temperature", "current": 14.2, "percentile": 70, "range": [-20.5, 22.1], "band": "8to14",
                "coef": {"log_kg": 0.002, "log_count": 0.001, "log_avg_kg": 0.0004}}],
    "signals": {"lice": {"value": 0.61, "unit": "lice per fish", "month": "2026-10", "percentile": 82},
                "treatments": {"…": "…"}, "sea_temp": {"…": "…"}, "temp_anomaly": {"…": "…"},
                "mortality": {"value": 9.8, "unit": "deaths per 1,000 fish", "month": "2026-09", "percentile": 91},
                "feed_rate": {"…": "…"}},
    "flags": [{"id": "lice_high", "signal": "lice", "label": "Lice pressure is in the top fifth of this area's history", "severity": "warning"}],
    "history": [{"month": "2024-10", "kg": 18100000, "count": 4000000, "avg_kg": 4.52}]
  }]
}
```

## Field notes

- `why[].kg_pct` is how far that driver group moves this month's forecast from a normal month for the area, in percent. The list is sorted by size. Season, trend and stock are already in the baseline.
- `levers[].band` applies only to temperature: the effect uses the coefficient for the area's current temperature band (`below8`, `8to14` or `above14`).
- `signals[].percentile` compares the value with the area's own past months. Mortality and feed are from the previous month, because the Directorate publishes them later; they're signals, not levers.
- `flags` are transparent rules: a signal at or above the area's 80th percentile (and, for temperature, at or below the 20th). They aren't model output.
- `evidence` is `null` until the 04:00 freeze, when the driver ranking (`drivers.json`) and the mechanism tests (`channels.json` → `panel`) exist. Rerun `python -m analysis.decision_lab` after the freeze to fill it.
- The range uses development-window (2021–2024) backtest errors only, never the holdout.
