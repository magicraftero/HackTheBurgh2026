# Review: `data/loaders` (Data)

Commit `fe06af6` ("Add Directorate, SSB and Norges Bank loaders with release log"), checked against `origin/main` at `7f626ac` on 7 Nov 2026 by Jesse's coding agent. Delete this file once you've dealt with the points below.

**Verdict: merge after rebasing onto main.** Nothing blocks. The three tables match the contract, and national September 2026 matches the expected figures.

## Worth fixing (none blocking)

1. **Blank raw cells would become 0.** In `pipeline/fetch_directorate.py:41`, `groupby(...).sum()` skips NaN, so a blank cell in the Directorate CSV would turn into a real-looking 0. Today's file has none. Fix: before the groupby, check `raw[list(COLUMNS)].isna().sum()` and warn (or stop) if anything is non-zero.
2. **Bad FX values would become NaN without a warning.** In `pipeline/fetch_norgesbank.py:28`, `errors="coerce"` hides values that don't parse. The 5–14 check (lines 45–48) runs after `dropna()`, so an all-NaN series would pass. Today there are no nulls. Fix: count NaNs per series after parsing, and set `ok = False` if there are any or if a series is empty.
3. **`--offline` reruns log downloads that didn't happen.** `fetch_directorate.py:103`, `fetch_ssb.py:68` and `fetch_norgesbank.py:56` call `log_download` even in offline mode. Each rerun adds a duplicate row to `release_log.parquet`, with `downloaded_at` set to the rerun time. Fix: skip `log_download` when `--offline` is set.
4. **`release_log.parquet` isn't in the contract.** Keeping it is fine, but tell the team it exists. Its dates are `datetime64[us]`, not `[ns]`, because `release_log.py:58` calls `to_parquet` directly instead of `write_parquet`.
5. **`tests/__init__.py` is outside the ownership table.** It's harmless and even helps: plain `pytest` can now import `analysis` for Production's tests on main. Let Production know.
6. **pandas versions may differ between laptops.** The Parquet metadata shows the tables were written with pandas 3.1.1, but `requirements.txt` allows `pandas>=2.2`. String columns (`month`, `week`) load as `object` on pandas 2.x and as `str` on 3.x. Agree on one major version with the team.

**Not an issue:** `ssb_weekly` has no 2026-W53 because that week (28 Dec 2026 to 3 Jan 2027) hasn't happened yet; the Data plan's "Done when" line is wrong to expect it. Week 53 is present for 2004, 2009, 2015 and 2020.

## What was checked

- **Ownership and safety:** all 18 changed files are Data's, except `tests/__init__.py`. Nothing changed in `docs/` or `prereg/`. No `.env`, tokens or `data/raw/`, and the largest file is 119 KB.
- **`directorate_area_month`:** 1,512 rows, one per area 0–13 per month from 2017-10 to 2026-09. Columns, order and dtypes match the contract. `avg_kg` is null in exactly the 83 rows with no harvest and equals kg ÷ count everywhere else. `available_at` is the 20th of the next month. No negative values and no unit jumps. National Sep 2026 (areas 0–13) is 41.93 m fish, 193,752 t and 4.62 kg.
- **`ssb_weekly`:** 1,400 weeks from 2000-W01 to 2026-W44, with no gaps or duplicates. `week_start` is the ISO Monday, and `available_at` is the Wednesday of week w + 1. Price runs 17–125 NOK/kg and volume 1,263–32,385 t, so the columns aren't swapped.
- **`fx_daily`:** 3,757 business days from 2011-12-01 to 2026-11-06, with no weekends, no nulls and every value between 5 and 14. USD/NOK is at or above EUR/NOK on only 48 days, all between 23 Aug and 10 Nov 2022 (the parity period), so the columns aren't swapped. `available_at` is the date + 1.
- **Dates:** every date column in the contract tables is `datetime64[ns]` at midnight.
- **Code:** read in full. The LAKS filter, `(null)` → area 0, the sum over UTSETTSÅR, the column mapping and all four publication-date rules match the contract. Production's `analysis/drivers.py` on main reads only columns this table has.
- **Not run:** imports, tests and `--offline`. pandas wasn't installed on the reviewing laptop, so the Parquet files were read with a standard-library reader, and `--offline` needs `data/raw/`. All five Python files parse.

## Merging

The branch is behind main by Production's commits to `analysis/` and `tests/test_*.py` (3 commits as of `5d65f56`). No file is changed on both sides, so `git rebase origin/main` is clean. Then fast-forward main with `git merge --ff-only`.
