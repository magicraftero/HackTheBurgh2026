# Price track

**Current pricing display: SISALMONI v2, EUR/kg.** Start with
[the display handoff](../docs/PRICE_DISPLAY_HANDOFF.md). Its canonical public
payload is `web/public/data/price_sisalmoni_v2.json`, located through
`web/public/data/price_display_manifest.json`. Regenerate the package with
`python -m price.export_display`; this packages frozen results without retraining.

**The implementation and `price.json` contract below are the archived SSB/NOK
track.** They remain valid for the registered F2 test, but are a different price
target from the SISALMONI v2 results to present. The selected Ridge display model
and the no-change live recommendation are deliberately separate fields.

This implements `docs/plans/price.md` and the shared contract. It forecasts the
weekly **fresh/chilled farmed salmon export price, NOK/kg** from Statistics Norway
table 03024. The output is static findings and Vega-Lite v5 chart specifications
for the separately owned front end. No server, credentials, or network access is
needed to run the SSB backtest. Its historical integration points are below;
the current display integration is defined in the handoff above.

## Run

From the repository root, using Python 3.11 or newer:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m price.backtest
python -m charts.price_charts
python -m unittest discover -s price/tests -v
```

The root `requirements.txt` is the single install path for all roles. It pins
pandas to 3.1.1, matching Data's table-writing environment. Altair is constrained
to v5 for the agreed chart schema, and NumPy stays below 2.5 for compatibility
with the existing analysis stack. The tests use `unittest` and deterministic
**synthetic test fixtures** in `price/tests/fixtures.py`; those observations are
never exported to the website.

Data must deliver these files under `data/processed/`:

- `ssb_weekly.parquet`: ISO `week`, Monday `week_start`, `price_nok_kg`,
  `volume_t` (export tonnes), `available_at`.
- `fx_daily.parquet`: `date`, `eurnok`, `usdnok` (NOK per currency unit),
  `available_at`.
- `directorate_area_month.parquet`: `area`, `month`, `harvest_kg`,
  `harvest_count`, `biomass_kg`, `feed_kg`, `dead`, `fish_stock`, `available_at`.

Production delivers `weekly_national_index.parquet` with the shared contract's
weekly level columns, past-only temperature bands, and `available_at`. Without
it, Price produces explicitly preliminary rw/ar/c0 results; F2 remains absent.
With it, all four models use the same complete rows. An entirely null
`disease_share` is dropped and documented; other missing predictors skip the
origin for **every** model, with counts in `RESULTS.md`.

Production's `drivers_national_month.parquet` is used when present. Otherwise,
Price builds national monthly levels from Directorate sums over areas 0–13,
including the suppressed area. National average weight is total harvest kg
divided by total fish harvested, feed rate is total feed kg / biomass kg, and
mortality is deaths per 1,000 fish. Missing inputs stay missing. If an area row
is absent, that month's national totals are null and the omission is reported.

Price uses `analysis.anomalies.anomaly` as soon as it is importable. Until
Production is merged it uses the allowed stand-in in `price/anomalies.py`,
matching the 75%-coverage trailing level and Fourier/holiday model. The engine
used is recorded. Weekly series and monthly series are fitted at their own
frequencies; precomputed full-sample anomaly columns are ignored.

Alternate paths, useful while teammates work on separate branches:

```sh
python -m price.backtest --input-dir /path/to/processed --output-root /tmp/price-check
python -m charts.price_charts --input /tmp/price-check/web/public/data/price.json --output-dir /tmp/price-check/web/public/charts
```

`--input-note '...'` adds a provenance caveat to both the public findings and the
results report. Inputs are read-only. Missing required files or invalid schemas
produce a clear CLI error without replacing an existing successful output.

## Outputs and front-end integration

| File | Contents |
| --- | --- |
| `data/processed/price_backtest.parquet` | Every matched prediction: `origin_week`, `h`, `model`, `window`, `y`, `y_hat`, `error` |
| `web/public/data/price.json` | Exact shared keys: `history`, `c1_drivers`, `windows`, `notes`, `scorecard`, `cw`, `by_year`, `f2`, `backtest_h4`, `current` |
| `web/public/charts/price_scorecard.vl.json` | MAE / random-walk MAE at 2–8 ISO weeks; reference line at 1 |
| `web/public/charts/price_by_year.vl.json` | Four-week c0 and c1 MAE by target ISO year |
| `web/public/charts/price_backtest.vl.json` | Holdout actual NOK/kg versus four-week forecasts and an empirical 80% interval; a waiting message until the final run |
| `price/RESULTS.md` | Measured scores, CW tests, training coverage, skipped origins, caveats |
| `price/provenance.json` | Generation date, original source URLs/units, input SHA-256 hashes, lag-selection diagnostics |

The front end can serve these files at `/data/price.json` and
`/charts/price_*.vl.json`, as prescribed by its role plan. Chart data is inlined;
charts read only `price.json`. Labels identify sources, target dates, units,
development/holdout status, and observed/predicted series. The theme is registered
with `charts.theme.register()` and its `PALETTE` covers all shared model and
driver-group names. No front-end-owned files are changed.

The owning front end should show a loading message while fetching, show its
missing-file state on HTTP failure, and render `notes`. A null `f2` means
**unscored**, never failure or zero. `backtest_h4` and `current` also remain null
before the freeze. The chart generator reports a missing findings file clearly;
if findings exist but holdout rows do not, it emits a visible waiting chart.

## Forecast and evaluation rules

- Origin week t is the latest published SSB observation, with forecast date
  equal to its `available_at` (normally Wednesday of t+1). Targets are the price
  change `log(P[t+h]) - log(P[t])`, h=2–8. Calendar target-week terms are known
  ahead of time. Calendar shifts preserve gaps and ISO week 53.
- Every origin filters source rows by publication date, refits anomalies using
  only that snapshot, and aligns each training row to the latest observation
  released by that row's own origin. Exact weekly lags stay null across gaps.
- Exchange-rate predictors are log changes of Monday–Sunday daily means;
  unreleased daily data is excluded. Directorate months are unavailable until
  their release (the following month's 20th if the driver-table stamp is absent).
  BarentsWatch releases are rejected if earlier than 13 days after the week's
  Monday (Sunday of t+1), restricting the current origin to t−1.
- `rw` predicts zero change. `ar` adds price-change lags and three Fourier
  harmonics plus Easter and Christmas. `c0` adds export-volume anomalies,
  national average-weight anomaly, and EUR/NOK changes. `c1` adds exactly the
  driver's list and lags in the Price plan.
- For each horizon, AR lag p=1–8 is selected by BIC on the same 2012–2018 rows,
  including only labels published by the end of 2018. It is then fixed across
  models. If that selection sample is unavailable, Price stops rather than
  selecting lags using development or holdout results.
- Models are direct OLS, refitted at every origin on an expanding matched sample.
  Training labels must already be published, with target week no later than t.
  Underidentified fits are skipped and counted.
- Windows are assigned by **target week**: development `2021-W01`–`2024-W52`;
  holdout `2025-W01`–`2026-W44`. Scores report MAE in log points, ratio to rw,
  and directional hit rate excluding zero predictions (rw is null).
- Clark–West compares c1 with c0 using HAC h−1 and a one-sided normal p-value.
  F2 requires holdout h=4 MAE at least 5% below c0 **and** unadjusted p<0.05.
  The six other horizons receive a within-window Holm correction; h=4 stays
  primary and unadjusted. Decisions use unrounded numbers.
- Holdout NOK/kg forecasts are `P[t] * exp(predicted_change)`. The 10th/90th
  percentile band uses only development errors. Its model is c1 if F2 passes,
  otherwise c0. This model choice occurs **after** holdout evaluation and is
  labelled; the replay is not a prospective model-selection experiment.

## Holdout freeze

Until **8 November 2026, 04:00 Europe/London**, `--final` exits before loading or
scoring data. The default command computes development targets only. Raw price
history from 2017 is public and includes later observations; historical prices
are not holdout forecast scores.

At the freeze, with all c1 inputs delivered:

```sh
python -m price.backtest --final
python -m charts.price_charts
```

A final-run lock prevents concurrent freezes, and `price/final_run.json` records
the successful frozen run. Later development or final CLI runs refuse to
overwrite it. Inspect failed-process locks before removing them; do not delete
a completed final record to tune results. Tests exercise the holdout calculation
on synthetic data only. Optional current forecasts and driver ranking were not
implemented; `current` stays null, consistent with Tier 3 being optional.

## Sources and limits

- [Statistics Norway 03024](https://www.ssb.no/en/statbank/table/03024/): fresh
  salmon export prices (NOK/kg), and volume (tonnes).
- [Directorate of Fisheries](https://register.fiskeridir.no/biomassestatistikk/BIOSTAT-LAKS-OMR/biostat-total-omr.csv):
  national stock, harvest weight, feed and mortality; harvest kg is round-weight
  equivalent.
- [Norges Bank](https://data.norges-bank.no/): EUR/NOK and USD/NOK.
- [BarentsWatch Fish Health](https://www.barentswatch.no/fiskehelse/): national
  lice, treatments, disease and sea-temperature indices supplied by Production.

Historical inputs are today's revised data, not archived releases, and assumed
release dates approximate holiday schedules. There is no futures-price history
in these models. Empirical bands do not guarantee coverage. Forecast success is
reported from the measurements, even if additional biology makes errors worse.
See `INTEGRATION.md` for the exact branch snapshots used for current verification.
