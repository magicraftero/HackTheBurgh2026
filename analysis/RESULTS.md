# Results

What we predicted, how well, which hidden patterns we found, and what failed. Numbers come from
`web/public/data/nowcast.json`, `combined.json`, `channels.json`, `trap.json`, `farmer_actions.json`
and `data/processed/mechanism_sensitivity.json`.

Errors are mean absolute error (MAE) in log points. For small errors, 0.20 means "typically about
20% off", so we also write it as "about 80% accurate".

## Disclosures first

- **The holdout was opened early.** The pre-registration put the one locked holdout run at 04:00 on
  8 November. The team agreed to open it at 23:47 on 7 November. The official F1 run used
  `--confirm-freeze` and its result is reported below exactly as it came out.
- **The v2 model was designed after F1 failed, using only the development window (2021-2024).**
  Its design is fixed in `prereg/PRODUCTION_V2.md` (commit `6b5b4a0`) before it was run on the
  holdout. It is not a pre-registered pass mark, and we don't claim it as one.
- **The combination rule** (v2 kilograms, ML weight) was chosen on the development window before
  the combination's holdout scores were read.
- Actuals are the latest revised Directorate figures, not the first releases.

## 1. Pre-registered tests (`prereg/PASS_MARKS.md`)

| Test | What it asked | Result |
|---|---|---|
| F1 | Do biology drivers beat the seasonal baseline (B1) by at least 5% on kilograms? | **Fail.** 3.19% better (0.2337 vs 0.2414), Clark-West p = 0.00035 |
| M1, weight | Do high lice lead to smaller harvested fish within 0-3 months? | **Pass.** Sum of coefficients −0.22, 95% interval −0.37 to −0.07 |
| M1, count | Do high lice lead to more fish harvested? | **Fail.** −1.06, interval −3.16 to 1.04 |
| M2 | Does extra warmth below 14 °C raise harvest weight 1-3 months later? | **Fail.** +0.00016, interval includes zero |

F1 fails because the improvement is real (p is tiny) but smaller than the 5% bar we set. M1 as a
whole fails because it needed both halves; only the weight half passes. Treatment rows in M1 were
descriptive (no pass mark) and show no clear effect.

**Sensitivity check, not a pass mark** (areas 1 and 13 excluded, chosen before M1/M2 results):
the lice weight effect holds (−0.24, interval −0.40 to −0.09). The lice count effect turns
positive (+0.28, interval −0.03 to 0.60) but still includes zero. Areas 1 and 13 have many
zero-harvest months, which give extreme count anomalies.

## 2. Forecast accuracy: harvest per area, next month

Holdout window 2025-01 to 2026-09, 231 matched area-months.

| Model | Kilograms | Fish count | Average weight |
|---|---|---|---|
| B1: same month last year, seasonal | 0.241 | 0.249 | 0.087 |
| Drivers (our F1 model) | 0.234 | 0.232 | 0.076 |
| ML challenger (Nikita) | 0.222 | 0.217 | **0.070** |
| ML blend | 0.222 | 0.218 | 0.070 |
| **Combined: v2 kilograms + ML weight** | **0.199** | **0.205** | **0.070** |

On the development window (341 area-months) the combined model scores 0.219 on kilograms against
B1's 0.251, so it isn't a holdout fluke.

In plain words: the combined model is about **80% accurate** on kilograms and fish count per area,
and about **93% accurate** on average fish weight. That is 17% less error than the seasonal
baseline on kilograms.

**Why v2 wins:** it reads Statistics Norway's weekly export figures, which are published about
9 days after each week. The Directorate's monthly harvest figures are published about 50 days
after the month starts. So by the time we forecast, exports already reveal most of the national
harvest. v2 converts exports to harvest with a trailing 12-month ratio, then splits the national
total across areas using biomass, last month's share, last year's share and fish weight.

## 3. Hidden patterns

1. **We see the harvest six weeks before it's published.** Weekly exports reveal Norway's
   monthly harvest to within about 10% (national error 0.104 on development, 0.083 on the
   holdout), roughly six weeks before the official figures.
2. **Lice force early harvests of smaller fish.** After high-lice months (top third against the
   middle third), areas harvested +8.2% fish at −1.3% average weight over the next 0-3 months. The
   weight part passes M1.
3. **Deaths come before emergency harvests.** After high-mortality months, +8.3% fish harvested at
   −1.7% weight.
4. **Cold seas slow everything.** After cold spells, −5.8% fish at −0.7% weight 1-3 months later.
5. **Heavy stock signals a harvest wave** (exploratory, found while building the farmer page).
   When fish in the water are heavier than in 80% of an area's past months, the next month's
   harvest takes about 7% more of the stock than usual for that time of year.
6. **The seasonality trap.** Raw disease and harvest series correlate at r = −0.67, but most of
   that is both following the seasons. After removing the seasonal pattern the correlation falls to
   r = −0.28. Anyone reading raw charts would overstate the link by more than double.

## 4. Live forecast: October 2026

Made on 8 November 2026. Official figures are due around 20 November.

- **National (areas 2-12): about 198,300 tonnes.**
- Areas 1 and 13 have no forecast: their harvest is too irregular (many zero months).
- Each area's forecast, range and current signals are in `web/public/data/farmer_actions.json`
  and in the cockpit.

## 5. My farm cockpit (prototype)

`cockpit/` is a standalone page, separate from the main site and styled to match it. You set up
your own farm (area, fish, average weight, month) and the conditions (lice, deaths, sea
temperature). It shows next month's harvest from your farm, its value at last week's export
price, an animated pen, and a step-by-step waterfall from a typical month to yours. Each step is
one of the measured patterns above. The page carries a disclaimer: these are patterns, not
guarantees or advice.

Build its data with `python -m analysis.farmer`, then `python -m analysis.cockpit`. Serve it with
`python -m http.server --directory cockpit` and open the printed address.
