# Lice → Supply → Price: build plan for HackTheBurgh XIII

> **Superseded.** This was the first-pass plan. The current plan is `docs/designs/salmon-production-price-build-plan.md`, with role plans for each coding agent in `docs/plans/`. This file is kept only for reference.

For the team · Saturday 7 Nov · Times assume about 17 hours left, with submissions around 11:00 on Sunday. If the deadline is different, keep the first two checks at +4 h and +8 h from now and move the overnight blocks.

## The short version

- **Keep the idea.** It covers both halves of the theme. Sea lice can't be seen, the farm data is public but almost nobody reads it, and the lice effect on supply only shows up once harvest is split into fish count × average weight. The prediction is a nowcast of Norway's official harvest figures, made weeks before they're published.
- **Cut the build hard.** v2 is a research programme. By +8 h, get a basic demo (Tier 1) onto the live site that works even if every model fails. Add the statistics after that.
- **Order the demo: map first, supply as the headline, and price as the honest second act.**
- **Split the team 2 front end + 2 back end.** Agree a JSON contract in the first hour so the front end never waits on the back end.
- **No official figures come out during the event.** Commit the predictions to git so their timestamp is fixed (we call these "sealed" predictions below), and show judges a replay of the 2021–2026 backtest.

## Next 60 minutes

1. Pick roles (see Team below). Whoever could go either way takes **Story**. It's the role closest to the data, so that person can help the back end if the data check fails.
2. **Data & Price:** create the BarentsWatch account and API client, get a token, make one test call, then start the bulk lice pull. Do 2026 back to 2017 first and 2012–2016 after. While it runs, load Statistics Norway 03024 and EUR/NOK.
3. **Everyone:** commit the pass marks (at the bottom of this file) before anyone looks at any results.
4. **All four, 10 minutes:** agree the data contract. The front end builds on mock files with those shapes.
5. **Map:** set up the app and deploy an empty page now, so any deployment problems show up tonight rather than at 08:00.
6. **Supply:** load the Directorate CSV (see the notes below) and write the anomaly function.
7. **Story:** build the page skeleton with the four demo beats and placeholder charts. Check the challenge list, and enter any data, forecasting or visualisation challenge the rules allow.

## Review of v2

**Keep**

- The three kinds of "invisible": the parasites, the unread data, and an effect hidden inside total harvest volume. Name all three in the pitch.
- Pass marks set in advance, and the "market already prices public biology" fallback. Both are rare at a hackathon, and judges with a statistics background will notice.
- The trap slide. In 20 seconds it shows you didn't fool yourselves.
- Supply as the main test. That's where the signal is.

**Change**

1. **Scope.** Five nested price models, six tests, a bootstrapped panel, a lead–lag chart and nine demo items add up to weeks of work. Use the tiers below.
2. **The supply baseline leaves out weekly exports.** Statistics Norway publishes export volume every Wednesday, so most of the national volume for the month just ended is known before the Directorate's release. A judge from a trading firm will ask about this. Add a second baseline, B1, which is B0 plus that month's export volume. Where biology can win is by area and in the count/weight split, not national volume.
3. **H1's sign for fish count is ambiguous if treatments drive it.** Zhang et al., one of your own sources, find that harvests speed up as lice rise but slow down during delousing, and v2's channel table predicts fewer fish during delousing. Make mobile lice the H1 variable, and put treatments in the same regression to capture the delousing effect.
4. **The pass marks still leave room to choose after seeing results.** Define H1 and H2 as sums of lag coefficients (lags 0–3 and 1–3). Fix the supply lag windows now: area data before 2019 covers only 15 months, so "choose lags on pre-2019 data" can only work for price. H3's 5% threshold is on mean absolute error, but Clark–West tests squared error, so state both. The pass-mark text at the bottom does all of this.
5. **The live test.** The Directorate publishes October's figures around Friday 20 Nov, and Statistics Norway's next price comes out on Wednesday 11 Nov, both after the event. Seal both predictions and demo a replay instead. The backtest is scored on revised data, but the live test will be scored on a first release, which tends to understate the figures. Expect the live error to look a little worse, and say so.
6. **Model complexity.** ARIMA errors and the Bayesian model (d) would cost hours without changing the answer. Use direct OLS for each horizon, and build the fan chart from the quantiles of past walk-forward errors.
7. **Demo.** Nine deliverables don't fit in three minutes. Use four beats, and let the site be the pitch.
8. **Pitch opener.** The snow crab story takes ten seconds to land and isn't on screen. Open on the moving map, keep the Scottish salmon line, and save snow crab for Q&A.

