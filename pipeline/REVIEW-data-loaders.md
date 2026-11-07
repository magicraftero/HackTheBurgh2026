# Review: `data/loaders` (Data), round 2

Checked on 7 Nov 2026 by Jesse's coding agent. Branch `data/loaders` at `9ea1d7f`: the loaders, `f9b0d2c` (the BarentsWatch stage plus the first review's fixes) and a merge of main. It was compared with `origin/main` at `507f5d9` and Production's `origin/production` at `80bcad0`. Delete this file once every point is handled.

**Verdict: merge after one fix.** The fix is one line in `pipeline/build_farm_week.py`, then a rebuild from files already on disk. Everything else is non-blocking.

## Who needs to do what

| Who | What |
| --- | --- |
| Data | Fix the area mismatch below, rebuild and push. If there's time, items 3–5. |
| Data and Production | Agree whether Data's fix or a looser check in `weekly_indices.py` handles areas, before the 22:30 indices. |
| Data and Price | Decide how to treat disease data before 2014 (item 1). |
| Production | Note that this branch adds `tests/__init__.py`, which lets plain `pytest` import `analysis`. |
| Everyone | Agree on one pandas major version (item 8), and OK the contract changes in items 2 and 6. |
| Front end | `farms.json` and `farm_weeks/` are ready and match the contract (see "What was checked"). |

## Blocking: one site's area stops Production's weekly indices

`analysis/weekly_indices.py` on `origin/production` (line 296) stops with "Farm areas disagree between farm_week and farms" if a `farm_week` row has a different area from `farms.parquet`. One site does: locality 34537 is area 4 in `farm_week` for 3 weeks in 2014, but area 3 in `farms.parquet` (3 rows of 830,284).

Fix in `pipeline/build_farm_week.py:106`: take every site's area from `farms.parquet`, and fall back to the lice report only for sites missing there:

```python
df["area"] = df["locality_no"].map(farm_area).astype("Int64").fillna(df["area"])
```

Then run `python -m pipeline.build_farm_week && python -m pipeline.export_site_data && python -m pipeline.checks`, which needs no downloads. Also add a check to `pipeline/checks.py` that every `farm_week` area equals the site's `farms.parquet` area. The alternative is for Production to loosen its check; agree which one.

## Non-blocking

1. **Disease data is sparse before 2014.** There are 153 flagged site-weeks in 2012 and 2,453 in 2013, against 6,800–8,400 a year from 2014 to 2020. `isa` and `pd` are false, not null, in those early years, so `disease_share` will show a rise that only reflects record-keeping. This matters for Price, because c1 includes disease share and lag lengths are chosen on 2012–2018. Options: set `isa`/`pd` to null before 2014-W01, or have Price start disease share in 2014. `data/README.md` already warns about this.
2. **Two columns not in the contract.** `farm_week` has `lice_limit` and `above_limit`. Code that picks columns by name, as Production's does, is unaffected, but it's a contract change, so the team needs to OK it. Also, BarentsWatch's `above_limit` flag isn't the same as `adult_female > lice_limit` in 872 of the 18,047 reported weeks it flags. If the dashboard shows it, say it's BarentsWatch's own flag.
3. **A download that keeps failing leaves a silent gap.** `pipeline/fetch_barentswatch.py:80-86` gives up on a report-year after 3 failed attempts and still prints "done". Today's data is complete: every week from 2012-W01 to 2026-W45 lists 1,042–1,113 sites. Fix: collect the failures, print them and exit with an error.
4. **A retry drops custom headers.** `pipeline/bw_client.py:53` pops `headers` inside the retry loop, so a retry after a 401 loses them. No caller passes headers today; pop them once, before the loop.
5. **Sites with no area are dropped.** `pipeline/fetch_register.py:69-72` drops them, but the Data plan (task 5) says to use the nearest register site's area. Check the "dropping N sites" line the script prints. If N is above 0, those sites are missing from `farms` and `farm_week`.
6. **Coordinates are rounded differently from the contract.** `farms.json` rounds lat/lon to 4 decimals (about 10 m), not the contract's 4 significant figures (about 1 km). That's better for a map, but record it in the contract.
7. **Two files aren't in the ownership table.** `data/README.md` and `tests/__init__.py` aren't covered by the contract's ownership table. Both are harmless.
8. **pandas versions may differ.** The tables were written with pandas 3.1.1, but `requirements.txt` allows `pandas>=2.2`. String columns load as `object` on 2.x and as `str` on 3.x.

