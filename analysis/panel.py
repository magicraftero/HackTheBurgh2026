"""Assemble the complete monthly driver tables and the area-month panel.

Run from the repository root with ``python -m analysis.panel``. The weekly
farm indices are optional: until they land, their columns are null, so the
Directorate-based outputs can ship on their own and fill in on a rerun.
"""

from __future__ import annotations

import argparse
import warnings
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Final

import numpy as np
import pandas as pd

from analysis.anomalies import Transform, anomaly
from analysis.config import AREAS, PROCESSED_DATA_DIR, SITE_DATA_DIR
from analysis.drivers import build_directorate_driver_tables
from analysis.io import (
    as_int,
    round_decimals,
    round_significant,
    write_json_atomic,
    write_parquet_atomic,
)

WEEKLY_COLUMNS: Final[list[str]] = [
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
]
OUTCOME_COLUMNS: Final[list[str]] = [
    "harvest_count",
    "harvest_kg",
    "avg_kg",
    "count_anom",
    "weight_anom",
    "volume_anom",
]


@dataclass(frozen=True)
class ProductionTables:
    drivers_area_month: pd.DataFrame
    drivers_national_month: pd.DataFrame
    area_month_panel: pd.DataFrame
    notes: list[str] = field(default_factory=list)


def build_production_tables(
    directorate: pd.DataFrame,
    ssb_weekly: pd.DataFrame,
    weekly_area: pd.DataFrame | None = None,
    weekly_national: pd.DataFrame | None = None,
) -> ProductionTables:
    notes: list[str] = []
    area_directorate, national_directorate = build_directorate_driver_tables(
        directorate
    )

    if weekly_area is None or weekly_national is None:
        notes.append(
            "Weekly farm indices not available yet: lice, treatment, disease "
            "and temperature columns are null."
        )
    area_drivers = _attach_weekly(area_directorate, weekly_area, keys=["area"])
    national_drivers = _attach_weekly(
        national_directorate, weekly_national, keys=[]
    )
    national_drivers = national_drivers.merge(
        monthly_export_volume(ssb_weekly), on="month", how="left"
    )
    national_drivers = national_drivers[
        [
            column
            for column in national_drivers.columns
            if column not in {"available_at_dir", "available_at_bw"}
        ]
        + ["available_at_dir", "available_at_bw"]
    ]

    outcomes = build_area_outcomes(directorate)
    panel = outcomes.merge(
        area_drivers, on=["area", "month"], how="left", validate="one_to_one"
    )
    zero_harvest = int(panel["avg_kg"].isna().sum())
    notes.append(
        f"{zero_harvest} area-months have zero harvest (avg_kg is null)."
    )
    return ProductionTables(area_drivers, national_drivers, panel, notes)


def week_month(week_start: pd.Series) -> pd.Series:
    """ISO weeks belong to the month that contains their Thursday."""

    thursdays = pd.to_datetime(week_start) + pd.Timedelta(days=3)
    return thursdays.dt.strftime("%Y-%m")


def week_start_from_label(weeks: pd.Series) -> pd.Series:
    starts = []
    for label in weeks.astype(str):
        year, week = label.split("-W")
        starts.append(pd.Timestamp(date.fromisocalendar(int(year), int(week), 1)))
    return pd.Series(starts, index=weeks.index, dtype="datetime64[ns]")