**Directorate file (checked 7 Nov)**

- The file is `;`-separated UTF-8 with a byte-order mark: `pd.read_csv(path, sep=";", encoding="utf-8-sig")`. Key columns: `ÅR`, `MÅNED_KODE`, `PO_KODE`, `ARTSID`, `UTSETTSÅR`, `UTTAK_STK`, `UTTAK_KG`, `BIOMASSE_KG`, `BEHFISK_STK`, `UTSETT_SMOLT_STK`, `DØDFISK_STK`.
- It includes rainbow trout, so keep only `ARTSID == "LAKS"`.
- There is one row per area per stocking year (`UTSETTSÅR`), so sum over stocking years.
- **No areas are hidden**, unlike v2 assumed. All 13 areas appear in all 108 months (Oct 2017–Sep 2026). Suppressed rows go into a separate row with `PO_KODE == "(null)"` that holds 1–5% of harvest (about 1–2% since 2021). Count it in national totals and leave it out of the area panel. No merging is needed.
- `UTTAK_KG` is round-weight equivalent (gutted weight × 1.125, plus fish reported in round weight), so `UTTAK_KG / UTTAK_STK` gives live weight per fish.
- The latest month is September 2026. Statistics Norway table 03024 runs to week 44 of 2026 (updated Wednesday 4 Nov). Fresh salmon is `VareGrupper2 = 01`, with columns `Vekt` (tonnes) and `Kilopris` (NOK/kg).
- **A hook to check, not yet a finding.** September 2024 had the most fish harvested (42.5 m) and the lowest average weight (4.28 kg) of any September from 2018 to 2026, during one of the hardest lice seasons in a decade. Harvest counts rise year on year, so confirm this with anomalies and the lice index before using it.

## Team

Recommended: **2 front end + 2 back end.** Judges score what they can see, which is the front end, and with the cuts below two people can cover the analysis.

| Role | Owns | By +4 h | By +8 h | Before the freeze |
| --- | --- | --- | --- | --- |
| **Data & Price** (back end) | BarentsWatch pull, data loaders, farm-to-area mapping, publication dates, map exports, price track | Clean farm-week lice table from 2017; `farms.json`, `farm_weeks.json` | Price models a, b, c0 and c1, walk-forward | Clark–West test, fan chart, sealed price forecast |
| **Supply** (back end) | Anomalies, Lice Pressure Index, trap numbers, nowcast, H1/H2 panel | Anomaly function; `area_month.json` | Index v1, trap, descriptive count × weight, nowcast backtest | H1/H2 panel; sealed October nowcast |
| **Map** (front end) | App, deployment, farm map, prediction view | Real farm locations, time slider, mock lice | Real lice by week, play button, treatment rings, click a farm, two bookmarks | Prediction view; performance |
| **Story** (front end) | Page flow, charts, copy, pitch, Devpost, backup video | Page skeleton; count × weight chart on real Directorate data | Trap and nowcast charts on real data | Two-channel chart, scorecard, fan chart; leads the pitch |

**If you go 1 front end + 3 back end instead:** the third back-end person takes the whole price track. The front-end person builds the map and the page, and the back-end people make the charts in Python with Altair, whose chart specs the page can embed directly. Whoever is the best speaker owns the pitch, whatever their role.

## How it fits together

- **No live server.** Python precomputes everything into static JSON files in `web/public/data/`, and the site deploys as static files (Vercel or Netlify, straight from the repo). The BarentsWatch token stays on one laptop, and nothing can fall over during judging.
- **Back end:** Python with pandas, requests, statsmodels and linearmodels. Store data as Parquet in `data/`. Write the pipeline as scripts and use notebooks only for exploring.
- **Front end:** use whatever the two of you know best. The default is Vite + React + TypeScript, MapLibre GL + deck.gl for the map, and Observable Plot for charts. Don't learn a new framework tonight.
- **A single date column handles publication lags.** Give every row an `available_at` date and only use features where `available_at <= forecast_date`. The dates:
  - Lice for week w: end of week w + 1 (reports can arrive late).
  - Statistics Norway week w: the following Wednesday.
  - Directorate month m: the 20th of month m + 1.
  - EUR/NOK: the next day.
- **Weeks to months:** assign each ISO week to the month that contains its Thursday. 2020 and 2026 both have a week 53.
- **Nowcast baselines:**
  - **B0:** area × calendar-month season, plus log biomass and fish numbers at the end of the previous month.
  - **B1:** B0 plus the national export-volume anomaly for the target month.
  - **Bio:** B1 plus lice-index and temperature-band anomalies for the target month and the three months before.

