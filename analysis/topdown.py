"""Production v2: top-down nowcast of area harvest volume (prereg/PRODUCTION_V2.md).

National harvest from same-month exports, split across areas by a small share model, then
averaged with B1 from ``analysis.nowcast``. Run from the repository root with
``python -m analysis.topdown`` after ``python -m analysis.nowcast --final``.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Final

import numpy as np
import pandas as pd

from analysis.config import AREAS, DEVELOPMENT_WINDOW, HOLDOUT_WINDOW, PROCESSED_DATA_DIR
from analysis.io import write_parquet_atomic
from analysis.nowcast import forecast_date

SHARE_FLOOR: Final = 0.001
RATIO_MONTHS: Final = 12
RATIO_MIN_MONTHS: Final = 6
SHARE_INPUTS: Final = ("x_biomass_share", "x_share_l1", "x_share_l12", "x_stock_weight")
MIN_ROWS_PER_PARAMETER: Final = 3


def month_weeks(month: pd.Period) -> pd.DatetimeIndex:
    """Mondays of the ISO weeks whose Thursday falls in ``month``."""

    first, last = month.start_time, month.end_time.normalize()
    mondays = pd.date_range(first - pd.Timedelta(days=6), last, freq="W-MON")
    thursdays = mondays + pd.Timedelta(days=3)
    return mondays[(thursdays >= first) & (thursdays <= last)]


def exports_kg(ssb: pd.DataFrame, month: pd.Period, made_on: pd.Timestamp) -> float:
    """Export volume in kg for ``month``, or NaN if any week is not yet public."""

    public = ssb.loc[ssb["available_at"] <= made_on]
    volumes = public.set_index("week_start")["volume_t"]
    weeks = month_weeks(month)
    if not weeks.isin(volumes.index).all():
        return np.nan
    values = volumes.loc[weeks]
    if values.isna().any():
        return np.nan
    return float(values.sum()) * 1000.0


def area_share_frame(directorate: pd.DataFrame) -> pd.DataFrame:
    """Shares and share-model inputs for every area-month (areas 1-13)."""

    frame = directorate.loc[directorate["area"].isin(AREAS)].copy()
    frame["period"] = pd.PeriodIndex(frame["month"], freq="M")
    frame = frame.sort_values(["area", "period"])
    national = frame.groupby("period")[["harvest_kg", "biomass_kg"]].transform("sum")
    frame["share"] = frame["harvest_kg"] / national["harvest_kg"].where(national["harvest_kg"] > 0)
    frame["biomass_share"] = frame["biomass_kg"] / national["biomass_kg"].where(
        national["biomass_kg"] > 0
    )
    frame["stock_weight"] = frame["biomass_kg"] / frame["fish_stock"].where(frame["fish_stock"] > 0)

    by_area = frame.groupby("area")
    frame["y"] = np.log(frame["share"] + SHARE_FLOOR)
    frame["x_biomass_share"] = np.log(by_area["biomass_share"].shift(1) + SHARE_FLOOR)
    frame["x_share_l1"] = np.log(by_area["share"].shift(1) + SHARE_FLOOR)
    frame["x_share_l12"] = np.log(by_area["share"].shift(12) + SHARE_FLOOR)
    frame["x_stock_weight"] = np.log(by_area["stock_weight"].shift(1))
    _check_consecutive(frame)
    return frame.replace([np.inf, -np.inf], np.nan)


def topdown_month(
    directorate: pd.DataFrame, ssb: pd.DataFrame, target: pd.Period
) -> pd.DataFrame:
    """Top-down log-kg forecast for every area in ``target``, using only data public at D(t)."""

    made_on = forecast_date(target)
    known = directorate.loc[pd.PeriodIndex(directorate["month"], freq="M") <= target - 1]
    blank = pd.DataFrame(
        {"area": list(AREAS), "month": str(target), "harvest_kg": np.nan,
         "biomass_kg": np.nan, "fish_stock": np.nan}
    )
    frame = area_share_frame(pd.concat([known, blank], ignore_index=True))

    result = pd.DataFrame({"area": list(AREAS), "month": str(target)})
    result["national_kg"] = national_forecast(known, ssb, target, made_on)
    result["topdown"] = np.nan
    result["n_train"] = 0

    train = frame.loc[(frame["period"] <= target - 1)].dropna(subset=["y", *SHARE_INPUTS])
    test = frame.loc[frame["period"] == target].dropna(subset=list(SHARE_INPUTS))
    result["n_train"] = len(train)
    if (
        len(train) < MIN_ROWS_PER_PARAMETER * (len(SHARE_INPUTS) + 1)
        or test.empty
        or not np.isfinite(result["national_kg"].iloc[0])
    ):
        return result

    design = np.column_stack([np.ones(len(train)), train[list(SHARE_INPUTS)].to_numpy(float)])
    beta, *_ = np.linalg.lstsq(design, train["y"].to_numpy(float), rcond=None)
    raw = np.exp(np.column_stack([np.ones(len(test)), test[list(SHARE_INPUTS)].to_numpy(float)]) @ beta)
    shares = pd.Series(raw / raw.sum(), index=test["area"].to_numpy())
    national = result["national_kg"].iloc[0]
    result["topdown"] = result["area"].map(np.log(national * shares))
    return result


def national_forecast(
    known: pd.DataFrame, ssb: pd.DataFrame, target: pd.Period, made_on: pd.Timestamp
) -> float:
    exports = exports_kg(ssb, target, made_on)
    if not np.isfinite(exports):
        return np.nan
    areas = known.loc[known["area"].isin(AREAS)]
    harvest = areas.groupby("month")["harvest_kg"].sum()
    ratios = []
    for lag in range(1, RATIO_MONTHS + 1):
        month = target - lag
        past_exports = exports_kg(ssb, month, made_on)
        past_harvest = harvest.get(str(month), np.nan)
        if np.isfinite(past_exports) and past_exports > 0 and past_harvest > 0:
            ratios.append(np.log(past_harvest / past_exports))
    if len(ratios) < RATIO_MIN_MONTHS:
        return np.nan
    return exports * float(np.exp(np.mean(ratios)))


def run_topdown(
    directorate: pd.DataFrame, ssb: pd.DataFrame, months: pd.PeriodIndex
) -> pd.DataFrame:
    return pd.concat(
        [topdown_month(directorate, ssb, month) for month in months], ignore_index=True
    )


def combine_with_b1(topdown: pd.DataFrame, backtest: pd.DataFrame) -> pd.DataFrame:
    """Join nowcast's B1 and Drivers (log kg) and form v2 = mean of topdown and B1."""

    kg = backtest.loc[backtest["outcome"] == "log_kg", ["area", "month", "window", "actual", "b1", "drivers"]]
    merged = kg.merge(topdown, on=["area", "month"], how="left", validate="one_to_one")
    merged["v2"] = (merged["topdown"] + merged["b1"]) / 2
    return merged