def weekly_to_monthly(weekly: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    """Average weekly index values over the weeks belonging to each month."""

    frame = weekly.copy()
    frame["month"] = week_month(week_start_from_label(frame["week"]))
    aggregations: dict[str, tuple[str, str]] = {
        column: (column, "mean") for column in WEEKLY_COLUMNS
    }
    aggregations["available_at_bw"] = ("available_at", "max")
    monthly = frame.groupby([*keys, "month"], as_index=False).agg(**aggregations)
    monthly["available_at_bw"] = pd.to_datetime(monthly["available_at_bw"])
    return monthly


def monthly_export_volume(ssb_weekly: pd.DataFrame) -> pd.DataFrame:
    """Sum fresh export tonnes per month; incomplete months stay null."""

    frame = ssb_weekly[["week_start", "volume_t"]].copy()
    frame["week_start"] = pd.to_datetime(frame["week_start"])
    frame["month"] = week_month(frame["week_start"])
    grouped = frame.groupby("month").agg(
        export_vol=("volume_t", "sum"),
        weeks_present=("volume_t", "count"),
    )
    month_starts = pd.to_datetime(grouped.index + "-01")
    expected_weeks = np.array([_thursdays_in_month(start) for start in month_starts])
    grouped.loc[grouped["weeks_present"].to_numpy() != expected_weeks, "export_vol"] = (
        np.nan
    )

    grid = pd.date_range(month_starts.min(), month_starts.max(), freq="MS")
    export = grouped["export_vol"].set_axis(month_starts).reindex(grid)
    result = pd.DataFrame(
        {
            "month": grid.strftime("%Y-%m"),
            "export_vol": export.to_numpy(),
            "export_vol_anom": anomaly(export, "M", "log").to_numpy(),
        }
    )
    return result


def build_area_outcomes(directorate: pd.DataFrame) -> pd.DataFrame:
    """Harvest outcomes and their anomalies for production areas 1-13."""

    required = {"area", "month", "harvest_count", "harvest_kg", "avg_kg"}
    missing = required.difference(directorate.columns)
    if missing:
        raise ValueError(
            "Directorate input is missing columns: " + ", ".join(sorted(missing))
        )

    frames = []
    source = directorate.loc[directorate["area"].isin(AREAS), sorted(required)]
    for area, group in source.groupby("area", sort=True):
        group = group.sort_values("month").copy()
        group.index = pd.DatetimeIndex(pd.to_datetime(group["month"] + "-01"))
        label = f"area {area}"
        group["count_anom"] = _anomaly_or_null(
            group["harvest_count"], "log1p", f"{label} count"
        )
        group["weight_anom"] = _anomaly_or_null(
            group["avg_kg"], "log", f"{label} average weight"
        )
        group["volume_anom"] = _anomaly_or_null(
            group["harvest_kg"], "log1p", f"{label} volume"
        )
        frames.append(group.reset_index(drop=True))

    outcomes = pd.concat(frames, ignore_index=True)
    return outcomes[["area", "month", *OUTCOME_COLUMNS]]


def area_month_records(panel: pd.DataFrame) -> list[dict[str, Any]]:
    """Shape the panel as ``area_month.json`` rows from the contract."""

    records = []
    for row in panel.sort_values(["area", "month"]).itertuples(index=False):
        records.append(
            {
                "area": as_int(row.area),
                "month": row.month,
                "kg": round_significant(row.harvest_kg),
                "count": round_significant(row.harvest_count),
                "avg_kg": round_significant(row.avg_kg),
                "volume_anom": round_significant(row.volume_anom),
                "count_anom": round_significant(row.count_anom),
                "weight_anom": round_significant(row.weight_anom),
                "mobile_idx": round_decimals(row.mobile_idx),
                "dd_anom": round_decimals(row.dd_anom),
                "feed_rate_anom": round_significant(row.feed_rate_anom),
                "mortality_anom": round_significant(row.mortality_anom),
            }
        )
    return records


def _attach_weekly(
    monthly: pd.DataFrame,
    weekly: pd.DataFrame | None,
    *,
    keys: list[str],
) -> pd.DataFrame:
    if weekly is None:
        result = monthly.copy()
        for column in WEEKLY_COLUMNS:
            result[column] = np.nan
        result["available_at_bw"] = pd.Series(
            pd.NaT, index=result.index, dtype="datetime64[ns]"
        )
    else:
        result = monthly.merge(
            weekly_to_monthly(weekly, keys),
            on=[*keys, "month"],
            how="left",
            validate="one_to_one",
        )
    ordered = [
        column
        for column in result.columns
        if column not in {"available_at_dir", "available_at_bw"}
    ]
    return result[[*ordered, "available_at_dir", "available_at_bw"]]


def _anomaly_or_null(series: pd.Series, transform: Transform, label: str) -> pd.Series:
    try:
        return anomaly(series.astype(float), "M", transform)
    except ValueError as error:
        warnings.warn(f"No anomaly for {label}: {error}", stacklevel=2)
        return pd.Series(np.nan, index=series.index, dtype=float)


def _thursdays_in_month(month_start: pd.Timestamp) -> int:
    days = pd.date_range(month_start, month_start + pd.offsets.MonthEnd(0))
    return int((days.dayofweek == 3).sum())


def _read_optional(path: Path) -> pd.DataFrame | None:
    return pd.read_parquet(path) if path.exists() else None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--processed", type=Path, default=PROCESSED_DATA_DIR)
    parser.add_argument("--site", type=Path, default=SITE_DATA_DIR)
    args = parser.parse_args()

    directorate_path = args.processed / "directorate_area_month.parquet"
    ssb_path = args.processed / "ssb_weekly.parquet"
    for required in (directorate_path, ssb_path):
        if not required.exists():
            raise FileNotFoundError(f"Required input has not landed yet: {required}")

    tables = build_production_tables(
        pd.read_parquet(directorate_path),
        pd.read_parquet(ssb_path),
        _read_optional(args.processed / "weekly_area_index.parquet"),
        _read_optional(args.processed / "weekly_national_index.parquet"),
    )
    outputs = {
        "drivers_area_month.parquet": tables.drivers_area_month,
        "drivers_national_month.parquet": tables.drivers_national_month,
        "area_month_panel.parquet": tables.area_month_panel,
    }
    for name, frame in outputs.items():
        write_parquet_atomic(frame, args.processed / name)
        print(f"Wrote {len(frame):,} rows to {args.processed / name}")

    json_path = args.site / "area_month.json"
    records = area_month_records(tables.area_month_panel)
    write_json_atomic(records, json_path)
    print(f"Wrote {len(records):,} records to {json_path}")
    for note in tables.notes:
        print(f"NOTE: {note}")


if __name__ == "__main__":
    main()
