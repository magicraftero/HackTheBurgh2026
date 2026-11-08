# Identified seasonal reconstruction

The development-only audit found a preparation defect before any nowcast
model or challenger was evaluated. The seasonal adjustment originally checked
the number of residual observations but did not check whether its registered
calendar design was identified.

For area 1, the January–April 2021 forecast vintages had 9–12 valid monthly
harvest residuals for an eight-column seasonal design of rank seven. No usable
residual supported the Easter column. The minimum-norm least-squares solution
still returned finite coefficients, some with absolute magnitudes near 767.
The March 2021 target log-kg base was about −242.60, compared with typical
log-kg bases around 15–17 in the other areas. Those unstable transformations
also affected historical area-1 rows used in the pooled regression.

`analysis.anomalies._fit_season` now requires full column rank and a finite
condition number no greater than `1e10`. Calendar design columns have bounded,
comparable scales. A failed identification check raises a clear `ValueError`
with the existing “Not enough usable observations” prefix. Existing preparation
and Price callers therefore preserve their error-handling interface and mark
the affected adjustment unavailable. No registered seasonal term, outcome
transform, feature, pass mark or lag window was changed.

The compatible correction is to report unavailable data, not to drop a holiday
column, regularise the seasonal model, clip predictions, or fill missing bases.
The dated forecasts and supporting tables can be regenerated with:

```sh
.venv/bin/python -m analysis.prepare --as-of 2026-11-08
.venv/bin/python -m analysis.checks
```

This numerical guard does not guarantee stable statistical extrapolation.
Area 1's May 2021 seasonal fit is full rank with condition number about 145 and
only 13 residual observations. It can still extrapolate poorly; finite extreme
predictions and their resulting errors must be retained and reported. Area 13
has no usable reconstruction base throughout the development forecast window,
because its positive harvest history is too sparse for the specified trailing
level and seasonal fit. Ridge or CatBoost in the prediction stage cannot
recover an unavailable seasonal reconstruction.

Tests exercise an unidentified holiday column and a full-rank but
catastrophically ill-conditioned seasonal design. `VintageStore` additionally
audits publication dates, target-label isolation, sparse-area coverage, and
chronological Parquet filters. Default reads materialise only development
vintages and labels; snapshot rows are repeated histories, not independent
observations.
