# SISALMONI target experiment

Fixed on 8 November 2026 before any SISALMONI model scores are computed.
This is an exploratory target change, separate from the registered SSB-price F2 test.

- Use genuine SISALMONI observations from 2024-W32 onwards, from the official public
  weekly history at `https://salmonprice.com/fishpool/public/priceHistory` and its
  `servlets/newt/public/json/fpiAverages?year=YEAR` data files. Verify the target's
  currency and benchmark definition against the official weekly reports before scoring.
- Do not append Nasdaq, NOS or the old Fish Pool composite to extend training history.
- Target: the SISALMONI 3–6 kg benchmark in **EUR/kg**, using `fpiEUR` in the
  public history. This is the pure SISALMONI benchmark used by the EUR contract.
  The 2024 `fpiNOK` field is the Fish Pool blend and must not be used: at 2024-W33
  it is 73.04, while the official SISALMONI NOK report says 73.19. The EUR field
  is 6.20, agreeing exactly with the official SISALMONI EUR report. Use exact
  weekly observations, not monthly averages or values read from a plotted chart.
- Retain SSB export volumes and the existing FX, monthly stock/weight and weekly
  biology inputs. Earlier SSB export prices must become missing target values;
  they must never fill the SISALMONI history.
- Reuse the existing `rw`, `ar`, `c0` and `c1` model features and direct OLS fits.
  Use the AR lags already frozen in `price/final_run.json` (two at every horizon),
  selected on pre-2019 SSB data. SISALMONI has no pre-2019 observations, so this
  is an explicitly inherited lag choice, not a new index-specific BIC selection.
- SISALMONI is normally released to subscribers on Tuesday, and the contemporary
  weekly report says it is made public on Wednesday around 15:00. Use Thursday
  of the following week as the combined price/export observation's available
  date, conservatively after both normal public releases. Existing exogenous
  publication dates are retained. Historical holiday release dates remain
  approximate; this is not a claim to reproduce intraday trading conditions.
- At each origin refit on expanding data with published labels only, recompute
  anomalies using that origin's information, preserve calendar-week target shifts,
  and require more complete training rows than columns in the largest model,
  exactly as in the existing Price backtest. All four models share the same
  scored origins at each horizon. Report skipped origins and training counts.
- Request target weeks 2025-W01 through 2026-W44, at horizons 2–8 weeks.
  The short history will make some early forecasts unavailable. Do not tune or
  strengthen the sample rule after seeing which results it gives.
- Report log-change MAE, EUR/kg MAE, error relative to no change, direction hit
  rate, matched counts, first/last scored target and c1-versus-c0 improvement.
  Report Clark–West HAC results with horizon-minus-one lags; four weeks is the
  primary comparison, with Holm adjustment for the other horizons.
- Do not call this a fresh independent holdout or an official F2 pass/fail.
  The requested target is new, but this protocol is an exploratory adaptation
  of a model whose SSB evaluation has already been examined.
- Save outputs only under `price/experiments/sisalmoni/`. Preserve the frozen
  SSB backtest, public JSON, charts, results, provenance and final-run record.

No target-specific hyperparameters or features will be chosen from these scores.
