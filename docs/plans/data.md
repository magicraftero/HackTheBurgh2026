# Role plan: Data (back end)

For: the coding agent working with the Data person. Read `docs/plans/00-shared.md` first, because it defines every path, schema, driver and deadline used here.

## Your job

Get every dataset in, cleaned and stamped with its publication date, and feed the other three roles on time. Your tables feed every driver in the contract. Stock, the smolt pipeline, feed and deaths come from the Directorate file. Lice, treatments, sea temperature and disease come from BarentsWatch. The market comes from Statistics Norway and Norges Bank. After that, build the production charts and write the README. Follow the contract's holdout rule: you never run or look at holdout scores before the 04:00 freeze. Three people are waiting on your first outputs, so until 21:30 speed matters more than polish.

## Sources (use only these)

| Source | Address | Notes |
| --- | --- | --- |
| Directorate of Fisheries, biomass statistics by production area | `https://register.fiskeridir.no/biomassestatistikk/BIOSTAT-LAKS-OMR/biostat-total-omr.csv` | No login. Checked on 7 Nov: it works and covers Oct 2017 to Sep 2026. It also holds feed and deaths |
| Statistics Norway table 03024 (PxWebApi v2) | Metadata: `https://data.ssb.no/api/pxwebapi/v2/tables/03024/metadata?lang=en` | Checked on 7 Nov: it works and runs to 2026-W44. Build the data query from it (task 2) |
| Norges Bank EUR/NOK and USD/NOK | `https://data.norges-bank.no/api/data/EXR/B.EUR.NOK.SP?format=csv` and `https://data.norges-bank.no/api/data/EXR/B.USD.NOK.SP?format=csv` | Same API. Add `&startPeriod=2011-12-01` to both |
| Directorate aquaculture register | `https://api.fiskeridir.no/pub-aqua/api/v1/dump/new-legacy-csv-file` | One row per licence × site |
| BarentsWatch Fish Health API | Docs: `https://developer.barentswatch.no/docs/fishhealth/`; tutorial: `https://developer.barentswatch.no/docs/tutorial` | Needs your human's account and API client. Lice, treatments, sea temperature, fallow status and, if present, ISA and PD flags |

## Tasks, in order

### 1. Repo basics (first 15 minutes)

- `requirements.txt`: `pandas>=2.2`, `numpy`, `pyarrow`, `requests`, `python-dotenv`, `scipy`, `statsmodels>=0.14`, `linearmodels>=6.0`, `altair>=5.3`.
- `.gitignore`: `.venv/`, `.env`, `data/raw/`, `__pycache__/`, `web/node_modules/`, `web/dist/`, `.DS_Store`.
- `.env.example`, containing `BW_CLIENT_ID=` and `BW_CLIENT_SECRET=`.
- `pipeline/__init__.py` and `charts/__init__.py`, plus `.gitkeep` files in `data/processed/`, `web/public/data/` and `web/public/charts/`.
- Check that `prereg/PASS_MARKS.md` is on GitHub. If it isn't, tell your human straight away.
- Meanwhile your human creates the BarentsWatch account and API client (see the tutorial) and puts the client ID and secret in `.env`.
- **Done when:** this is pushed and `pip install -r requirements.txt` works in a fresh virtualenv.

### 2. Quick loaders (push by 18:30, because Production and Price are waiting)

In every table you write, store the date columns (`date`, `week_start`, `available_at`) as pandas `datetime64[ns]` at midnight, so the others can compare them with `pd.Timestamp`.

