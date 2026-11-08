# Presentation notes

A shared scratchpad for the pitch. Add ideas anywhere; keep each line short. Production numbers
come from `analysis/RESULTS.md` and `ml/RESULTS.md`. Pricing numbers to present come from
`web/public/data/price_sisalmoni_v2.json`; see [the display handoff](PRICE_DISPLAY_HANDOFF.md).

## Current price result to present: SISALMONI v2

- Target: **SISALMONI 3–6 kg index, EUR/kg**. Display model: **price-only Ridge v2**.
- Four-week result on **24 target weeks, 2026-W21 to 2026-W44**: **33.6% less MAE
  than no change**, **4.7% less than the original biology model on those same dates**,
  and **EUR 0.292/kg MAE**.
- **79.2% correct direction** means 19 of 24 rise/fall calls, not overall price accuracy.
- Say **"promising retrospective result"**. Paired uncertainty intervals include no benefit;
  the full 10% objective against the strongest baseline was not met. No change remains
  the recorded live recommendation.
- The older SSB/NOK percentages, the first SISALMONI OLS error of EUR 5.392/kg, and the
  unselected alpha-100 variant are different comparisons, not this headline result.

## The one-line pitch

"Everyone watching Norway's salmon watches the lice. We tested every public factor, and the
biology doesn't decide **how much** salmon comes out next month. It decides **what size**. Stock
and trade decide how much, and with them we forecast each region's harvest before the official
figures, with an open track record."

## Don't say

- "We discovered that lice cause early harvests." It's known research. Say we **measured** it
  for whole regions from public data, and that it shows up in fish **size**, not tonnage.
- "Six weeks early." Wrong. We forecast on the 10th; the official figure comes on the 20th. Say
  "about 10 days before the official figures".
- "90% accurate" for everything. Tonnes and fish count are about 80%; fish size is about 93%.

## The story in 3 minutes

1. **Hook (20 s).** "Norway farms half the world's salmon and publishes almost everything about
   it: every farm, every week. Lice, deaths, sea temperature. Which of it actually predicts supply?"
2. **Make it visible (40 s).** Jesse's farm map: scrub through a year and watch lice glow along
   the coast. "This is the data everyone talks about."
3. **The surprise (60 s).** The factor ranking (below). Take out stock and the forecast gets 14%
   worse. Take out lice, temperature or feed: almost nothing changes for tonnes. But for fish
   **size**, deaths, disease and lice are the top drivers. "Biology changes what size comes
   out, not how much."
4. **The prediction (40 s).** "October 2026: about 198,300 tonnes across 11 regions, 10 days
   before the official figure. Tested on 21 months it never saw: about 80% accurate per region,
   17% better than the seasonal baseline. The trick wasn't a bigger model. It was using export
   data the right way."
5. **Make it personal (20 s).** The cockpit: set up a farm, start a lice outbreak, watch the fish
   get smaller and come out earlier.
6. **Honesty close (10 s).** "We wrote our pass marks before looking. Our first model missed its
   bar: 3.2% against 5%. That's what sent us looking for what really matters."

## What we found, ranked by how new it is

| Finding | New? | The line to say |
|---|---|---|
| Stock decides tonnage, biology decides size | **Ours** | "Remove stock and the forecast gets 14% worse. Remove lice: about 0% for tonnes, 2% for fish size. Deaths and disease: 4% for size." |
| Structure beats more data | **Ours** | "The same export number used as one input among many: 1.6% better. Used as a ratio to harvest and split by region: 17% better." |
| The seasonality trap | **Ours** (method) | "Disease and harvest look strongly linked (r = -0.67). Take out the seasons and most of it vanishes (r = -0.28). Raw charts overstate it by more than double." |
| Lice mean smaller fish | Known, now measured | "After bad lice months, regions harvest 8% more fish at 1.3% smaller size. That passed a test we wrote before seeing the data." |
| Deaths come before emergency harvests | Known, now measured | "When deaths spike, harvests jump 8% at smaller sizes." |
| Cold seas slow growth | Known, now measured | "A cold spell means about 6% fewer fish harvested 1-3 months later." |

## Numbers cheat sheet

- Combined model (exports + regional shares for tonnes, Nikita's machine learning for fish size):
  **about 80% accurate** on tonnes and fish count per region, **about 93%** on fish size.
- **17% less error** than the seasonal baseline on tonnes (0.199 vs 0.241 log points).
- Tested on **231 region-months** (January 2025 to September 2026) the model never trained on.
- October 2026: **about 198,300 tonnes** across regions 2-12; official figure due around 20 Nov.
- National total from exports: within about **10%** (8% on the holdout).
- Factor ranking for tonnes: stock 14%, exports 1.6%, smolt pipeline 1.2%, deaths and disease
  0.2%, lice about 0%, temperature about 0%. For fish size: deaths and disease 4.0%, stock 2.4%,
  lice 1.9%, feed 1.0%.

## The pre-registered tests, said simply

- **F1:** "Does fish-health data make the forecast at least 5% better?" 3.2%: real but short of
  the bar. That result is the surprise above: biology isn't what moves tonnage.
- **M1:** "Do lice make farmers harvest more, smaller fish?" Smaller: yes, proven. More: not proven.
- **M2:** "Does warmer water make fish heavier later?" Not proven.
- **Why it's a strength:** we wrote the bar down before looking. Most teams decide what success
  means afterwards.

## Demo script

1. Jesse's site, farm map: scrub through a year.
2. Findings: the seasonality trap chart, then the factor ranking, then the forecast against actuals.
3. Cockpit (`cockpit/`): pick area 3, press "Lice outbreak". Point at:
   - the lice dots on the fish;
   - the harvest going up while the size per fish goes down;
   - the waterfall step for each factor.
4. Press "Load my area's real conditions": "this is what the data says right now".

## Likely judge questions

- **"Isn't lice and early harvest already known?"** Yes, from farm studies. We measured it for
  whole regions from public data, and found it shows up in fish size far more than in tonnage.
  That's why lice data alone won't forecast supply.
- **"Isn't export volume cheating?"** No. It's published 9 days after each week starts, before
  the official harvest figure. We only use what was public on each forecast date.
- **"Did you overfit?"** The holdout was locked during development. The combined model was chosen
  on 2021-2024 data before its holdout scores were read. The team opened the holdout early, at
  23:47, and we say so.
- **"Why not just use machine learning?"** We did (gradient-boosted trees). It wins on fish size,
  where biology matters. The big win on tonnes came from using export data the right way.
- **"Who would use this?"** Processors, well-boat operators and buyers planning by region, and
  anyone who doesn't pay for a private forecast. Paid forecasters don't publish a track record.
- **"Can a farmer act on this?"** The cockpit shows what similar months led to. These are
  patterns, not advice, and we say that on the page.

## Ideas backlog

- QR code on the closing slide that opens the cockpit on a phone.
- A countdown: "official October figure in N days: check our forecast".
- One animated chart: the seasonality trap before and after removing the seasons.
- The factor ranking as two bar charts side by side, tonnes and fish size.
