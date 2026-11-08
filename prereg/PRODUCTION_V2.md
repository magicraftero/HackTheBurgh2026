# Production v2 (top-down): design fixed before it is built

Exploratory. Committed before the v2 code exists and before any v2 holdout score. Nobody edits
this file after that commit. It changes nothing in `prereg/PASS_MARKS.md`: F1 is judged on the
Drivers model exactly as written there.

## Disclosure

- The team opened the 2025-2026 holdout early, at 23:47 on 7 Nov 2026 (`ml/RESULTS.md`).
- This design comes from a short exploration on 2021-2024 only (00:17-00:23 on 8 Nov). Holdout
  scores for other models were first read at about 00:24, after the design below was tested.
- The design is exactly the one tested on 2021-2024. Nothing is changed after its holdout score is
  seen. Its holdout score is reported as "designed after the holdout was opened by the team".

```text
PRODUCTION V2: TOP-DOWN NOWCAST OF AREA HARVEST VOLUME

TARGET
log harvest kg for areas 1-13, month t. Same timing as analysis/nowcast.py: forecast date
D(t) = the 10th of month t+1; Directorate data only up to month t-1; weekly rows only if
available_at <= D(t).

STEP 1, NATIONAL TOTAL FROM EXPORTS
E(t) = Statistics Norway weekly export volume (tonnes x 1000) summed over the weeks whose Thursday
falls in month t, using only weeks with available_at <= D(t). If any such week is missing, no
forecast.
H(m) = sum of harvest_kg over areas 1-13 in month m.
ratio = mean of log(H(m) / E(m)) over the 12 months m = t-12 .. t-1 (at least 6 present).
N(t) = E(t) x exp(ratio).

STEP 2, AREA SHARES
s_a(m) = harvest_kg_a(m) / H(m). Inputs for area a, month t (all known at D(t)):
  x1 = log(b_a(t-1) + 0.001), b_a = area biomass / sum of biomass over areas 1-13, month t-1
  x2 = log(s_a(t-1) + 0.001)
  x3 = log(s_a(t-12) + 0.001)
  x4 = log(biomass_a(t-1) / fish_stock_a(t-1))   (average weight of fish in the water)
Model: OLS of log(s_a(m) + 0.001) on a constant and x1-x4, pooled over areas, fitted on all
target months m <= t-1 with complete inputs; refitted every month (walk-forward). At least 3
training rows per parameter.
Share forecast: exp(fitted value), divided by its sum over the areas forecast in month t.

STEP 3, COMBINE
topdown(a, t) = log(N(t) x share_a(t)).
v2(a, t) = mean of topdown(a, t) and B1(a, t) in log space, where B1 exists. Where B1 has no
forecast (for example areas 1 and 13), topdown alone is reported separately, not mixed into the
matched comparison.

SCORING
MAE on log kg against the latest revised actuals, months with harvest > 0.
Windows as in PASS_MARKS: dev 2021-01 to 2024-12, holdout 2025-01 to 2026-09.
Reported on (a) the rows of analysis/nowcast.py where B1, Drivers, topdown and v2 all exist, and
(b) the matched rows of ml/RESULTS.md (h = 0) where Nikita's ml and blend also exist.
Models compared: B1, Drivers, ml, blend, topdown, v2. Also the national total error of N(t).
Leakage alarm: if v2 is more than 20% better than B1 on dev, check for leakage before publishing.
Run once on the holdout. No input, constant or rule changes after that.
```
