# Production data preparation

Built as of 2026-11-08; no model scores computed.

| Table | Rows |
| --- | ---: |
| weekly_area_index | 10,062 |
| weekly_national_index | 774 |
| drivers_area_month | 1,404 |
| drivers_national_month | 108 |
| area_month_panel | 1,404 |
| nowcast_features | 897 |
| nowcast_targets | 1,404 |
| nowcast_vintages | 66,378 |

| Model inputs | Complete forecast rows | Total |
| --- | ---: | ---: |
| b0 | 897 | 897 |
| b1 | 897 | 897 |
| drivers | 835 | 897 |

| Model | Log kg forecastable | Log count forecastable | Log weight forecastable |
| --- | ---: | ---: | ---: |
| b0 | 784 | 784 | 784 |
| b1 | 784 | 784 | 784 |
| drivers | 737 | 737 | 737 |

416 missing capacities use area medians for weighting; source tables stay intact.
83 zero-harvest area-months retain null average weights and log labels.
1061 farm-week rows excluded because they are not published as of the build date.

Treatment reporting diagnostic, W46–W09 a year apart: 8.54% → 11.65% of reporting farms treated.

- 83 area-months have zero harvest (avg_kg is null).
- Stored panel/driver anomalies use full-sample fits and are for descriptive analysis only.
- nowcast_vintages refits anomalies from published levels for each forecast month; target labels remain null.
- nowcast_features is the target subset of those vintages, not a substitute for each vintage's training rows.
- Targets are latest revised figures. Historical source vintages and farm capacity histories are unavailable.
- Zero-harvest outcomes have missing log labels; do not replace those with zero or log1p for the F1 nowcast.
- Temperature bands need 3 previous years of same-ISO-week temperatures and 6 consecutive valid weeks.
- Missing weeks (especially ISO week 53) can leave temperature bands and nowcast predictors unavailable.
- Treatment format changed in 2024-W46; the seasonal comparison is diagnostic, not proof of comparability.
- Area 13's descriptive weight anomaly is unavailable when its sparse positive harvests cannot support the registered seasonal fit.
- This preparation command does not train or score nowcast models.