**`pipeline/fetch_directorate.py` → `directorate_area_month.parquet`**
- Download to `data/raw/directorate/` and read with `sep=";"` and `encoding="utf-8-sig"` (the file starts with a byte-order mark). Print the header and confirm the column names below.
- Keep `ARTSID == "LAKS"`. The file also includes rainbow trout (`REGNBUEØRRET`).
- Treat `PO_KODE == "(null)"` as area 0, and convert other areas to int.
- Sum every numeric column over `UTSETTSÅR` (stocking year) for each area, `ÅR` and `MÅNED_KODE`.
- Column mapping:
  - `UTTAK_STK` → `harvest_count`
  - `UTTAK_KG` → `harvest_kg` (already in round-weight equivalent: gutted × 1.125 plus round weight)
  - `BIOMASSE_KG` → `biomass_kg`
  - `BEHFISK_STK` → `fish_stock`
  - `UTSETT_SMOLT_STK` → `smolt_released`
  - `DØDFISK_STK` → `dead`
  - `FORFORBRUK_KG` → `feed_kg`
- `avg_kg` = `harvest_kg / harvest_count`, null when `harvest_count` is 0.
- `month` = `f"{ÅR}-{MÅNED_KODE:02d}"`; `available_at` = the 20th of the next month.
- **Check `feed_kg` and `dead`.** Production turns them into the `feed_rate` and `mortality` drivers, so errors here spread into the nowcast and the driver ranking.
  - No negative values. Also print any area-month where `biomass_kg` is above 0 but `feed_kg` is 0.
  - No unit jumps between years. For each year, print the median over its months of national `feed_kg / biomass_kg` and national `1000 × dead / fish_stock`, where national means the sum over areas 0–13. Each year's median should be within a factor of 2 of the year before. A jump of about 1,000× means tonnes and kilograms are mixed.
  - If a check fails, push the table anyway and tell your human which years and areas are affected. Rescale only if they agree.
- **Done when:** areas 0–13 appear in every month from 2017-10, the `feed_kg` and `dead` checks pass, and national September 2026 is close to 41.9 m fish, 194,000 t and 4.62 kg average, as seen on 7 Nov (revisions can shift these slightly).

**`pipeline/fetch_ssb.py` → `ssb_weekly.parquet`**
- Read the metadata, then request `VareGrupper2 = 01` (fresh or chilled farmed salmon), `ContentsCode` `Vekt` (tonnes) and `Kilopris` (NOK/kg), and every `Tid` value. The v2 data endpoint looks like `https://data.ssb.no/api/pxwebapi/v2/tables/03024/data?lang=en&valueCodes[VareGrupper2]=01&valueCodes[ContentsCode]=Vekt,Kilopris&valueCodes[Tid]=*` plus an output format. If it errors, check the PxWebApi v2 documentation. The limit is 30 requests a minute, and one request should be enough.
- `Kilopris` → `price_nok_kg` and `Vekt` → `volume_t`.
- `Tid` codes look like `2026U44`, which becomes week `2026-W44`. `week_start` = `date.fromisocalendar(y, w, 1)`, and `available_at` = the Wednesday of the next ISO week.
- **Done when:** weeks run from 2000-W01 to 2026-W44 with no gaps, including week 53 in 2004, 2009, 2015, 2020 and 2026.

**`pipeline/fetch_norgesbank.py` → `fx_daily.parquet`**
- Fetch both series from 2011-12-01: `B.EUR.NOK.SP` becomes `eurnok` and `B.USD.NOK.SP` becomes `usdnok`. Take the `TIME_PERIOD` and `OBS_VALUE` columns. Print the first lines before parsing, because the separator may be `;` and the decimal mark may be a comma.
- Outer-join the two series on `date`. Keep only the business days Norges Bank publishes; don't fill weekends or holidays.
- `available_at` = `date` + 1 day.
- **Done when:** the columns are exactly `date`, `eurnok`, `usdnok` and `available_at`, both series run from December 2011 to the latest business day, and every value is between 5 and 14.

Push all three tables and tell your human they're up.

### 3. BarentsWatch: token and one test call (as soon as `.env` exists)

