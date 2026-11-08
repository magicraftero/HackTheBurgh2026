"""Build weekly farm-health indices by production area and nationally."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Final

import numpy as np
import pandas as pd

from analysis.anomalies import Transform, anomaly
from analysis.config import AREAS, PROCESSED_DATA_DIR
from analysis.io import write_parquet_atomic

FARM_WEEK_COLUMNS: Final[set[str]] = {
    "locality_no",
    "week",
    "week_start",
    "area",
    "reported",
    "mobile",
    "treated",
    "sea_temp_c",
    "isa",
    "pd",
    "available_at",
}
FARM_COLUMNS: Final[set[str]] = {"locality_no", "area", "capacity_t"}
INDEX_COLUMNS: Final[list[str]] = [
    "mobile_idx",
    "mobile_anom",
    "treat_rate",
    "treat_anom",
    "disease_share",
    "temp_c",
    "dd_anom",
    "dd_below8",
    "dd_8to14",
    "dd_above14",
    "dd_below14",
    "n_reporting",
    "available_at",
]


def build_weekly_indices(
    farm_week: pd.DataFrame,
    farms: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return contract-compliant area and national weekly indices."""

    observations, farm_lookup = _validate_and_prepare(farm_week, farms)
    observations = observations.merge(
        farm_lookup[["locality_no", "capacity_t"]],
        on="locality_no",
        how="left",
        validate="many_to_one",
    )
    area_medians = farm_lookup.groupby("area")["capacity_t"].median()
    observations["weight"] = observations["capacity_t"].fillna(
        observations["area"].map(area_medians)
    )
    if observations["weight"].isna().any() or (observations["weight"] <= 0).any():
        raise ValueError("Every observed farm needs positive capacity or a known area median.")

    reported = observations.loc[observations["reported"].fillna(False)].copy()
    disease_available = bool(
        reported[["isa", "pd"]].notna().to_numpy().any()
    )
    reported["disease"] = _disease_flag(reported, disease_available)

    first_week = observations["week_start"].min()
    last_week = observations["week_start"].max()
    weekly_dates = pd.date_range(first_week, last_week, freq="7D")

    area = _aggregate(reported, ["area", "week_start"])
    area_grid = pd.MultiIndex.from_product(
        [AREAS, weekly_dates], names=["area", "week_start"]
    ).to_frame(index=False)
    area = area_grid.merge(area, on=["area", "week_start"], how="left")
    # Non-reporting rows also have publication dates. Empty weeks remain dated
    # missing observations, never zero-valued health indices.
    releases = observations.groupby(["area", "week_start"])["available_at"].max()
    area["available_at"] = pd.MultiIndex.from_frame(area[["area", "week_start"]]).map(releases)
    area["available_at"] = area["available_at"].fillna(area["week_start"] + pd.Timedelta(days=13))
    area["n_reporting"] = area["n_reporting"].fillna(0).astype(int)
    area = _finish_indices(area, group_columns=["area"])

    national = _aggregate(reported, ["week_start"])
    national = pd.DataFrame({"week_start": weekly_dates}).merge(
        national, on="week_start", how="left"
    )
    national["available_at"] = national["week_start"].map(
        observations.groupby("week_start")["available_at"].max()
    ).fillna(national["week_start"] + pd.Timedelta(days=13))
    national["n_reporting"] = national["n_reporting"].fillna(0).astype(int)
    national = _finish_indices(national, group_columns=[])

    area = area[["area", "week", *INDEX_COLUMNS]]
    national = national[["week", *INDEX_COLUMNS]]
    return area, national


