"""Build monthly Directorate production drivers.

Run from the repository root with ``python -m analysis.drivers`` after Data
publishes ``directorate_area_month.parquet``.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Final

import numpy as np
import pandas as pd

from analysis.anomalies import anomaly
from analysis.config import AREAS, PROCESSED_DATA_DIR
from analysis.io import write_parquet_atomic

SOURCE_COLUMNS: Final[set[str]] = {
    "area",
    "month",
    "biomass_kg",
    "fish_stock",
    "smolt_released",
    "feed_kg",
    "dead",
}
SUM_COLUMNS: Final[list[str]] = [
    "biomass_kg",
    "fish_stock",
    "smolt_released",
    "feed_kg",
    "dead",
]
LEVEL_COLUMNS: Final[list[str]] = [
    "biomass_kg",
    "fish_stock",
    "smolt_pipe",
    "feed_rate",
    "mortality",
]
ANOMALY_TRANSFORMS: Final[dict[str, str]] = {
    "biomass_kg": "log",
    "fish_stock": "log",
    "smolt_pipe": "none",
    "feed_rate": "log",
    "mortality": "log1p",
}


def build_directorate_driver_tables(
    source: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build area and national monthly driver tables from Directorate data.

    Area 0 is excluded from area analysis but included in national sums.
    National rates are calculated from national sums, never from area means.
    """

    clean = _validate_and_prepare(source)

    area_frames = [
        _build_driver_frame(group, area=area)
        for area, group in clean.loc[clean["area"].isin(AREAS)].groupby(
            "area", sort=True
        )
    ]
    area_drivers = pd.concat(area_frames, ignore_index=True)
    area_drivers = area_drivers[
        ["area", "month", *LEVEL_COLUMNS, *_anomaly_columns(), "available_at_dir"]
    ]

    national_source = (
        clean.groupby("month", sort=True, as_index=False)[SUM_COLUMNS].sum(
            min_count=1
        )
    )
    national_drivers = _build_driver_frame(national_source, area=None)
    national_drivers = national_drivers[
        ["month", *LEVEL_COLUMNS, *_anomaly_columns(), "available_at_dir"]
    ]
    return area_drivers, national_drivers


def _build_driver_frame(
    source: pd.DataFrame,
    *,
    area: int | None,
) -> pd.DataFrame:
    frame = source.sort_values("month").copy()
    index = pd.DatetimeIndex(pd.to_datetime(frame["month"] + "-01"), name="date")
    frame.index = index
    frame = add_directorate_levels(frame)

    for level_column, transform in ANOMALY_TRANSFORMS.items():
        frame[_anomaly_name(level_column)] = anomaly(
            frame[level_column],
            "M",
            transform=transform,  # type: ignore[arg-type]
        )

    frame["available_at_dir"] = index.map(_directorate_release_date)
    frame["month"] = index.strftime("%Y-%m")
    if area is not None:
        frame["area"] = int(area)
    return frame.reset_index(drop=True)


def add_directorate_levels(frame: pd.DataFrame) -> pd.DataFrame:
    """Add the derived level columns to one area's (or the nation's) months.

    ``frame`` must be sorted on a regular monthly grid, with missing months
    present as NaN rows, so the smolt window counts calendar months.
    """

    frame = frame.copy()
    frame["smolt_pipe"] = np.log1p(
        frame["smolt_released"].shift(12).rolling(12, min_periods=12).sum()
    )
    frame["feed_rate"] = _safe_ratio(frame["feed_kg"], frame["biomass_kg"])
    frame["mortality"] = 1000 * _safe_ratio(frame["dead"], frame["fish_stock"])
    return frame


def _safe_ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    ratio = numerator.astype(float) / denominator.astype(float).where(
        denominator > 0
    )
    return ratio.replace([np.inf, -np.inf], np.nan)


def _directorate_release_date(month_start: pd.Timestamp) -> pd.Timestamp:
    return month_start + pd.offsets.MonthBegin(1) + pd.Timedelta(days=19)


def _anomaly_name(level_column: str) -> str:
    return {
        "biomass_kg": "biomass_anom",
        "fish_stock": "fish_stock_anom",
        "smolt_pipe": "smolt_pipe_anom",
        "feed_rate": "feed_rate_anom",
        "mortality": "mortality_anom",
    }[level_column]


def _anomaly_columns() -> list[str]:
    return [_anomaly_name(column) for column in ANOMALY_TRANSFORMS]


def _validate_and_prepare(source: pd.DataFrame) -> pd.DataFrame:
    missing_columns = SOURCE_COLUMNS.difference(source.columns)
    if missing_columns:
        raise ValueError(
            "Directorate input is missing columns: "
            + ", ".join(sorted(missing_columns))
        )

    frame = source.loc[:, sorted(SOURCE_COLUMNS)].copy()
    frame["area"] = pd.to_numeric(frame["area"], errors="raise").astype(int)
    if not frame["area"].between(0, 13).all():
        raise ValueError("Directorate area values must be between 0 and 13.")
    if frame.duplicated(["area", "month"]).any():
        raise ValueError("Directorate input has duplicate area-month rows.")

    parsed_months = pd.to_datetime(frame["month"] + "-01", errors="raise")
    frame["month"] = parsed_months.dt.strftime("%Y-%m")

    missing_areas = set(AREAS).difference(frame["area"].unique())
    if missing_areas:
        raise ValueError(
            "Directorate input is missing production areas: "
            + ", ".join(map(str, sorted(missing_areas)))
        )

    for area, group in frame.loc[frame["area"].isin(AREAS)].groupby("area"):
        periods = pd.PeriodIndex(group["month"], freq="M").sort_values()
        if len(periods) > 1 and not bool((np.diff(periods.astype(int)) == 1).all()):
            raise ValueError(f"Area {area} does not have a regular monthly grid.")

    return frame.sort_values(["area", "month"]).reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=PROCESSED_DATA_DIR / "directorate_area_month.parquet",
    )
    parser.add_argument(
        "--area-output",
        type=Path,
        default=PROCESSED_DATA_DIR / "drivers_area_month.parquet",
    )
    args = parser.parse_args()

    if not args.input.exists():
        raise FileNotFoundError(
            f"Directorate input has not landed yet: {args.input}"
        )

    source = pd.read_parquet(args.input)
    area_drivers, _ = build_directorate_driver_tables(source)
    write_parquet_atomic(area_drivers, args.area_output)
    print(f"Wrote {len(area_drivers):,} rows to {args.area_output}")


if __name__ == "__main__":
    main()
