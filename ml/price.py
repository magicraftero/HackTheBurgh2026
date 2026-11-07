"""Walk-forward price forecasts at h = 1..8 weeks: Price's models plus the ML challenger.

Origins, the as-of feature frame (``price.dataset``), the BIC-fixed AR lag and
the matched-sample rule are exactly Price's (``price.backtest.run_backtest``).
rw, ar, c0 and c1 are recomputed here so that h = 1 exists and every model is
scored on the same rows; at h = 2..8 they reproduce ``price_backtest.parquet``.
Targets before 2021-W01 are a warm-up that only seeds the uncertainty bands.

    python -m ml.price           warm-up + development window (default)
    python -m ml.price --final   adds the holdout and the current outlook, once, after 04:00
"""

from __future__ import annotations

import argparse
import json
import os
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits

from analysis.io import write_parquet_atomic
from ml.config import PRICE_FREEZE, PRICE_HORIZONS, PRICE_WARMUP_START, PRICE_WINDOWS, PROCESSED_DATA_DIR
from ml.models import fit_gbm, normal_values, why
from price.calendar import iso_week, week_start
from price.dataset import C0_FEATURES, PriceDataset
from price.models import choose_lag, design, fit_predict, target

ROOT = Path(__file__).resolve().parents[1]
FINAL_RECORD = ROOT / "ml" / "final_price.json"
OUTPUT_NAME = "ml_price_backtest.parquet"
LINEAR = ("ar", "c0", "c1")
MODELS = ("rw", *LINEAR, "ml", "blend")
EXTRA = [f"dp_lag{lag}" for lag in range(8)] + ["price_gap"]
GROUPS = {
    "market": ["v_anom", "v_anom_lag1"],
    "harvest_size": ["weight_anom"],
    "currency": ["eurnok_chg", "eurnok_chg_lag1", "usdnok_chg", "usdnok_chg_lag1"],
    "stock": ["biomass_anom"],
    "feed": ["feed_rate_anom"],
    "temperature": ["dd_below8", "dd_8to14", "dd_above14"],
    "losses": ["mortality_anom", "disease_share"],
    "lice": ["mobile_anom", "mobile_anom_lag1", "treat_anom", "treat_anom_lag1"],
    "momentum": EXTRA,
}
LEVELS = ("disease_share",)
WHY_MODELS = ("c1", "ml")


def window_of(target_week: pd.Timestamp) -> str:
    if target_week < week_start(PRICE_WINDOWS["dev"][0]):
        return "warmup"
    return "dev" if target_week <= week_start(PRICE_WINDOWS["dev"][1]) else "holdout"


def with_extras(frame: pd.DataFrame) -> pd.DataFrame:
    """Add the price gap: p(t) minus the mean of p over the previous 52 weeks."""

    frame = frame.copy()
    frame["price_gap"] = frame["p"] - frame["p"].shift(1).rolling(52, min_periods=39).mean()
    return frame


def forecast_origin(
    dataset: PriceDataset,
    t: pd.Timestamp,
    available_at: pd.Timestamp,
    lags: dict[int, int],
    start: pd.Timestamp,
    end: pd.Timestamp | None,
    window: str | None = None,
) -> list[dict]:
    """Every model at every horizon from one origin, on Price's matched rows."""

    frame = dataset.snapshot(available_at)
    if t not in frame.index:
        return []
    frame = with_extras(frame)
    rows = []
    for h in PRICE_HORIZONS:
        T = t + pd.Timedelta(weeks=h)
        if window is None and not start <= T <= end:
            continue
        largest = design(frame, h, lags[h], "c1", dataset.drivers)
        complete = largest.notna().all(axis=1) & frame.p.notna()
        if not complete.loc[t]:
            continue
        y = target(frame, h)
        targets = frame.index + pd.Timedelta(weeks=h)
        releases = dataset.ssb.available_at.reindex(targets).to_numpy()
        valid = complete & y.notna() & (targets <= t) & (releases <= available_at.to_datetime64())
        if int(valid.sum()) <= largest.shape[1]:
            continue
        if window is None:
            if T not in dataset.ssb.index or pd.isna(dataset.ssb.loc[T, "price_nok_kg"]):
                continue
            actual = float(np.log(dataset.ssb.loc[T, "price_nok_kg"]) - frame.loc[t, "p"])
        else:
            actual = np.nan

        ar_columns = [c for c in largest if c not in dataset.feature_columns]
        columns = {"ar": ar_columns, "c0": ar_columns + C0_FEATURES, "c1": list(largest)}
        predictions = {"rw": 0.0}
        for model in LINEAR:
            x = largest[columns[model]]
            predictions[model] = fit_predict(x.loc[valid], y.loc[valid], x.loc[[t]])

        ml_columns = [c for c in largest if c != "const"]
        ml_columns += [c for c in EXTRA if c not in ml_columns]
        features = pd.concat([largest[[c for c in ml_columns if c in largest]],
                              frame[[c for c in ml_columns if c not in largest]]], axis=1)[ml_columns]
        train = features.loc[valid]
        predict_ml = fit_gbm(train, y.loc[valid].to_numpy(float))
        here = features.loc[[t]]
        predictions["ml"] = float(predict_ml(here)[0])
        predictions["blend"] = (predictions["c0"] + predictions["ml"]) / 2

        row = {"origin_week": iso_week(t), "h": h, "target_week": iso_week(T),
               "origin_date": available_at.strftime("%Y-%m-%d"),
               "window": window or window_of(T), "p_origin": float(frame.loc[t, "p"]),
               "y": actual, "n_train": int(valid.sum()), **predictions}
        normals = normal_values(train, ml_columns, LEVELS, None)
        contributions = {
            "ml": why(predict_ml, here, GROUPS, normals, None),
            "c1": why(_linear(largest.loc[valid, columns["c1"]], y.loc[valid]),
                      largest.loc[[t], columns["c1"]], GROUPS, normals, None),
        }
        for model in WHY_MODELS:
            for name in GROUPS:
                values = contributions[model].get(name)
                row[f"why_{model}_{name}"] = float(values[0]) if values is not None else np.nan
        rows.append(row)
    return rows