### Data contract

| File | Shape | Producer | Due |
| --- | --- | --- | --- |
| `farms.json` | `[{id, name, lat, lon, area, capacity_t}]` | Data & Price | +2 h |
| `farm_weeks.json` | `{weeks, ids, mobile, treated, temp}`; each of `mobile`, `treated`, `temp` holds one array per week, aligned to `ids`, with `null` for no report | Data & Price | sample +2 h, full +4 h |
| `area_month.json` | `[{area, month, count, avg_kg, count_anom, weight_anom, lice_idx, temp_anom}]` | Supply | +4 h |
| `trap.json` | `{raw_r, anom_r, series: [{week, lice, price, lice_anom, price_anom}]}` | Supply | +6 h |
| `channels.json` | `{bins: [...], panel: [{outcome, driver, coef, lo, hi}]}` | Supply | bins +8 h, panel at freeze |
| `nowcast.json` | `{backtest: [{area, month, actual, b0, b1, bio}], scores, sealed: {target, commit, made_at, areas: [{area, count, avg_kg, lo, hi}]}}` | Supply | +8 h; sealed at freeze |
| `price.json` | `{history: [{week, price}], scorecard: [{h, model, mae_ratio, hit_rate}], cw, fan: [{week, p10, p50, p90}], sealed}` | Data & Price | at freeze |

Map notes: deck.gl handles a thousand or so farms easily, so just recolour the points each time the week changes. Ship data from 2019 onward rounded to two decimals, and split it by year if the file grows past about 10 MB. For the prediction view, a south-to-north strip of the 13 areas works without any boundary files.

## Scope

**Tier 1: on the live site by +8 h. The demo works with only this.**

- Farm map: lice per farm per week, a ring when a farm treats, a time slider with play, and two bookmarks: one warm period with heavy lice and one without, picked from the index.
- Trap chart: raw correlation next to the anomaly correlation.
- Count × weight, descriptive: average count and weight anomalies for each third of the lice-anomaly range, and the same for temperature.
- Supply nowcast: walk-forward 2021–2026 by area against B0 and B1, plus the sealed October prediction.

**Tier 2: by the analysis freeze.**

- H1/H2 panel with Driscoll–Kraay errors, shown as the two-channel chart in place of the descriptive bins.
- Price models a, b, c0 and c1 at 2–8 weeks ahead, the error relative to the random walk, Clark–West at 4 weeks, and the scorecard.
- Fan chart from past walk-forward error quantiles, and the sealed price forecast.

**Tier 3: only if you're ahead.** Lead–lag chart with the shuffled-year noise band; regional interactions; wild bootstrap; the slow young-farm channel; H4; the HLN–Diebold–Mariano and Pesaran–Timmermann tests and CRPS; average weight within stocking-year groups as a robustness check.

**Cut.** The Bayesian model (d); ARIMA errors; the 2012–2016 supply robustness checks (still pull 2012–2016 lice, because price training needs it); a separate side-by-side map (the bookmarks cover it); any slides beyond a title and a closing slide.

## Timeline

| Time | Data & Price | Supply | Map | Story |
| --- | --- | --- | --- | --- |
| 17:30–18:30 | Account, token, start the pull | Load Directorate and Statistics Norway data | Set up app; deploy empty site | Skeleton; mock files |
| 18:30–21:30 | Clean lice; farm-to-area; map exports | Anomalies; `area_month.json` | Farms on the map; slider | Count × weight chart on real data |
| 21:30–01:30 | Price a, b, c0, then c1 | Index, trap, count × weight bins, nowcast | Real lice, treatments, click, bookmarks | Trap and nowcast charts |
| 01:30–04:00 | Sleep | Panel; sealed October nowcast, committed before 04:00 | Prediction view | Sleep |
| 04:00–06:30 | Clark–West; fan; sealed price forecast | Sleep | Sleep | Two-channel chart, scorecard, fan chart |
| 06:30–08:00 | README; tidy repo | Check every number on the site | Polish; performance | Script; Devpost draft |
| 08:00–10:30 | All four: rehearse three times, record a backup video, practise Q&A, submit by 10:30 | | | |

