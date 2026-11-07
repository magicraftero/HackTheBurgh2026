# Data tables

Built by the Data role (`pipeline/`). Schemas follow `docs/plans/00-shared.md`; this page says what's in each file and what to watch out for. Every check is in `python -m pipeline.checks` (all pass as of 7 Nov 2026).

```python
import pandas as pd
df = pd.read_parquet("data/processed/farm_week.parquet")
```

A forecast made on date D may only use rows with `available_at <= D`.

## `data/processed/`

| File | Rows | Grain and coverage | Source |
| --- | --- | --- | --- |
| `directorate_area_month.parquet` | 1,512 | area 0–13 × month, 2017-10 to 2026-09, salmon only, summed over stocking year | Directorate of Fisheries |
| `ssb_weekly.parquet` | 1,400 | ISO week, 2000-W01 to 2026-W44, fresh/chilled salmon export price and tonnes | Statistics Norway 03024 |
| `fx_daily.parquet` | 3,757 | business day, 2011-12-01 to 2026-11-06, EUR/NOK and USD/NOK | Norges Bank |
| `farms.parquet` | 1,475 | one row per marine salmonid site with an area 1–13 | Aquaculture register + BarentsWatch |
| `farm_week.parquet` | 830,284 | site × ISO week, 2012-W01 to 2026-W45 | BarentsWatch lice, treatments, disease |
| `release_log.parquet` | | one row per download: periods covered, publication date, download time, file hash | — |

### `farm_week` columns

- `reported`: the site counted lice that week. When it's false, `adult_female`, `mobile` and `stationary` are null, never 0.
- `fallow`: BarentsWatch's estimate that the site is likely without fish.
- `treated`: any delousing treatment (medicinal or not) that week; `treat_types` lists them.
- `sea_temp_c`: cleaned. Null below −2 °C, above 25 °C, or more than 6 °C from the site's trailing 8-week median.
- `isa`, `pd`: a suspected or confirmed ISA (ILA) / PD case that week.
- `lice_limit`, `above_limit`: the week's published adult-female threshold (0.5, or 0.2 in spring) and BarentsWatch's flag for being above it. **Not in the contract yet**; added from the dashboard plan.
- Bool columns are pandas nullable `boolean`, so missing stays missing.

## `web/public/data/` (for the front end)

- `farms.json`: `[{id, name, lat, lon, area, capacity_t}]`, the same sites as `farms.parquet`.
- `farm_weeks/index.json` and `farm_weeks/{2019..2026}.json`: `mobile`, `treated`, `temp` and `disease` grids, `[week][site]`, in the contract's shape. Weeks appear once their Tuesday reporting deadline has passed (2026 runs to W44).

## Things to know

- **The latest week is incomplete.** 2026-W45 has only 72 of about 600 reports, because reports are due Tuesday 10 Nov. Its `available_at` (15 Nov) keeps it out of models.
- **Treatments, 2024-W46 format change.** The number of rows per week rose, but the farms treating per week (the `treat_rate` measure) is comparable: 49 vs 68 in W46–W09 one year apart. Before 2024 most non-medicinal treatments have no type, so `treat_types` says `ikke-medikamentell`.
- **Disease records are sparse before 2014.** About 3 active cases a week in 2012, 47 in 2013 and about 150 from 2014, so early years understate disease.
- **No 2026-W53 yet.** That week starts 28 Dec 2026.
- **Area 0** in the Directorate table is the suppressed `(null)` row (1–5% of harvest). Include it in national totals, and leave it out of anything done by area.
- **Revised data.** Every table is today's revised version. A historical backtest built from them is a reconstruction, not a record of real-time data.

## Rebuilding

```bash
python -m pipeline.fetch_directorate && python -m pipeline.fetch_ssb && python -m pipeline.fetch_norgesbank
python -m pipeline.fetch_barentswatch        # needs BW_CLIENT_ID / BW_CLIENT_SECRET in .env (Data laptop only)
python -m pipeline.fetch_register && python -m pipeline.build_farm_week && python -m pipeline.export_site_data
python -m pipeline.checks
```

Add `--offline` to the `fetch_*` loaders to rebuild from the last download without fetching again.