def _aggregate(
    reported: pd.DataFrame,
    group_columns: list[str],
) -> pd.DataFrame:
    keys: str | list[str]
    keys = group_columns[0] if len(group_columns) == 1 else group_columns
    rows: list[dict[str, object]] = []
    for group_key, group in reported.groupby(keys, sort=True, dropna=False):
        key_values = group_key if isinstance(group_key, tuple) else (group_key,)
        row = dict(zip(group_columns, key_values, strict=True))
        row.update(
            {
                "mobile_idx": _weighted_mean(group["mobile"], group["weight"]),
                "treat_rate": _nullable_mean(group["treated"]),
                "disease_share": _nullable_mean(group["disease"]),
                "temp_c": _weighted_mean(group["sea_temp_c"], group["weight"]),
                "n_reporting": int(group["locality_no"].nunique()),
                "available_at": group["available_at"].max(),
            }
        )
        rows.append(row)
    if not rows:
        return pd.DataFrame(
            columns=[
                *group_columns,
                "mobile_idx",
                "treat_rate",
                "disease_share",
                "temp_c",
                "n_reporting",
                "available_at",
            ]
        )
    return pd.DataFrame(rows)


def _finish_indices(
    frame: pd.DataFrame,
    *,
    group_columns: list[str],
) -> pd.DataFrame:
    frame = frame.sort_values([*group_columns, "week_start"]).reset_index(drop=True)
    frame["week"] = frame["week_start"].map(_iso_week)

    if group_columns:
        pieces = [
            _add_group_features(group)
            for _, group in frame.groupby(group_columns, sort=True)
        ]
        return pd.concat(pieces, ignore_index=True)
    return _add_group_features(frame)


def _add_group_features(group: pd.DataFrame) -> pd.DataFrame:
    group = group.sort_values("week_start").copy()
    iso_calendar = group["week_start"].dt.isocalendar()
    group["_iso_year"] = iso_calendar["year"].to_numpy()
    group["_iso_week"] = iso_calendar["week"].to_numpy()
    group["normal_c"] = np.nan

    for _, positions in group.groupby("_iso_week", sort=False).groups.items():
        values = group.loc[positions, "temp_c"].astype(float)
        prior_count = values.notna().cumsum().shift(1, fill_value=0)
        prior_sum = values.fillna(0).cumsum().shift(1, fill_value=0)
        normal = (prior_sum / prior_count.where(prior_count > 0)).where(
            prior_count >= 3
        )
        group.loc[positions, "normal_c"] = normal.to_numpy()

    weekly_temperature_anomaly = 7 * (group["temp_c"] - group["normal_c"])
    group["dd_anom"] = weekly_temperature_anomaly.rolling(
        6, min_periods=6
    ).sum()
    _add_temperature_bands(group)

    group["mobile_anom"] = _safe_weekly_anomaly(
        group["mobile_idx"], group["week_start"], "log1p"
    )
    group["treat_anom"] = _safe_weekly_anomaly(
        100 * group["treat_rate"], group["week_start"], "log1p"
    )
    return group.drop(columns=["_iso_year", "_iso_week", "normal_c"])


def _add_temperature_bands(frame: pd.DataFrame) -> None:
    valid = frame["dd_anom"].notna() & frame["temp_c"].notna()
    conditions = {
        "dd_below8": frame["temp_c"] < 8,
        "dd_8to14": frame["temp_c"].ge(8) & frame["temp_c"].lt(14),
        "dd_above14": frame["temp_c"] >= 14,
    }
    for column, condition in conditions.items():
        frame[column] = np.nan
        frame.loc[valid, column] = 0.0
        frame.loc[valid & condition, column] = frame.loc[
            valid & condition, "dd_anom"
        ]
    frame["dd_below14"] = frame["dd_below8"] + frame["dd_8to14"]


def _safe_weekly_anomaly(
    values: pd.Series,
    dates: pd.Series,
    transform: Transform,
) -> pd.Series:
    if int(values.notna().sum()) < 52:
        return pd.Series(np.nan, index=values.index, dtype=float)
    adjusted = anomaly(
        pd.Series(values.to_numpy(), index=pd.DatetimeIndex(dates)),
        "W",
        transform=transform,
    )
    return pd.Series(adjusted.to_numpy(), index=values.index, dtype=float)


def _weighted_mean(values: pd.Series, weights: pd.Series) -> float:
    valid = values.notna() & weights.notna() & (weights > 0)
    if not bool(valid.any()):
        return np.nan
    return float(
        np.average(values.loc[valid].astype(float), weights=weights.loc[valid])
    )


