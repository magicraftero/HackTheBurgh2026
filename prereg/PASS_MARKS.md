# Pass marks

Committed before any model was run on real outcome data. Nobody edits this file after that commit.

```text
Pass marks: committed before any results were looked at.

COMMON DEFINITIONS
Units: production area × month, Oct 2017 – Sep 2026, 13 areas (the "(null)" row excluded).
Anomalies: logs, minus a trailing 12-month level (52 weeks for weekly series), Fourier
seasonality and holiday terms (Easter; Christmas for weekly series).
Drivers: biomass and fish numbers; smolt released 12–23 months earlier; feed per kg of
biomass; deaths per 1,000 fish; capacity-weighted mobile lice per fish; treatments per active
farm-week; share of reporting sites with ISA or PD (only if the data exists); sea-temperature
degree-day anomaly = 6-week rolling sum of 7 × (weekly sea temperature − that area's mean for
the same ISO week in previous years), split into bands by the current week's temperature
(below 8 °C, 8–14 °C, 14 °C and above); national export volume.
Nowcast timing: made on the 10th of the following month, using only data published by then.
Baselines: B0 = season plus biomass and fish numbers at the end of the previous month.
B1 = B0 plus that month's national export volume. Drivers = B1 plus every other driver.

EVALUATION WINDOWS AND THE HOLDOUT
Every forecast test is a walk-forward backtest that simulates real time: each forecast uses
only data published by its forecast date, and models are refitted on that data alone.
Production: development window Jan 2021 – Dec 2024; holdout Jan 2025 – Sep 2026.
Price: development window 2021-W01 – 2024-W52; holdout 2025-W01 – 2026-W44. (Features from the
Directorate start in late 2018, so earlier origins would have almost no training data.)
Holdout results are not computed or looked at before the analysis freeze (04:00 on 8 Nov 2026).
At the freeze the full backtest runs once. F1 and F2 are judged on the holdout; results for the
development window are reported alongside.

FORECAST TESTS (THE MAIN FOCUS)
F1 (primary, production). On the holdout, the Drivers model's nowcast of each area's harvest
volume (log kg) has at least 5% lower mean absolute error than B1, and the Clark–West test
(squared error, averaged across areas each month, Newey–West with 3 lags) rejects at 5%,
one-sided. Fish count and average weight are reported separately.
F2 (secondary, price). On the holdout, at 4 weeks ahead, c1 (c0 plus the drivers below) has at least
5% lower mean absolute error than c0 (past prices, export volume, average harvest weight,
EUR/NOK), and the Clark–West test (squared error, HAC with h − 1 lags) rejects at 5%,
one-sided. c1 adds national mobile lice, treatments, disease share, temperature bands, biomass,
feed per kg of biomass, deaths per 1,000 fish and the USD/NOK change. The other horizons
(2, 3, 5, 6, 7 and 8) are reported with a Holm correction.

MECHANISM TESTS (HOW DRIVERS MOVE PRODUCTION)
Panel: fixed effects for area × calendar month and month × year; Driscoll–Kraay errors,
bandwidth 12; controls: biomass and fish-number anomalies four months earlier.
M1 (lice signature). Holding temperature bands and treatments fixed, the sum of mobile-lice
coefficients at lags 0–3 months is above zero for log fish harvested and below zero for log
average weight, each with a 95% interval that excludes zero.
M2 (growth). In the temperature-only model, the sum of coefficients on the degree-day anomaly
below 14 °C (bands below 8 °C and 8–14 °C combined) at lags 1–3 months is above zero for log
average weight, with a 95% interval that excludes zero.
M3 (exploratory, price). Lice pressure lowers price at 0–6 weeks and raises it at 13–26 weeks;
both one-sided tests must reject.
Driver ranking (exploratory, no pass mark): the rise in walk-forward error over Jan 2021 –
Sep 2026 when each driver group is left out, computed at the freeze.

Lag windows are fixed above, not chosen from data. Price lag lengths are chosen on 2012–2018
data only.
```