- **Token:** a client-credentials POST to `https://id.barentswatch.no/connect/token` with `grant_type=client_credentials`, `scope=api`, and the client ID and secret from `.env`. Confirm the details against the tutorial. The token lasts about an hour, so cache it, and on any HTTP 401 fetch a new one and retry once.
- **Test call:** the API base is `https://www.barentswatch.no/bwapi`. Request all farms for one recent week; the team's spec lists this as `POST /v2/geodata/fishhealth/locality/{year}/{week}`, so confirm it in the docs.
- Print one record and tell your human which of these fields exist:
  - locality number, name, coordinates and production area (if present);
  - adult female, mobile and stationary lice per fish;
  - treatments;
  - sea temperature (it moved under `liceReport` in v2);
  - fallow status;
  - disease flags for ISA (`ILA` in Norwegian) and PD, for example `hasIla` or `hasPd`. Use the site's own status, not whether it lies in an ILA or PD control zone. If the record has none, look in the docs for a separate ILA or PD endpoint, or a disease report type in the bulk download.
- **Say clearly whether sea temperature and the disease flags are there.** These are the team's two open questions, and Production needs the disease answer for `disease_share`. With no disease flags, the disease driver is dropped: `isa` and `pd` stay null and the year files get no `disease` array.
- If the API separates suspected from confirmed cases, count both as flagged, and tell your human you did.

### 4. BarentsWatch bulk pull (start right after the test call; it's the longest job)

- Use the bulk lice download. It's still v1 and allows at most 1 year + 1 week per call; find it in the docs. Pull single-threaded, as BarentsWatch asks.
- Pull 2026 back to 2017 first (the core window), then 2016 back to 2012 (Price and Production both need those years).
- Save every response under `data/raw/barentswatch/` and skip chunks that are already on disk, so a crash loses nothing.
- If the bulk download lacks sea temperature or treatments, pull 2017 onward from the weekly all-farms endpoint instead, one call per week, single-threaded.
- If it lacks only the disease flags, and task 3 found them elsewhere, fetch them after the lice for the same years, also single-threaded. They must not hold up the 21:30 table.
- If nothing works by 21:00, tell your human. The fallback is the BarentsWatch website's CSV export, downloaded by hand, with analysis at national level only.

### 5. Register → `farms.parquet` (while the pull runs)

- `pipeline/fetch_register.py`: download the register and print its columns. Keep one row per site (locality number) for marine salmon and trout sites, with name, latitude, longitude, production area and site capacity in tonnes. The file has one row per licence × site, so deduplicate.
- Sites that closed before today may be missing. Add any site that appears in BarentsWatch but not in the register: take coordinates from BarentsWatch, the area from BarentsWatch if it has one (otherwise from the nearest register site), and leave capacity null.
- Write only the contract's columns. This table has no `available_at`.

### 6. Build `farm_week.parquet` (2017 onward by 21:30)

- One row per locality × ISO week, with the columns in the contract. Store the bool columns as pandas' nullable `"boolean"` dtype, so nulls survive in Parquet.
- `reported` = the farm submitted lice counts that week. Weeks with no report stay missing and are never set to zero.
- `treated` = any delousing treatment was reported that week. Keep the raw types in `treat_types`. The lice-report format changed in November 2024, so compare the treatment fields before and after 2024-W46 and tell your human about any break.
- `sea_temp_c`: set it to null when it's below −2 °C or above 25 °C, or more than 6 °C away from the farm's own rolling 8-week median. Expect gaps: about 281 sites never report temperature, and a published audit found about 7,800 bad values.
- `isa` and `pd`: true if BarentsWatch flags the site with that disease in that week, false if not, and null for weeks the disease data doesn't cover. If the data comes as cases with start and end dates, flag every week from start to end, or to today if the case is still open. With no disease flags at all, both are null in every row. If the flags need the extra pull from task 4, push with them null first and fill them in with task 8.
- `available_at` = the Sunday that ends week w + 1.
- Print a summary: rows per year, share of farms reporting, share with temperature, share flagged with ISA or PD, and areas covered.
- **Done when:** 2017-W01 onward is pushed, every row has an area from 1 to 13, and you've posted the summary to your human.

### 7. Site exports (finding 1, by 21:30)