| Check | Must be true | If not |
| --- | --- | --- |
| **+4 h (21:30)** | Lice data from 2017 with temperature and treatments; Directorate and Statistics Norway data loaded; real farms on the map | Use the BarentsWatch website CSV export, work at national level only, and limit the map to 2023–2025 |
| **+8 h (01:30)** | Tier 1 on the live site | Drop the nowcast to national level, and lead with the trap chart and the count × weight bins |
| **Analysis freeze (05:00)** | Pass or fail recorded against the committed pass marks; sealed predictions committed | Anything unfinished is cut, not rushed. If c1 doesn't beat c0, the price beat becomes "the market already prices public biology" |
| **Code freeze (08:00)** | Site deployed; backup video recorded | Demo from the video |

## Demo

Three minutes, plus a 60-second version for judges who come to your table.

| Time | On screen | Say |
| --- | --- | --- |
| 0:00 | Map playing autumn 2024 | "Every week, every salmon farm on Norway's coast counts the parasites on its fish. It's all public, and almost nobody looks at it." |
| 0:20 | Map | "Norway farms just over half the world's Atlantic salmon, and Scottish salmon, the UK's top food export, sells at prices set largely by Norwegian supply." |
| 0:40 | Trap chart | "Lice and prices look tightly linked, but that's just the seasons. Take out season and trend and most of the link disappears, so everything we do is on anomalies." |
| 1:05 | Two-channel chart | "Warm water does two things. Fish grow faster, so there are more, bigger fish. Lice multiply, so farmers harvest early, which means more, smaller fish. Split harvest into count × weight and you can see which one is happening." |
| 1:50 | Prediction strip and backtest | "Norway's official harvest figures come out on the 20th. We predict them by area, weeks earlier, from public farm reports. Since 2021 that has beaten [baseline] by [x]%. Here's October, committed to git at [time]: check us on 20 November." |
| 2:30 | Scorecard and fan chart | "On price, our four-week forecast [beats / doesn't beat] a random walk. [If not: the market already prices most of what public biology says.]" |
| 2:50 | Repo and QR code | "Lice are invisible. What they do to supply doesn't have to be." |

The 60-second version: map (15 s), two channels (20 s), sealed prediction (20 s), close.

**Questions to expect**

- *Isn't it just seasonality?* Point to the trap chart: everything is in anomalies, with month × year effects.
- *Don't export figures already tell you supply?* Nationally, mostly, which is why they're in our baseline. Our edge is by area, and in count versus weight.
- *Is it causal?* For supply, temperature is held fixed and month × year effects absorb national shocks. For price we claim forecasting skill, not cause.
- *Why not use futures?* There's no free price history for them, and we state that as a limitation.
- *How do we know you didn't p-hack?* The pass marks were committed at [time], before any results.
- *Who would use it?* Buyers and processors planning around fish size, Scottish farmers who take Norway's price, analysts, and regulators or welfare groups who want early warning.

## Pass marks: commit before looking at any results

```text
Pass marks: committed before any results were looked at.

Supply panel: production area × month, Oct 2017 – Sep 2026, 13 areas (the "(null)" row excluded).
Outcomes and drivers are anomalies: logs, minus a trailing 12-month level, Fourier seasonality,
and Easter and Christmas terms. Fixed effects: area × calendar month and month × year.
Errors: Driscoll–Kraay, bandwidth 12.
Lice pressure: capacity-weighted mobile lice per fish. Treatments per active farm-week enter the
same regression as the delousing channel (reported, no pass mark). Adult females: robustness only.

H1 (primary). Holding temperature-band anomalies and treatments fixed, the sum of mobile-lice
coefficients at lags 0–3 months is above zero for log fish harvested and below zero for log
average weight, each with a 95% interval that excludes zero.

H2. In the temperature-only model, the sum of coefficients on the degree-day anomaly below 14 °C
(bands below 8 °C and 8–14 °C combined) at lags 1–3 months is above zero for log average weight,
with a 95% interval that excludes zero.

H3 (secondary). Walk-forward 2019–2026 at 4 weeks ahead: c1 has at least 5% lower mean absolute
error than c0, and the Clark–West test (squared error, HAC with h − 1 lags) rejects at 5%,
one-sided. Horizons 2–8 are reported with a Holm correction.

H4 (exploratory). Tested only at 0–6 and 13–26 weeks; both one-sided tests must reject.

Supply lag windows are fixed above, not chosen from data. Price lag lengths are chosen on
2012–2018 data only.

Live test: sealed nowcast of October 2026 fish harvested and average weight by area, scored
against the Directorate's first release (around 20 Nov 2026); sealed price forecast for
week 48 of 2026, scored against Statistics Norway (around 2 Dec 2026).
```