def _nullable_mean(values: pd.Series) -> float:
    numeric = pd.to_numeric(values, errors="coerce")
    return float(numeric.mean()) if bool(numeric.notna().any()) else np.nan


def _disease_flag(frame: pd.DataFrame, available: bool) -> pd.Series:
    if not available:
        return pd.Series(np.nan, index=frame.index, dtype=float)
    any_true = (frame["isa"].eq(True) | frame["pd"].eq(True)).fillna(False)  # noqa: E712
    both_false = (
        frame["isa"].eq(False) & frame["pd"].eq(False)  # noqa: E712
    ).fillna(False)
    return pd.Series(
        np.select(
            [any_true.to_numpy(dtype=bool), both_false.to_numpy(dtype=bool)],
            [1.0, 0.0],
            default=np.nan,
        ),
        index=frame.index,
    )


def _iso_week(timestamp: pd.Timestamp) -> str:
    iso = timestamp.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def _validate_and_prepare(
    farm_week: pd.DataFrame,
    farms: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    missing_observation_columns = FARM_WEEK_COLUMNS.difference(farm_week.columns)
    missing_farm_columns = FARM_COLUMNS.difference(farms.columns)
    if missing_observation_columns:
        raise ValueError(
            "farm_week input is missing columns: "
            + ", ".join(sorted(missing_observation_columns))
        )
    if missing_farm_columns:
        raise ValueError(
            "farms input is missing columns: "
            + ", ".join(sorted(missing_farm_columns))
        )

    observations = farm_week.loc[:, sorted(FARM_WEEK_COLUMNS)].copy()
    farm_lookup = farms.loc[:, sorted(FARM_COLUMNS)].copy()
    if observations.duplicated(["locality_no", "week"]).any():
        raise ValueError("farm_week has duplicate locality-week rows.")
    if farm_lookup["locality_no"].duplicated().any():
        raise ValueError("farms has duplicate locality rows.")

    observations["week_start"] = pd.to_datetime(
        observations["week_start"], errors="raise"
    )
    observations["available_at"] = pd.to_datetime(
        observations["available_at"], errors="raise"
    )
    if not bool((observations["week_start"].dt.day_of_week == 0).all()):
        raise ValueError("week_start must always be a Monday.")
    if not observations["area"].isin(AREAS).all():
        raise ValueError("farm_week areas must be between 1 and 13.")

    area_check = observations[["locality_no", "area"]].merge(
        farm_lookup[["locality_no", "area"]],
        on="locality_no",
        how="left",
        suffixes=("_observation", "_register"),
        validate="many_to_one",
    )
    if area_check["area_register"].isna().any():
        raise ValueError("Every observed locality must exist in farms.")
    if not bool(
        (
            area_check["area_observation"].astype(int)
            == area_check["area_register"].astype(int)
        ).all()
    ):
        raise ValueError("Farm areas disagree between farm_week and farms.")
    return observations, farm_lookup


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--farm-week",
        type=Path,
        default=PROCESSED_DATA_DIR / "farm_week.parquet",
    )
    parser.add_argument(
        "--farms",
        type=Path,
        default=PROCESSED_DATA_DIR / "farms.parquet",
    )
    args = parser.parse_args()

    for source in (args.farm_week, args.farms):
        if not source.exists():
            raise FileNotFoundError(f"Required input has not landed yet: {source}")

    area, national = build_weekly_indices(
        pd.read_parquet(args.farm_week),
        pd.read_parquet(args.farms),
    )
    area_output = PROCESSED_DATA_DIR / "weekly_area_index.parquet"
    national_output = PROCESSED_DATA_DIR / "weekly_national_index.parquet"
    write_parquet_atomic(area, area_output)
    write_parquet_atomic(national, national_output)
    print(f"Wrote {len(area):,} rows to {area_output}")
    print(f"Wrote {len(national):,} rows to {national_output}")


if __name__ == "__main__":
    main()
