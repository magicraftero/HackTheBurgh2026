# Review: `priceRyan` (Price)

Checked on 7 Nov 2026 by Jesse's coding agent. Branch `priceRyan` at `1df553f`, compared with `origin/main` at `30bdfc7` and Production's `origin/production` at `b8fb0d0`, against `docs/plans/00-shared.md`, `docs/plans/price.md` and `prereg/PASS_MARKS.md`. The reviewing laptop has no pandas, so this review is from the code and the committed outputs; the tests and the backtest weren't run here. Delete this file once every point is handled.

**Verdict: merge. Nothing blocks.** The holdout is untouched, every input respects its publication date, and the models and tests match F2. Make the small fixes in items 1, 2 and 4 on this branch, then main gets fast-forwarded.

## Implementation status (7 Nov 2026)

- Items **1, 2 and 4 implemented**: national BarentsWatch releases require at
  least 13 days; theme registration checks the API capability; both duplicate
  `.gitignore` files are removed. Regression tests cover early/valid releases
  and both registration APIs; all three charts also serialize under Altair 5.3.
- Item **3 implemented** by matching Data's existing pandas **3.1.1** version in
  the root `requirements.txt`, retaining NumPy `<2.5` and Altair `<6`. The separate
  Price requirements file is removed, and setup instructions and environment
  errors point to the root file. A fresh shared `.venv` installs successfully;
  All 26 Price tests, Data pipeline checks and `pip check` pass. Price's deprecated
  pandas aliases were replaced with equivalent supported APIs for this version.
- Items **5 and 6 pending Production delivery to main**: neither national table
  is on `origin/main` (`30bdfc7`); the weekly national index is also absent from
  `origin/production` (`e7807b0`). Preserve the existing c1 outputs until both
  authoritative tables land. Then run `python -m price.backtest` followed by
  `python -m charts.price_charts` on up-to-date main, **without `--input-note`**,
  and check input coverage/scale without changing the registered models.

This review is retained until the conditional rerun and note cleanup are done.

## Who needs to do what

| Who | What |
| --- | --- |
| Price | Run `git pull --rebase` first: this file was pushed to `priceRyan`. Then do items 1, 2 and 4 here and tell Jesse. Item 3 once Data agrees. Items 5 and 6 on main, once Production's tables land and before 04:00. |
| Production | Get `weekly_national_index.parquet` and `drivers_national_month.parquet` onto main. Price's 04:00 `--final` run won't start without the weekly index. |
| Price and Data | Agree on one pandas version and the version caps in the root `requirements.txt` (item 3). |
| Front end | `price.json` and the three price chart specs match the contract. Until the rerun, `notes` has a debugging line (item 6). |
| Jesse | Fast-forward main once items 1, 2 and 4 are pushed. |

## Now, on this branch

1. **Tighten the release check for the BarentsWatch index.** `price/dataset.py:46-47` only rejects a week published less than 7 days after its Monday. That suits Statistics Norway (9 days: the Wednesday), but the contract publishes BarentsWatch week w on the Sunday ending week w + 1, which is 13 days. An index with earlier dates would let week t into c1 at origin t, four days early, and nothing would stop it. Fix:

   ```python
   def _weekly(frame, name, columns, min_lag_days=7):  # line 39
       ...
       if (frame.available_at < frame.index + pd.Timedelta(days=min_lag_days)).any():  # line 46
           raise ValueError(f"{name}: a week cannot be published before its release date")
   ```

   Then pass `min_lag_days=13` in the weekly-index call at line 127. Your fixtures already use 13 days (`price/tests/fixtures.py:39`), so the tests still pass.

2. **Make the theme's Altair check safe.** `charts/theme.py:31` tests `hasattr(alt, "theme")`. On Altair 5.3–5.4, which the root `requirements.txt` allows, that may be true even though `alt.theme.register` doesn't exist (not testable here). Data's charts call `register()`, so use:

   ```python
   if hasattr(getattr(alt, "theme", None), "register"):
   ```

