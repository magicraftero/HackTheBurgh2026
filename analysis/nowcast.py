"""Walk-forward production nowcast, test F1 and the driver ranking.

Each target month m is nowcast on D(m), the 10th of month m + 1, from
Directorate months up to m - 1 and weekly rows public by D(m). Every anomaly
is recomputed with ``fit_end`` at month m - 1, and every model is refitted on
area-months before m. All models train and score on the same rows, so the
comparison between them is like for like.

    python -m analysis.nowcast           development window only (default)
    python -m analysis.nowcast --final   full window with the holdout, once, at the freeze
"""

from __future__ import annotations

import argparse
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Final

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.stats import norm

from analysis.anomalies import Frequency, Transform, decompose
from analysis.config import (
    AREAS,
    DEVELOPMENT_WINDOW,
    F1_MAXIMUM_P_VALUE,
    F1_MINIMUM_IMPROVEMENT_PCT,
    HOLDOUT_WINDOW,
    NOWCAST_DAY_OF_FOLLOWING_MONTH,
    PROCESSED_DATA_DIR,
    SITE_DATA_DIR,
)
from analysis.drivers import add_directorate_levels
from analysis.io import round_significant, write_json_atomic, write_parquet_atomic
from analysis.panel import monthly_export_levels, week_start_from_label

FREEZE_AT: Final = datetime(2026, 11, 8, 4, 0)
MIN_ROWS_PER_PARAMETER: Final = 3
ACTUALS_NOTE: Final = "latest revised data, not first releases"
LATEST_MONTH: Final = HOLDOUT_WINDOW.end

OUTCOMES: Final[dict[str, str]] = {
    "log_kg": "harvest_kg",
    "log_count": "harvest_count",
    "log_avg_kg": "avg_kg",
}
LEVEL_KEYS: Final[dict[str, str]] = {"log_kg": "kg", "log_count": "count", "log_avg_kg": "avg_kg"}
MODELS: Final = ("b0", "b1", "drivers")

DIRECTORATE_FEATURES: Final[list[tuple[str, str, Transform]]] = [
    ("biomass_kg", "biomass_anom", "log"),
    ("fish_stock", "fish_stock_anom", "log"),
    ("smolt_pipe", "smolt_pipe_anom", "none"),
    ("feed_rate", "feed_rate_anom", "log"),
    ("mortality", "mortality_anom", "log1p"),
]
WEEKLY_FEATURES: Final = [
    "mobile_anom",
    "treat_anom",
    "disease_share",
    "dd_below8",
    "dd_8to14",
    "dd_above14",
]
WEEKLY_LEVELS: Final = [
    "mobile_idx",
    "treat_rate",
    "disease_share",
    "dd_below8",
    "dd_8to14",
    "dd_above14",
]

B0_FEATURES: Final = ["biomass_anom_l1", "fish_stock_anom_l1"]
B1_FEATURES: Final = [*B0_FEATURES, "export_vol_anom"]
DRIVERS_FEATURES: Final = [
    *B1_FEATURES,
    "smolt_pipe_anom_l1",
    "feed_rate_anom_l1",
    "mortality_anom_l1",
    *[f"{column}{suffix}" for column in WEEKLY_FEATURES for suffix in ("", "_l1")],
]


@dataclass(frozen=True)
class DriverGroup:
    name: str
    label: str
    columns: tuple[str, ...]


DRIVER_GROUPS: Final[list[DriverGroup]] = [
    DriverGroup("stock", "Stock (biomass, fish numbers)", ("biomass_anom", "fish_stock_anom")),
    DriverGroup("market", "Market (export volume)", ("export_vol_anom",)),
    DriverGroup("pipeline", "Smolt pipeline", ("smolt_pipe_anom",)),
    DriverGroup("feed", "Feed per kg of biomass", ("feed_rate_anom",)),
    DriverGroup("temperature", "Sea temperature", ("dd_below8", "dd_8to14", "dd_above14")),
    DriverGroup("losses", "Losses (deaths, disease)", ("mortality_anom", "disease_share")),
    DriverGroup("lice", "Lice and treatments", ("mobile_anom", "treat_anom")),
]