- `pipeline/export_site_data.py` writes `web/public/data/farms.json`, `web/public/data/farm_weeks/index.json`, and one `farm_weeks/{year}.json` for each year from 2019 to 2026, following the contract.
- In each year file, `ids` is every locality that reported at least once that year. Align every array to it: `mobile` from `mobile`, `treated` as 0 or 1, and `temp` from `sea_temp_c`, with `null` where there's no value.
- `disease` is 1 if `isa` or `pd` is true, 0 if both are false, and `null` otherwise. Write it in every year file if the flags exist, and leave the key out of all of them if they don't.
- Round as the contract's "Site JSON" rule says, but never round `id`, `ids`, `area` or `year`.
- **Done when:** each year file is under about 3 MB and loads in a browser, and every id in the year files is in `farms.json`.

### 8. Farm data for 2012–2016 (by 23:30)

Append these years to `farm_week.parquet`, push, and tell your human so Price and Production can rerun. Production needs them for temperature normals, and Price for training. Fill `isa` and `pd` for whatever years the disease data covers, including any fill left over from task 6, then rerun `python -m pipeline.export_site_data`.

### 9. Production charts (from 21:30; make each within 30 minutes of its JSON landing)

`charts/production_charts.py`, run as `python -m charts.production_charts`, reads `trap.json`, `channels.json`, `nowcast.json` and `drivers.json` from `web/public/data/` and writes the five Data specs in the contract's chart table. It skips any chart whose input isn't there yet (for example the panel chart before `channels.json` has `panel`) and prints what it skipped, so rerun it whenever a file lands. Until then, test it on the contract's example JSON, kept outside `web/public/`, and never push a chart built from example data. It uses `charts/theme.py` (from Price by 21:30; use Altair's default until then).

- **`trap.vl.json`** (finding 2, due 00:00):
  - top: one row per entry in `drivers`, labelled with `label`, showing `raw_r` and `anom_r` as two points joined by a line, on an x axis from −1 to 1 with a rule at 0;
  - below: two panels for the `highlight` driver's `series` against `week` (plotted at its Monday): `driver` with `price`, then `driver_anom` with `price_anom`. Standardise each line (subtract its mean, divide by its standard deviation) so each pair shares one axis, and say so in the axis title. Put that driver's `raw_r` and `anom_r` in the two panel titles.
- **`channels_bins.vl.json`** (finding 3, due 02:00): one panel per bin driver, in the order `lice`, `temp`, `feed`, `mortality`, titled "Mobile lice", "Sea temperature", "Feed per kg of biomass" and "Deaths per 1,000 fish", plus that driver's `window`. Each has `tercile` (1 to 3) on x, bars for `count_anom` and `weight_anom` side by side, and `n` in the tooltip.
- **`nowcast_backtest.vl.json`** (finding 4): the development-window version by 02:00, then regenerate it with the holdout at 05:00, after the freeze. Before the freeze, `scores.holdout`, `f1` and `latest` are null and `backtest` has no holdout rows, so the chart shows the development window only. Never compute holdout scores yourself.
  - top: MAE by model (`b0`, `b1`, `drivers`, shown as B0, B1 and Drivers) for each outcome, `log_kg` (volume), `log_count` (fish count) and `log_avg_kg` (average weight), side by side for each window in `scores` that isn't null (`dev`, `holdout`). Take window dates from `windows`, and put `scores.actuals` in the subtitle. After the freeze, put F1 from `f1` in the title: `improvement_pct`, `cw_p`, and pass or fail, judged on the holdout;
  - below: national actual against the Drivers nowcast by month, in three small panels for volume, count and average weight. Sum `actual` and `pred.drivers` over `backtest` rows with `area` 1–13; average weight is summed kg ÷ summed count. Label it "areas 1–13", because area 0 isn't forecast. Shade the holdout months from `windows.holdout`, and call out September 2026 from `latest` (its `national` `pred_kg`, `actual_kg` and `error_pct`) once `latest` isn't null.