def mae_table(frame: pd.DataFrame, models: list[str]) -> pd.DataFrame:
    rows = []
    for window in ("dev", "holdout"):
        part = frame.loc[frame["window"] == window].dropna(subset=["actual", *models])
        if part.empty:
            continue
        row = {"window": window, "n": len(part)}
        row.update({model: (part["actual"] - part[model]).abs().mean() for model in models})
        rows.append(row)
    return pd.DataFrame(rows)


def _check_consecutive(frame: pd.DataFrame) -> None:
    for area, periods in frame.groupby("area")["period"]:
        ordinals = periods.map(lambda p: p.ordinal).to_numpy()
        if len(ordinals) and not (np.diff(ordinals) == 1).all():
            raise ValueError(f"Area {area} months are not consecutive.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--processed", type=Path, default=PROCESSED_DATA_DIR)
    parser.add_argument("--ml-backtest", type=Path, default=None,
                        help="Nikita's ml_supply_backtest.parquet, for the matched comparison")
    args = parser.parse_args()

    directorate = pd.read_parquet(args.processed / "directorate_area_month.parquet")
    ssb = pd.read_parquet(args.processed / "ssb_weekly.parquet")
    ssb["week_start"] = pd.to_datetime(ssb["week_start"])
    ssb["available_at"] = pd.to_datetime(ssb["available_at"])
    backtest = pd.read_parquet(args.processed / "nowcast_backtest.parquet")

    months = pd.period_range(DEVELOPMENT_WINDOW.start, HOLDOUT_WINDOW.end, freq="M")
    topdown = run_topdown(directorate, ssb, months)
    combined = combine_with_b1(topdown, backtest)
    write_parquet_atomic(combined, args.processed / "topdown_backtest.parquet")

    print("Our nowcast rows (B1, Drivers, topdown, v2 all present):")
    print(mae_table(combined, ["b1", "drivers", "topdown", "v2"]).round(4).to_string(index=False))
    national = topdown.drop_duplicates("month").set_index("month")["national_kg"]
    actual_nat = directorate.loc[directorate["area"].isin(AREAS)].groupby("month")["harvest_kg"].sum()
    nat_err = (np.log(actual_nat.reindex(national.index)) - np.log(national)).abs()
    for name, window in (("dev", DEVELOPMENT_WINDOW), ("holdout", HOLDOUT_WINDOW)):
        part = nat_err.loc[window.start:window.end].dropna()
        print(f"National total error ({name}): MAE {part.mean():.4f} over {len(part)} months")

    if args.ml_backtest is not None:
        ml = pd.read_parquet(args.ml_backtest)
        print(ml.columns.tolist())


if __name__ == "__main__":
    main()
