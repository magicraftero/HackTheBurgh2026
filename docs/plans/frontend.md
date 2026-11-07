# Role plan: Front end

For: the coding agent working with the front-end person. Read `docs/plans/00-shared.md` first, because it defines every file the back end produces, its schema and when it arrives. If this plan disagrees with it, 00-shared.md wins; tell your human.

## Your job

Build a properly hosted static website that shows the findings. **The team decides how the site looks once the back-end work is under way.** Don't invent a visual design or a story order. Build the design-independent foundation now, then build whatever design the team chooses.

## Fixed requirements

- **Static only.** No server, no API keys, and no secrets in the browser.
- **Deploys automatically** from the GitHub repo on every push to `main`.
- **Reads only these files:** `web/public/data/*.json`, `web/public/data/farm_weeks/*.json` and `web/public/charts/*.vl.json` (plus `web/public/data/_mock/` in development). Every number on the page comes from them; nothing is hard-coded.
- **Handles missing files.** Findings land throughout the night, so any file may be missing at any time. Show a clear "coming later" state, never a crash or a blank page.
- **Loads quickly** on hackathon Wi-Fi, reads well on a projector and on a laptop, and has keyboard-accessible controls.

## Careful: the back end writes into `web/public/`

Data creates `web/public/data/` and `web/public/charts/` in the first 15 minutes, and files keep arriving there all night.

- Never delete or overwrite anything in those two folders. Your only folder inside them is `web/public/data/_mock/`.
- Most project generators (for example `npm create vite`) offer to empty a folder that isn't empty. Don't accept. Instead, scaffold in a temporary folder and move the files into `web/`, keeping `web/public/data/` and `web/public/charts/` intact.

## The findings

Chart specs (`.vl.json`) are in `web/public/charts/`. Every other file is in `web/public/data/`. Due times are local.

| # | Finding | Files (due) | Owner |
| --- | --- | --- | --- |
| 1 | Farm-by-farm weekly picture | `farms.json`, `farm_weeks/index.json`, `farm_weeks/{year}.json` (21:30) | Data |
| 2 | The seasonality trap | `trap.json` (23:30), `trap.vl.json` (00:00) | Production; chart by Data |
| 3 | Count × weight split | `bins` in `channels.json` (01:30), `channels_bins.vl.json` (02:00) | Production; chart by Data |
| 4 | Production nowcast backtest (F1), with the September 2026 example | `nowcast.json` (01:30; holdout 04:00), `nowcast_backtest.vl.json` (02:00; holdout 05:00) | Production; chart by Data |
| 5 | Driver ranking | `drivers.json` (04:00), `drivers_importance.vl.json` (05:00) | Production; chart by Data |
| 6 | Mechanism tests M1 and M2 | `panel` in `channels.json` (04:00), `channels_panel.vl.json` (05:00) | Production; chart by Data |
| 7 | Price backtest (F2) | `price.json` (03:00; holdout 04:00), `price_scorecard.vl.json`, `price_by_year.vl.json`, `price_backtest.vl.json` (04:00) | Price |
| 8 | Optional: current forecasts | `current` in `nowcast.json` and in `price.json`, `price_fan.vl.json` (optional, no due time) | Production and Price |
| | Harvest and drivers by area and month (no number) | `area_month.json` (23:30) | Production |

## Phase 0: foundation (now to 21:30)

1. **Ask your human** which framework (default: Vite + React + TypeScript) and which host (Vercel, Netlify or GitHub Pages). Scaffold in `web/`, deploy an empty page, and give your human the URL by 18:30.
2. **Typed data layer:** a TypeScript type and a loader for every file in the table, following 00-shared.md. A missing file or a schema mismatch returns a typed "not available yet" result.
   - Fetch at run time from the site's base path, not `/` (GitHub Pages serves the site under `/HackTheBurgh2026/`). Never import the files at build time, or a missing file breaks the build.
   - Until the 04:00 freeze, `f1`, `latest` and `scores.holdout` in `nowcast.json`, and `f2` and `backtest_h4` in `price.json`, are `null`, and no row has `"window": "holdout"`. `channels.json` can also lack `panel`. Each of these means "coming later" for that part only.
   - `current` is `null` by default, and 00-shared.md doesn't define its shape yet. `disease` in the year files is optional. Any number can be `null`, and so can a `panel` row's `pass`.
3. **Mock data:** small, schema-correct copies of every file in the table in `web/public/data/_mock/` (chart specs in `_mock/charts/`), plus a development-only switch to use them. Mock both the before-freeze and after-freeze shapes that 00-shared.md shows. Never show mocks as real findings in production.
4. **Chart embed:** one component that renders any `.vl.json` spec with `vega-embed` (plus the `vega` and `vega-lite` packages), at a responsive width with `actions: false`.
5. **Scaffold page:** every row of the table under its plain title. Each one shows its charts or data, or the "coming later" state. This page exists to test the data flow; it isn't the final design.

## Phase 1: the team's design (after your human tells you)

Build the design the team picks on top of the Phase 0 layer. Notes for that decision:

- **Finding 1** (lice, treatments, disease and sea temperature by farm and week) is the only one that needs custom rendering.
  - If the team wants a map, MapLibre GL with deck.gl handles about a thousand points per week. Recolour the points when the week changes, and load the year files only when needed.
  - From the planning session: lice pressure (`mobile`) and treatments (`treated`) tell the story better than counts against the legal limit, because farmers keep counts under that limit.
- **Findings 2–7** arrive as finished Vega-Lite charts, so the site only places them. Their styling lives in Price's `charts/theme.py`, so chart colour or font changes go through your human.
- **The design must make room for these.** They land at the 04:00 freeze (charts by 05:00), so use mocks until then.
  - The driver ranking (finding 5).
  - The holdout results: F1 (`nowcast.json` → `f1`) and F2 (`price.json` → `f2`). They are `null` before the freeze, and development-window results never stand in for them.
  - The September 2026 worked example (`nowcast.json` → `latest`): the nowcast against the Directorate's published figure, nationally and by area.
  - The `price_backtest.vl.json` chart: actual prices against the 4-week-ahead forecasts over the holdout.

  How they look is the team's call.
- **Finding 8** is optional, and `current` stays `null` unless the back end has time. If it's filled in, it must be labelled as unverifiable, because it can't be checked before judging.

## Timeline

| By | What |
| --- | --- |
| 18:30 | Empty site hosted and the URL shared |
| 21:30 | Phase 0 done, running on mocks |
| About 02:00 | Real findings 1–4 showing, on the development window. Your human sleeps 01:30 to 04:00, so new files must appear on their own |
| About 05:00 | Findings 5–7, the holdout results and the September 2026 example showing |
| 07:00 | The team's design built |
| 08:00 | Code freeze: the hosted site shows every finding that exists, including the September 2026 example |

## Ask your human when

- any design decision comes up: layout, colours, story order, map or no map;
- a contract file doesn't match its schema. The back end owns the contract, so report it rather than adapting silently;
- `current` stops being `null`, because 00-shared.md doesn't define its shape yet;
- a file is still missing after the 04:00 analysis freeze, when unfinished work is cut;
- deployment fails.
