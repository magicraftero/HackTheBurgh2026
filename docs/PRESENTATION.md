# Presentation notes

A shared scratchpad for the pitch. Add ideas anywhere; keep each line short. Numbers come from
`analysis/RESULTS.md`, `ml/RESULTS.md` and `price/RESULTS.md`; check there before quoting.

## The story in 3 minutes

1. **Hook (20 s).** "Norway tells the world how much salmon it harvested about seven weeks after
   the month starts. We can read it six weeks before that, from data anyone can download."
2. **What's invisible (40 s).** Under the water: lice, deaths, sea temperature, fish growth. All
   public, almost nobody connects them to supply. Show Jesse's farm map: every farm, every week.
3. **The hidden patterns (60 s).** Pick two or three from the list below. Lead with
   "six weeks early" and "lice make fish smaller".
4. **The prediction (40 s).** October 2026: about 198,300 tonnes, before the official figure
   (due around 20 November). About 80% accurate per area on data the model never saw.
5. **Make it personal (20 s).** The cockpit: set up your own farm, start a lice outbreak, watch
   your fish get smaller and your harvest come early.
6. **Honesty close (10 s).** "We set our pass marks before looking. Some failed. Here's what held up."

## Hidden patterns, with the surprising line

| Pattern | The line to say |
|---|---|
| Exports reveal the harvest early | "Weekly export figures give away Norway's monthly harvest to within about 10%, six weeks before it's published." |
| Lice force early harvests | "After bad lice months, farms pull out 8% more fish, and they're smaller. That passed the test we wrote before seeing the data." |
| The seasonality trap | "Disease and harvest look strongly linked (r = -0.67). Take out the seasons and most of it vanishes (r = -0.28). Raw charts lie by more than double." |
| Deaths come before emergency harvests | "When deaths spike, harvests jump about 8%, at smaller sizes: farmers pull fish before they lose them." |
| Cold seas slow everything | "A cold spell means about 6% fewer fish harvested one to three months later." |
| Heavy stock means a harvest wave | "When an area's fish are unusually heavy, next month's harvest is about 6-7% bigger. Book your boats." |

## Numbers cheat sheet

- Combined model (exports + area shares for tonnes, Nikita's ML for fish size): **about 80% accurate**
  on tonnes and fish count per area, **about 93%** on fish size.
- **17% less error** than the seasonal baseline on tonnes (0.199 vs 0.241 log points).
- Tested on **231 area-months** (January 2025 to September 2026) the model never trained on.
- October 2026 forecast: **about 198,300 tonnes** across areas 2-12.
- National total from exports: within about **10%** (8% on the holdout).

## The pre-registered tests, said simply

- **F1:** "Does fish-health data make the forecast at least 5% better?" We got 3.2%: real but
  short of the bar. Then the export insight got 17%.
- **M1:** "Do lice make farmers harvest more, smaller fish?" Smaller: yes, proven. More: not proven.
- **M2:** "Does warmer water make fish heavier later?" Not proven.
- **Why it's a strength:** we wrote the bar down before looking. Most teams decide what success
  means afterwards.

## Demo script

1. Open Jesse's site and its farm map. Scrub through a year: watch lice glow along the coast.
2. Findings page: the seasonality trap chart, then the forecast against the actual figures.
3. Cockpit (`cockpit/`): pick area 3, press "Lice outbreak". Point at:
   - the fish in the pen gaining lice dots;
   - the harvest going up and the size per fish going down;
   - the waterfall showing the step for each pattern.
4. Press "Load my area's real conditions": "this is what the data says about right now".

## Likely judge questions

- **"Isn't export volume cheating?"** No. It's published about 9 days after each week, before
  the official harvest figure. We only use what was public on each forecast date.
- **"Did you overfit?"** The holdout was locked during development. The combined model was chosen
  on 2021-2024 data before its holdout scores were read. The team opened the holdout early, at
  23:47, and we say so.
- **"Why not just use machine learning?"** We did (gradient-boosted trees). It helps with fish size.
  The big win came from understanding when data is published, not from a bigger model.
- **"Can a farmer act on this?"** The cockpit shows what similar months led to. These are patterns,
  not advice, and we say that on the page.

## Ideas backlog

- QR code on the closing slide that opens the cockpit on a phone.
- A live counter: "official October figure published in N days: check our forecast".
- Before and after the seasonality trap, shown as one animated chart.
- "Spot the lice outbreak" quiz: show a year strip and ask the audience which month it hit.