## Fixed since the first review

- Blank cells in the Directorate file now print a warning and fail the check.
- The Norges Bank loader now fails on unparseable values, an empty series or days with only one rate.
- `--offline` reruns no longer write to `release_log.parquet`, and its dates are now `datetime64[ns]`.

## What was checked

- **Ownership and safety:** all 38 files the branch adds belong to Data, apart from item 7. Nothing changes in `docs/` or `prereg/`. There's no `.env`, token, raw data or hard-coded credential. The largest file is `farm_week.parquet`, at 4.3 MB.
- **BarentsWatch code:** credentials come only from `.env` and are never printed. The token is cached, and a 401 gets a new token and one retry. Calls are single-threaded, and raw files go to `data/raw/`, which git ignores.
- **`directorate_area_month`, `ssb_weekly` and `fx_daily`:** unchanged since the first review, which found them correct.
  - Directorate: areas 0–13 in every month, and national September 2026 is 41.93 m fish, 193,752 t and 4.62 kg.
  - SSB: weeks run from 2000-W01 to 2026-W44 with no gaps.
  - Norges Bank: rates from 2011-12-01 with no nulls.
  - Every publication-date rule is right.
- **`farms.parquet`:** columns and dtypes match the contract. There are 1,475 unique sites, all in areas 1–13 with coordinates inside Norway. Capacity is null for 416 sites, mostly closed ones. Only 2 of the 861 sites reporting in 2026 lack it, and Production fills gaps with the area median.
- **`farm_week.parquet`:**
  - 830,284 rows, with the contract columns in order plus the two extras. Bool columns are nullable `boolean`, and dates are `datetime64[ns]` at midnight.
  - Weeks run from 2012-W01 to 2026-W45 with no gaps or duplicate site-weeks. `week_start` is the ISO Monday, and `available_at` is the Sunday that ends week w + 1.
  - Lice values are null in every unreported week, never 0. `sea_temp_c` runs from −0.2 to 23.5 °C, with sensible monthly means.
  - `treated` matches `treat_types`. Disease flags come in runs of about 44 weeks, so they're weekly statuses, not one-off events.
  - Every site is in `farms.parquet`.
- **The unfinished week:** only 72 of 1,060 sites have reported for 2026-W45. Its `available_at` (15 Nov) keeps it out of models, and the site JSON stops at W44.
- **Site JSON:**
  - `farms.json` matches `farms.parquet` site by site, and `farm_weeks/index.json` lists 2019–2026.
  - Each year file has the contract keys and only weeks whose reporting deadline has passed. Its `ids` are the sites that reported that year, all of them in `farms.json`.
  - Every `mobile`, `treated`, `temp` and `disease` cell matches `farm_week`, rounded to 2 decimals.
  - The largest year file is 0.70 MB.
- **Production compatibility:** this branch and `origin/production` change no files in common. Every Data column that Production's code names exists in these tables. The area check is the only thing that fails.

**Not run:** imports, tests and any fetch. The reviewing laptop has no pandas, so the Parquet files were read with a standard-library reader. The raw data exists only on the Data laptop.

## Merging

The branch already contains main. After the fix, run `git switch main`, `git merge --ff-only origin/main`, `git merge --ff-only origin/data/loaders` and `git push origin main`.
