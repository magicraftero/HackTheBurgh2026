"""Walk-forward production forecasts at h = 0..3 months: linear models and the ML challenger.

Every target month T is forecast for each horizon h on its issue date
D = the 10th of month T - h + 1, from the panel in ``ml.vintage``. All models
are refitted on area-months whose actuals were published by D, and they train
and score on the same rows. Rows before 2021 are a warm-up that only seeds the
uncertainty bands.

    python -m ml.supply           warm-up + development window (default)
    python -m ml.supply --final   adds the holdout and the current outlook, once, after 04:00
"""

from __future__ import annotations

import argparse
import json
import os
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits

from analysis.io import write_parquet_atomic
from analysis.nowcast import (
    DRIVER_GROUPS,
    MIN_ROWS_PER_PARAMETER,
    PreparedInputs,
    holdout_unlocked,
    model_features,
)
from ml.config import (
    DEVELOPMENT_WINDOW,
    FREEZE_AT,
    HOLDOUT_WINDOW,
    OUTCOMES,
    PROCESSED_DATA_DIR,
    SUPPLY_HORIZONS,
    SUPPLY_LINEAR,
    SUPPLY_WARMUP_START,
)
from ml.models import fit_gbm, fit_ols, normal_values, why
from ml.vintage import LAGGED_OUTCOMES, LEVEL_FEATURES, ML_EXTRA_FEATURES, build_horizon_vintage, issue_date

ROOT = Path(__file__).resolve().parents[1]
FINAL_RECORD = ROOT / "ml" / "final_supply.json"
OUTPUT_NAME = "ml_supply_backtest.parquet"
WHY_MODELS = ("drivers", "ml")


def window_of(month: str) -> str:
    if month < DEVELOPMENT_WINDOW.start:
        return "warmup"
    return "dev" if month <= DEVELOPMENT_WINDOW.end else "holdout"


def feature_sets(include_disease: bool) -> dict[str, list[str]]:
    linear = model_features(include_disease)
    ml = [*linear["drivers"], *ML_EXTRA_FEATURES, "area"]
    return {**linear, "ml": ml}


def driver_groups(columns: list[str]) -> dict[str, list[str]]:
    """Production's driver groups, plus sea temperature level and recent harvest."""

    groups = {
        group.name: [c for c in columns if c.removesuffix("_l1") in group.columns]
        for group in DRIVER_GROUPS
    }
    groups["temperature"].append("temp_c")
    groups["recent_harvest"] = [*LAGGED_OUTCOMES, "log_avg_kg_level_m"]
    return {name: [c for c in cols if c in columns] for name, cols in groups.items()}


def forecast(
    prepared: PreparedInputs,
    target: pd.Period,
    h: int,
    *,
    made_on: pd.Timestamp | None = None,
    window: str | None = None,
) -> pd.DataFrame:
    """Forecast every area for ``target`` at horizon ``h`` with every model."""

    sets = feature_sets(prepared.include_disease)
    sample = sets["drivers"]
    vintage = build_horizon_vintage(prepared, target, h, made_on)
    issued = issue_date(target, h) if made_on is None else min(pd.Timestamp(made_on), issue_date(target, h))
    known_end = (target - h - 1).to_timestamp()
    train = vintage.loc[vintage["date"] <= known_end]
    test = vintage.loc[vintage["date"] == target.to_timestamp()].reset_index(drop=True)
    n_parameters = len(sample) + 1
    groups = driver_groups(sets["ml"])
    level_columns = [c for c in sets["ml"] if c in LEVEL_FEATURES]

    results = []
    for outcome in OUTCOMES:
        anomaly, base_column = f"{outcome}_anom", f"{outcome}_base"
        train_rows = train[anomaly].notna() & train[sample].notna().all(axis=1)
        test_rows = (test[base_column].notna() & test[sample].notna().all(axis=1)).to_numpy()
        fitting = train.loc[train_rows]
        n_train = len(fitting)
        result = pd.DataFrame({
            "area": test["area"].to_numpy(),
            "month": str(target),
            "h": h,
            "issued": issued.strftime("%Y-%m-%d"),
            "window": window or window_of(str(target)),
            "outcome": outcome,
            "actual": test[f"{outcome}_actual"].to_numpy(),
            "n_train": n_train,
        })
        base = test[base_column].to_numpy(float)
        for model in ("seasonal", *SUPPLY_LINEAR, "ml", "blend"):
            result[model] = np.nan
        if n_train < MIN_ROWS_PER_PARAMETER * n_parameters or not test_rows.any():
            results.append(result)
            continue

        y = fitting[anomaly].to_numpy(float)
        scored = test.loc[test_rows]
        predictors = {model: fit_ols(fitting[sets[model]], y) for model in SUPPLY_LINEAR}
        predictors["ml"] = fit_gbm(fitting[sets["ml"]], y, categorical=["area"])
        result.loc[test_rows, "seasonal"] = base[test_rows]
        for model, predict in predictors.items():
            result.loc[test_rows, model] = base[test_rows] + predict(scored)
        result["blend"] = (result["drivers"] + result["ml"]) / 2

        normals = normal_values(fitting, sets["ml"], level_columns, "area")
        for model in WHY_MODELS:
            model_groups = {name: [c for c in cols if c in sets[model]] for name, cols in groups.items()}
            contributions = why(predictors[model], scored, model_groups, normals, "area")
            for name in groups:
                values = np.full(len(test), np.nan)
                if name in contributions:
                    values[test_rows] = contributions[name]
                result[f"why_{model}_{name}"] = values
        results.append(result)
    return pd.concat(results, ignore_index=True)