def _linear(x: pd.DataFrame, y: pd.Series):
    import statsmodels.api as sm

    params = sm.OLS(y, x).fit().params
    return lambda new: new[x.columns].to_numpy(float) @ params.to_numpy()


_STATE: dict = {}


def _init_worker(processed: str, lags: dict[int, int], start: str, end: str | None) -> None:
    _STATE.update(dataset=PriceDataset.load(processed), lags=lags,
                  start=pd.Timestamp(start), end=None if end is None else pd.Timestamp(end))


def _task(args: tuple[str, str, str | None]) -> list[dict]:
    t, available_at, window = args
    with threadpool_limits(1):
        return forecast_origin(_STATE["dataset"], pd.Timestamp(t), pd.Timestamp(available_at),
                               _STATE["lags"], _STATE["start"], _STATE["end"], window)


def run(processed: Path, final: bool, jobs: int) -> pd.DataFrame:
    dataset = PriceDataset.load(processed)
    if dataset.weekly is None:
        raise FileNotFoundError("Run python -m analysis.weekly_indices first: weekly_national_index is missing")
    start = week_start(PRICE_WARMUP_START)
    end = week_start(PRICE_WINDOWS["holdout" if final else "dev"][1])
    prefit = dataset.snapshot(pd.Timestamp("2018-12-31"))
    lags = {h: choose_lag(prefit, h)[0] for h in PRICE_HORIZONS}
    origins = dataset.ssb.loc[(dataset.ssb.index >= start - pd.Timedelta(weeks=max(PRICE_HORIZONS)))
                              & (dataset.ssb.index <= end - pd.Timedelta(weeks=min(PRICE_HORIZONS)))]
    tasks = [(str(t), str(row.available_at), None) for t, row in origins.iterrows()]
    if final:
        latest = dataset.ssb.loc[dataset.ssb.price_nok_kg.notna()].index.max()
        tasks.append((str(latest), str(dataset.ssb.loc[latest, "available_at"]), "current"))
    print(f"Price ML: {len(tasks)} origins on {jobs} workers; AR lags {lags}", flush=True)
    rows: list[dict] = []
    with ProcessPoolExecutor(max_workers=jobs, initializer=_init_worker,
                             initargs=(str(processed), lags, str(start), str(end))) as pool:
        for position, result in enumerate(pool.map(_task, tasks, chunksize=2)):
            rows.extend(result)
            if (position + 1) % 50 == 0 or position + 1 == len(tasks):
                print(f"  {position + 1}/{len(tasks)} origins done", flush=True)
    results = pd.DataFrame(rows)
    if not final and results["window"].isin(["holdout", "current"]).any():
        raise AssertionError("holdout rows in a development run")
    return results


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--final", action="store_true", help="include the holdout and the current outlook (after 04:00, once)")
    parser.add_argument("--confirm-freeze", action="store_true", help="run --final before 04:00 on the team's say-so")
    parser.add_argument("--processed", type=Path, default=PROCESSED_DATA_DIR)
    parser.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    args = parser.parse_args(argv)

    early = datetime.now(ZoneInfo("Europe/London")) < PRICE_FREEZE
    if args.final:
        if early and not args.confirm_freeze:
            raise SystemExit("The holdout is locked until 04:00 Europe/London on 8 November 2026.")
        if FINAL_RECORD.exists():
            raise SystemExit(f"The final price run is already recorded in {FINAL_RECORD}.")
    elif FINAL_RECORD.exists():
        raise SystemExit("Frozen final results exist; a development run would overwrite them.")

    results = run(args.processed, args.final, args.jobs)
    write_parquet_atomic(results, args.processed / OUTPUT_NAME)
    if args.final:
        FINAL_RECORD.write_text(json.dumps({"run_at": datetime.now().isoformat(), "rows": len(results),
                                            "before_freeze": early, "team_confirmed": args.confirm_freeze}) + "\n")
    print(f"Wrote {len(results):,} rows to {args.processed / OUTPUT_NAME}: "
          f"{results.groupby(['window', 'h']).size().to_dict()}")


if __name__ == "__main__":
    main()