class PreparedInputs:
    """Inputs indexed once, so each monthly vintage is cheap to rebuild."""

    def __init__(
        self,
        directorate: pd.DataFrame,
        weekly_area: pd.DataFrame,
        ssb_weekly: pd.DataFrame,
    ) -> None:
        self.include_disease = bool(weekly_area["disease_share"].notna().any())

        areas = directorate.loc[directorate["area"].isin(AREAS)].copy()
        areas["date"] = pd.to_datetime(areas["month"] + "-01")
        self.first_month: pd.Timestamp = areas["date"].min()
        self.directorate = {
            int(area): group.set_index("date").sort_index()
            for area, group in areas.groupby("area")
        }

        weekly = weekly_area.copy()
        weekly["week_start"] = week_start_from_label(weekly["week"])
        weekly["available_at"] = pd.to_datetime(weekly["available_at"])
        self.weekly = {
            int(area): group.set_index("week_start").sort_index()
            for area, group in weekly.groupby("area")
        }

        ssb = ssb_weekly.copy()
        ssb["week_start"] = pd.to_datetime(ssb["week_start"])
        ssb["available_at"] = pd.to_datetime(ssb["available_at"])
        self.ssb = ssb


def model_features(include_disease: bool) -> dict[str, list[str]]:
    drivers = [
        column
        for column in DRIVERS_FEATURES
        if include_disease or not column.startswith("disease_share")
    ]
    return {"b0": list(B0_FEATURES), "b1": list(B1_FEATURES), "drivers": drivers}


def ranking_features(drivers: Sequence[str]) -> dict[str, list[str]]:
    return {
        f"without_{group.name}": [c for c in drivers if _base_name(c) not in group.columns]
        for group in DRIVER_GROUPS
    }


def forecast_date(target: pd.Period) -> pd.Timestamp:
    return (target + 1).to_timestamp() + pd.Timedelta(days=NOWCAST_DAY_OF_FOLLOWING_MONTH - 1)


def target_months(final: bool) -> pd.PeriodIndex:
    end = HOLDOUT_WINDOW.end if final else DEVELOPMENT_WINDOW.end
    return pd.period_range(DEVELOPMENT_WINDOW.start, end, freq="M")


def window_of(month: str) -> str:
    return "dev" if month <= DEVELOPMENT_WINDOW.end else "holdout"


def holdout_unlocked(now: datetime, confirm_freeze: bool) -> bool:
    return confirm_freeze or now >= FREEZE_AT