3. **One install path.** `price/requirements.txt` caps pandas below 3, NumPy below 2.5 and Altair below 6. The contract's single `.venv` installs from the root `requirements.txt` (Data's file), which has none of those caps, and Data wrote its tables with pandas 3.1.1 (Data's round-2 review, commit `f86afd8`, item 8). Agree on one pandas version with Data and ask Data to put the caps in the root file. Then run `python -m unittest discover -s price/tests -v` in that environment, delete `price/requirements.txt` and point `price/README.md` at the root file. This can land after the merge.

4. **Delete `charts/.gitignore` and `price/.gitignore`.** Both only repeat the root's `__pycache__/`, and `charts/.gitignore` isn't on Price's ownership list.

## On main, before 04:00

5. **Rerun once Production's tables land.** The committed `price.json`, `price_backtest.parquet`, `RESULTS.md` and `provenance.json` came from Data at `9ea1d7f`, Production's anomaly code at `80bcad0` and a weekly national index you built yourself, which isn't committed anywhere, so nobody can reproduce them from main. Main now has Data's round-2 fixes (`30bdfc7`), including one area per site, which removes the locality 34537 clash. When `weekly_national_index.parquet` and `drivers_national_month.parquet` are on main, run `python -m price.backtest` and then `python -m charts.price_charts` from an up-to-date main, and push the outputs. `--final` refuses to run without the weekly index (`price/backtest.py:191-192`), so the 04:00 run depends on this.

6. **Leave out `--input-note`.** The note at `web/public/data/price.json:2082` ("Verification inputs: … locality 34537 …") came from that flag, and the site may show `notes`. Running item 5 without the flag removes it.

## For information

7. **c1 trails c0 on the development window.** At 4 weeks, c1's MAE is 0.098 against c0's 0.077 (Clark–West p = 0.71), and 0.121 against 0.075 in 2024. With 13 extra columns and 118 training rows at the first development forecast, that looks like overfitting, not a bug. After the rerun, check c1's inputs for coverage and scale, but don't add, drop or tune anything to rescue F2: `PASS_MARKS.md` fixes c0 and c1. If F2 fails, the band uses c0, which the code already does.

## What was checked (all fine)

- **Ownership:** all 25 files in `1df553f` are Price's, apart from `charts/.gitignore` (item 4). There are no copies of Data's tables or of `analysis/`, and no file overlaps with `origin/production`.
- **Safety:** no `.env`, tokens or `data/raw/`. `price/` only reads `data/processed/`, and its URLs are provenance labels.
- **Holdout:** in `price.json`, `f2`, `backtest_h4` and `current` are null, and `scorecard` and `cw` hold only `dev` rows. `price_backtest.parquet` has only `dev` rows (origins 2020-W46 to 2024-W50). `RESULTS.md`, `provenance.json` and the chart specs carry no holdout numbers. `--final` is locked until 04:00 and runs once.
- **Timing:** the origin is week t's Statistics Norway `available_at`, and every input is cut at `available_at <= origin`: exchange rates to the day before, Directorate months by their release, BarentsWatch to week t − 1. Week t + h is a calendar shift on Mondays, so week 53 is safe.
- **Anomalies:** refitted at every origin with `fit_end` = origin. The stored `*_anom` columns are overwritten and never used. The stand-in matches the contract signature and gives way to `analysis.anomalies` automatically. Production's temperature normal uses earlier years only, so the `dd` bands are past-only.
- **Models:** rw, ar, c0 and c1 use exactly `price.md`'s columns. BIC on 2012–2018 only picks p = 2 at every horizon. All models share one expanding window from 2018-W33.
- **Scoring:** MAE, `mae_ratio`, `hit_rate` (skips ŷ = 0, null for rw), Clark–West with h − 1 HAC lags, Holm over h = 2, 3 and 5–8 (null at 4), the F2 rule and the `backtest_h4` band from development errors all match.
- **Contract and charts:** the `price.json` keys and the `c1_drivers` order are exact, and `history` starts at 2017-W01. `theme.py` registers and enables `lice` with all 17 `PALETTE` keys. The charts inline their data and are built only from `price.json`.
- **Leakage smell test:** clear. c0's MAE ratio at 4 weeks is 0.866. The 0.72–0.78 ratios at 6–8 weeks are matched by `ar`, which only sees past prices and the calendar, so they come from seasonality.

## Merge plan

Once items 1, 2 and 4 are pushed, Jesse fast-forwards main with `git merge --ff-only origin/priceRyan` (after a rebase onto main if main has moved). Items 5 and 6 then happen on main. Production merges separately: its branch only touches `analysis/` and `tests/`, so it shares no files with this one.