- **`drivers_importance.vl.json`** (finding 5, due 05:00): horizontal bars of `increase_pct` by group `label`, largest first, with a rule at 0. Show negative values as they are. Add a smaller panel each for `log_count` and `log_avg_kg` from `by_outcome`, taking labels from `groups` by matching `group`. In the subtitle, give `outcome`, `window` and `full_mae`, and say the ranking is exploratory, with no pass mark.
- **`channels_panel.vl.json`** (finding 6, due 05:00): one row per `panel` entry, labelled with its `driver`, `outcome` and `lags` and grouped by `test` (M1, M2). Show `coef_sum` as a point and `lo` to `hi` as a line, with a rule at 0, and a text column reading "pass", "fail" or, when `pass` is null, "no pass mark".

The contract's 01:30 check also counts the bins and nowcast charts, so run the script the moment their JSON lands. Keep all styling in the theme, not in chart code, and never hard-code numbers: everything comes from the JSON. Take colours from the theme; if it has none for something you need, use its default colours and tell your human, so Price can add one. If the theme sets `width="container"`, note that Vega-Lite ignores it in concat and facet charts, so give each panel a fixed `width`.

**Done when:** each spec is pushed by its due time and your human has seen it render, in the Vega editor or on the site.

### 10. After the 04:00 freeze

- **Regenerate the charts** with `python -m charts.production_charts` once Production pushes the `--final` results, so `nowcast_backtest.vl.json` has the holdout by 05:00.
- **Write `README.md`** before the 08:00 code freeze, covering:
  - what the project is, based on "The project" in the contract;
  - how to reproduce it, as the exact commands in order, including the `--final` runs at the freeze;
  - the data sources, with links;
  - the holdout rule and both windows, from `windows` in `nowcast.json` and `price.json`;
  - pass or fail for each test, copied from the JSON with the numbers beside it, or "not recorded" if it's missing:
    - F1 (primary), judged on the holdout: `nowcast.json` → `f1`, with the development-window MAEs from `scores.dev` beside it;
    - F2, judged on the holdout: `price.json` → `f2`, with the development-window rows of `scorecard` and `cw` beside it;
    - M1 and M2: the `channels.json` → `panel` rows for that `test`, with `coef_sum`, `lo` and `hi`. A test passes only if every one of its rows with a non-null `pass` is true;
  - the driver ranking from `drivers.json`, largest `increase_pct` first, marked as exploratory with no pass mark;
  - the September 2026 worked example from `nowcast.json` → `latest`: the nowcast as made on `made_on` against the Directorate's published figure, nationally and by area. Say that the backtest is scored on revised data (`scores.actuals`).
- **Check every number the site shows** against the JSON files, and tell your human about any mismatch.

## Who is waiting on you

| What | Who | By |
| --- | --- | --- |
| `directorate_area_month.parquet` | Production (for the Directorate drivers in `drivers_area_month.parquet`, due 21:30), Price | 18:30 |
| `ssb_weekly.parquet` | Production (export volume for B1), Price | 18:30 |
| `fx_daily.parquet` | Price | 18:30 |
| `farm_week.parquet` from 2017, `farms.parquet` | Production | 21:30 |
| `farms.json`, `farm_weeks/` | Front end | 21:30 |
| `farm_week.parquet` for 2012–2016 | Production, Price | 23:30 |
| `trap.vl.json` | Front end | 00:00 |
| `channels_bins.vl.json`, `nowcast_backtest.vl.json` (development window) | Front end | 02:00 |
| `nowcast_backtest.vl.json` with the holdout, `drivers_importance.vl.json`, `channels_panel.vl.json` | Front end | 05:00 |

## Ask your human when

- the token or the test call fails, or sea temperature, treatments or the disease flags are missing;
- a column in the contract can't be filled;
- `feed_kg` or `dead` fails its checks;
- it's 21:00 and `farm_week.parquet` isn't close to done;
- a findings JSON doesn't match the contract, so a chart can't be built from it;
- holdout rows or scores appear in any JSON before 04:00, because that breaks the holdout rule.