def build_vintage(
    prepared: PreparedInputs,
    target: pd.Period,
    made_on: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Every area-month up to ``target`` as it looked on the forecast date.

    ``made_on`` defaults to D(target); a live nowcast passes an earlier date.
    """

    made_on = forecast_date(target) if made_on is None else min(made_on, forecast_date(target))
    last_known = (target - 1).to_timestamp()
    weekly_fit_end = (target - 1).to_timestamp(how="end").normalize()
    grid = pd.date_range(prepared.first_month, target.to_timestamp(), freq="MS")

    public_ssb = prepared.ssb.loc[prepared.ssb["available_at"] <= made_on]
    export = monthly_export_levels(public_ssb).reindex(grid)
    export_anom = _components(export, "M", "log", last_known)["anomaly"]

    frames = []
    for area in AREAS:
        full = prepared.directorate[area].reindex(grid)
        known = full.copy()
        known.loc[known.index > last_known] = np.nan
        levels = add_directorate_levels(known)

        frame = pd.DataFrame(index=grid)
        for level, name, transform in DIRECTORATE_FEATURES:
            parts = _components(levels[level], "M", transform, last_known)
            frame[f"{name}_l1"] = parts["anomaly"].shift(1)
        frame["export_vol_anom"] = export_anom
        weekly = _monthly_weekly_features(
            prepared.weekly.get(area), made_on, weekly_fit_end, grid
        )
        for column in WEEKLY_FEATURES:
            frame[column] = weekly[column]
            frame[f"{column}_l1"] = weekly[column].shift(1)
        for outcome, column in OUTCOMES.items():
            parts = _components(known[column], "M", "log", last_known)
            frame[f"{outcome}_anom"] = parts["anomaly"]
            frame[f"{outcome}_base"] = parts["level"] + parts["season"]
            frame[f"{outcome}_actual"] = np.log(full[column].where(full[column] > 0))
        frame.insert(0, "area", area)
        frame.insert(1, "date", grid)
        frames.append(frame.reset_index(drop=True))
    return pd.concat(frames, ignore_index=True)


def nowcast_month(
    vintage: pd.DataFrame,
    target: pd.Period,
    feature_sets: dict[str, list[str]],
    sample_columns: Sequence[str],
) -> pd.DataFrame:
    """Fit every feature set on months before ``target`` and predict it."""

    target_start = target.to_timestamp()
    train = vintage.loc[vintage["date"] < target_start]
    test = vintage.loc[vintage["date"] == target_start]
    sample = list(sample_columns)
    n_parameters = max(len(features) for features in feature_sets.values()) + 1

    results = []
    for outcome in OUTCOMES:
        anomaly_column = f"{outcome}_anom"
        base_column = f"{outcome}_base"
        train_rows = train[anomaly_column].notna() & train[sample].notna().all(axis=1)
        test_rows = (test[base_column].notna() & test[sample].notna().all(axis=1)).to_numpy()
        n_train = int(train_rows.sum())
        fit_allowed = n_train >= MIN_ROWS_PER_PARAMETER * n_parameters and test_rows.any()

        result = pd.DataFrame(
            {
                "area": test["area"].to_numpy(),
                "month": str(target),
                "made_on": forecast_date(target).strftime("%Y-%m-%d"),
                "window": window_of(str(target)),
                "outcome": outcome,
                "actual": test[f"{outcome}_actual"].to_numpy(),
                "n_train": n_train,
            }
        )
        y = train.loc[train_rows, anomaly_column].to_numpy(float)
        base = test.loc[test_rows, base_column].to_numpy(float)
        for name, features in feature_sets.items():
            predictions = np.full(len(test), np.nan)
            if fit_allowed:
                fitted = sm.OLS(y, design_matrix(train.loc[train_rows, features])).fit()
                predictions[test_rows] = base + design_matrix(test.loc[test_rows, features]) @ fitted.params
            result[name] = predictions
        results.append(result)
    return pd.concat(results, ignore_index=True)


def run_backtest(
    prepared: PreparedInputs,
    months: Iterable[pd.Period],
    feature_sets: dict[str, list[str]],
    sample_columns: Sequence[str],
    *,
    progress: bool = False,
) -> pd.DataFrame:
    frames = []
    for target in months:
        vintage = build_vintage(prepared, target)
        frames.append(nowcast_month(vintage, target, feature_sets, sample_columns))
        if progress:
            print(f"  nowcast {target} done", flush=True)
    return pd.concat(frames, ignore_index=True)


def mae_scores(
    results: pd.DataFrame, window: str, models: Sequence[str] = MODELS
) -> dict[str, dict[str, Any]] | None:
    rows = results.loc[results["window"] == window]
    if rows.empty:
        return None
    scores: dict[str, dict[str, Any]] = {}
    for outcome in OUTCOMES:
        common = _common_rows(rows.loc[rows["outcome"] == outcome], models)
        scores[outcome] = {
            model: round_significant((common[model] - common["actual"]).abs().mean())
            for model in models
        }
    return scores


def f1_test(results: pd.DataFrame) -> dict[str, Any]:
    """F1 on the holdout: MAE improvement over B1 and the Clark-West test."""

    holdout = results.loc[(results["window"] == "holdout") & (results["outcome"] == "log_kg")]
    common = _common_rows(holdout, ("b1", "drivers"))
    error_b1 = common["actual"] - common["b1"]
    error_drivers = common["actual"] - common["drivers"]
    adjusted = error_b1**2 - (error_drivers**2 - (common["b1"] - common["drivers"]) ** 2)
    monthly = adjusted.groupby(common["month"]).mean().sort_index()
    clark_west = sm.OLS(monthly.to_numpy(), np.ones(len(monthly))).fit(
        cov_type="HAC", cov_kwds={"maxlags": 3}
    )
    statistic = float(clark_west.tvalues[0])
    p_value = float(norm.sf(statistic))
    mae_b1 = float(error_b1.abs().mean())
    mae_drivers = float(error_drivers.abs().mean())
    improvement = 100 * (1 - mae_drivers / mae_b1)
    return {
        "window": "holdout",
        "mae_b1": round_significant(mae_b1),
        "mae_drivers": round_significant(mae_drivers),
        "improvement_pct": round_significant(improvement),
        "cw_stat": round_significant(statistic),
        "cw_p": round_significant(p_value),
        "pass": bool(improvement >= F1_MINIMUM_IMPROVEMENT_PCT and p_value < F1_MAXIMUM_P_VALUE),
    }


def latest_example(results: pd.DataFrame, f1: dict[str, Any]) -> dict[str, Any]:
    """The last holdout month as made on its forecast date, by area and nationally."""

    model = "b1" if f1["mae_b1"] < f1["mae_drivers"] else "drivers"
    rows = results.loc[(results["month"] == LATEST_MONTH) & (results["outcome"] == "log_kg")]
    rows = rows.loc[rows["actual"].notna() & rows[model].notna()].sort_values("area")
    predicted = np.exp(rows[model])
    actual = np.exp(rows["actual"])
    national_pred = float(predicted.sum())
    national_actual = float(actual.sum())
    return {
        "month": LATEST_MONTH,
        "made_on": forecast_date(pd.Period(LATEST_MONTH, "M")).strftime("%Y-%m-%d"),
        "model": model,
        "national": {
            "pred_kg": round_significant(national_pred),
            "actual_kg": round_significant(national_actual),
            "error_pct": round_significant(_error_pct(national_pred, national_actual)),
        },
        "areas": [
            {
                "area": int(area),
                "pred_kg": round_significant(pred),
                "actual_kg": round_significant(act),
                "error_pct": round_significant(_error_pct(pred, act)),
            }
            for area, pred, act in zip(rows["area"], predicted, actual)
        ],
    }


def driver_ranking(results: pd.DataFrame, drivers: Sequence[str]) -> dict[str, Any]:
    """Rise in walk-forward MAE when each driver group leaves the Drivers model."""

    without = [f"without_{group.name}" for group in DRIVER_GROUPS]
    by_outcome: dict[str, list[dict[str, Any]]] = {}
    groups: list[dict[str, Any]] = []
    full_mae: float | None = None
    for outcome in OUTCOMES:
        common = _common_rows(results.loc[results["outcome"] == outcome], ["drivers", *without])
        baseline = float((common["drivers"] - common["actual"]).abs().mean())
        rows = []
        for group in DRIVER_GROUPS:
            mae_without = float((common[f"without_{group.name}"] - common["actual"]).abs().mean())
            rows.append(
                {
                    "group": group.name,
                    "label": group.label,
                    "columns": [c for c in group.columns if c in {_base_name(d) for d in drivers}],
                    "mae_without": round_significant(mae_without),
                    "increase_pct": round_significant(100 * (mae_without / baseline - 1)),
                }
            )
        if outcome == "log_kg":
            full_mae = baseline
            groups = rows
        else:
            by_outcome[outcome] = [
                {"group": row["group"], "increase_pct": row["increase_pct"]} for row in rows
            ]
    return {
        "outcome": "log_kg",
        "window": f"{DEVELOPMENT_WINDOW.start} to {HOLDOUT_WINDOW.end}",
        "full_mae": round_significant(full_mae),
        "groups": groups,
        "by_outcome": by_outcome,
    }


def backtest_records(results: pd.DataFrame) -> list[dict[str, Any]]:
    records = []
    for (area, month), rows in results.groupby(["area", "month"], sort=True):
        by_outcome = rows.set_index("outcome")
        first = rows.iloc[0]
        records.append(
            {
                "area": int(area),
                "month": month,
                "window": first["window"],
                "made_on": first["made_on"],
                "actual": {
                    LEVEL_KEYS[o]: round_significant(np.exp(by_outcome.at[o, "actual"]))
                    for o in OUTCOMES
                },
                "pred": {
                    model: {
                        LEVEL_KEYS[o]: round_significant(np.exp(by_outcome.at[o, model]))
                        for o in OUTCOMES
                    }
                    for model in MODELS
                },
            }
        )
    return records


def build_nowcast_json(results: pd.DataFrame, final: bool) -> dict[str, Any]:
    f1 = f1_test(results) if final else None
    return {
        "models": list(MODELS),
        "windows": {
            "dev": [DEVELOPMENT_WINDOW.start, DEVELOPMENT_WINDOW.end],
            "holdout": [HOLDOUT_WINDOW.start, HOLDOUT_WINDOW.end],
        },
        "backtest": backtest_records(results),
        "scores": {
            "dev": mae_scores(results, "dev"),
            "holdout": mae_scores(results, "holdout") if final else None,
            "actuals": ACTUALS_NOTE,
        },
        "f1": f1,
        "latest": latest_example(results, f1) if f1 is not None else None,
        "current": None,
    }


def _monthly_weekly_features(
    weekly: pd.DataFrame | None,
    made_on: pd.Timestamp,
    fit_end: pd.Timestamp,
    grid: pd.DatetimeIndex,
) -> pd.DataFrame:
    if weekly is None:
        return pd.DataFrame(np.nan, index=grid, columns=WEEKLY_FEATURES)
    public = weekly.loc[weekly.index <= made_on].copy()
    public.loc[~(public["available_at"] <= made_on), WEEKLY_LEVELS] = np.nan

    features = pd.DataFrame(index=public.index)
    features["mobile_anom"] = _components(public["mobile_idx"], "W", "log1p", fit_end)["anomaly"]
    features["treat_anom"] = _components(
        100 * public["treat_rate"], "W", "log1p", fit_end
    )["anomaly"]
    for column in ("disease_share", "dd_below8", "dd_8to14", "dd_above14"):
        features[column] = public[column]
    month = (features.index + pd.Timedelta(days=3)).to_period("M").to_timestamp()
    return features.groupby(month).mean().reindex(grid)


def _components(
    series: pd.Series, freq: Frequency, transform: Transform, fit_end: pd.Timestamp
) -> pd.DataFrame:
    try:
        return decompose(series.astype(float), freq, transform, fit_end)
    except ValueError as error:
        if "Not enough usable observations" not in str(error):
            raise
        return pd.DataFrame(np.nan, index=series.index, columns=["y", "level", "season", "anomaly"])


def design_matrix(features: pd.DataFrame) -> np.ndarray:
    return sm.add_constant(features.to_numpy(float), has_constant="add")


def _common_rows(rows: pd.DataFrame, models: Iterable[str]) -> pd.DataFrame:
    columns = ["actual", *models]
    return rows.loc[rows[columns].notna().all(axis=1)]


def _base_name(column: str) -> str:
    return column.removesuffix("_l1")


def _error_pct(predicted: float, actual: float) -> float:
    return 100 * (predicted - actual) / actual


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--final", action="store_true", help="include the holdout (04:00 freeze only)")
    parser.add_argument("--confirm-freeze", action="store_true", help="run --final before 04:00 on the team's say-so")
    parser.add_argument("--processed", type=Path, default=PROCESSED_DATA_DIR)
    parser.add_argument("--site", type=Path, default=SITE_DATA_DIR)
    args = parser.parse_args(argv)

    if args.final and not holdout_unlocked(datetime.now(), args.confirm_freeze):
        raise SystemExit(
            f"The holdout is locked until {FREEZE_AT:%H:%M on %d %b %Y}. "
            "Run without --final for the development window."
        )

    weekly_path = args.processed / "weekly_area_index.parquet"
    if not weekly_path.exists():
        raise FileNotFoundError(f"The nowcast needs the weekly area index: {weekly_path}")
    prepared = PreparedInputs(
        pd.read_parquet(args.processed / "directorate_area_month.parquet"),
        pd.read_parquet(weekly_path),
        pd.read_parquet(args.processed / "ssb_weekly.parquet"),
    )
    feature_sets = model_features(prepared.include_disease)
    drivers = feature_sets["drivers"]
    if args.final:
        feature_sets |= ranking_features(drivers)

    months = target_months(args.final)
    print(f"Nowcasting {months[0]} to {months[-1]} ({len(months)} months)")
    results = run_backtest(prepared, months, feature_sets, drivers, progress=True)

    write_parquet_atomic(results, args.processed / "nowcast_backtest.parquet")
    nowcast = build_nowcast_json(results, args.final)
    write_json_atomic(nowcast, args.site / "nowcast.json")
    if args.final:
        write_json_atomic(driver_ranking(results, drivers), args.site / "drivers.json")

    if not prepared.include_disease:
        print("NOTE: disease_share is null everywhere, so it is left out of the Drivers model.")
    covered = results.groupby("month")["drivers"].apply(lambda values: values.notna().any())
    print(f"Months with no Drivers nowcast at all: {list(covered.index[~covered])}")
    by_area = results.groupby("area")["drivers"].apply(lambda values: values.notna().mean())
    print(f"Share of rows nowcast, by area: {by_area.round(2).to_dict()}")
    first = results.loc[results["outcome"] == "log_kg"].groupby("month")["n_train"].first()
    print(f"Training rows: {first.iloc[0]} for {first.index[0]}, {first.iloc[-1]} for {first.index[-1]}")
    print(f"Development-window MAE: {nowcast['scores']['dev']}")
    if args.final:
        print(f"Holdout MAE: {nowcast['scores']['holdout']}")
        print(f"F1: {nowcast['f1']}")


if __name__ == "__main__":
    main()