def target_months(final: bool) -> pd.PeriodIndex:
    end = HOLDOUT_WINDOW.end if final else DEVELOPMENT_WINDOW.end
    return pd.period_range(SUPPLY_WARMUP_START, end, freq="M")


def current_targets(prepared: PreparedInputs, today: pd.Timestamp) -> list[tuple[pd.Period, int]]:
    """The outlook from today: h = 0 is the month after the latest published Directorate month."""

    released = [
        frame.index[(frame["available_at"] <= today) & frame["harvest_kg"].notna()].max()
        for frame in prepared.directorate.values()
    ]
    latest = pd.Period(min(released), "M")
    return [(latest + 1 + h, h) for h in SUPPLY_HORIZONS]


_PREPARED: PreparedInputs | None = None


def _init_worker(processed: str) -> None:
    global _PREPARED
    _PREPARED = load_inputs(Path(processed))


def _task(args: tuple[str, int, str | None, str | None]) -> pd.DataFrame:
    target, h, made_on, window = args
    assert _PREPARED is not None
    with threadpool_limits(1):
        return forecast(_PREPARED, pd.Period(target, "M"), h,
                        made_on=None if made_on is None else pd.Timestamp(made_on), window=window)


def load_inputs(processed: Path) -> PreparedInputs:
    weekly = processed / "weekly_area_index.parquet"
    if not weekly.exists():
        raise FileNotFoundError(f"Run python -m analysis.weekly_indices first: {weekly} is missing")
    return PreparedInputs(
        pd.read_parquet(processed / "directorate_area_month.parquet"),
        pd.read_parquet(weekly),
        pd.read_parquet(processed / "ssb_weekly.parquet"),
    )


def run(processed: Path, final: bool, jobs: int, today: pd.Timestamp) -> pd.DataFrame:
    tasks: list[tuple[str, int, str | None, str | None]] = [
        (str(target), h, None, None) for target in target_months(final) for h in SUPPLY_HORIZONS
    ]
    if final:
        prepared = load_inputs(processed)
        tasks += [(str(t), h, today.strftime("%Y-%m-%d"), "current") for t, h in current_targets(prepared, today)]
    print(f"Supply ML: {len(tasks)} (target, horizon) forecasts on {jobs} workers", flush=True)
    frames = []
    with ProcessPoolExecutor(max_workers=jobs, initializer=_init_worker, initargs=(str(processed),)) as pool:
        for position, frame in enumerate(pool.map(_task, tasks, chunksize=4)):
            frames.append(frame)
            if (position + 1) % 40 == 0 or position + 1 == len(tasks):
                print(f"  {position + 1}/{len(tasks)} done", flush=True)
    results = pd.concat(frames, ignore_index=True)
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

    if args.final:
        if not holdout_unlocked(datetime.now(), args.confirm_freeze):
            raise SystemExit(f"The holdout is locked until {FREEZE_AT:%H:%M on %d %b %Y}.")
        if FINAL_RECORD.exists():
            raise SystemExit(f"The final supply run is already recorded in {FINAL_RECORD}.")
    elif FINAL_RECORD.exists():
        raise SystemExit("Frozen final results exist; a development run would overwrite them.")

    today = pd.Timestamp(datetime.now().date())
    results = run(args.processed, args.final, args.jobs, today)
    write_parquet_atomic(results, args.processed / OUTPUT_NAME)
    if args.final:
        FINAL_RECORD.write_text(json.dumps({"run_at": datetime.now().isoformat(), "rows": len(results)}) + "\n")
    summary: dict[str, Any] = results.groupby(["window", "h"]).size().to_dict()
    print(f"Wrote {len(results):,} rows to {args.processed / OUTPUT_NAME}: {summary}")


if __name__ == "__main__":
    main()
