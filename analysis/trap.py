"""The seasonality trap: raw correlations with price against anomaly ones.

Run from the repository root with ``python -m analysis.trap`` once the weekly
national index exists. Numbers are reported as they come out; nothing here
is tuned toward the expected story.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import numpy as np
import pandas as pd

from analysis.anomalies import Transform, anomaly, apply_transform
from analysis.config import PROCESSED_DATA_DIR, SITE_DATA_DIR
from analysis.io import round_significant, write_json_atomic
from analysis.panel import week_start_from_label

TRAP_FROM: Final = "2017-W01"
TRAP_TO: Final = "2026-W44"
HIGHLIGHT: Final = "mobile_idx"


@dataclass(frozen=True)
class TrapDriver:
    name: str
    label: str
    column: str
    transform: Transform
    scale: float = 1.0


TRAP_DRIVERS: Final[list[TrapDriver]] = [
    TrapDriver("mobile_idx", "Mobile lice per fish", "mobile_idx", "log1p"),
    TrapDriver("treat_rate", "Delousing treatments", "treat_rate", "log1p", 100.0),
    TrapDriver("disease_share", "Sites with ISA or PD", "disease_share", "none"),
    TrapDriver("temp_c", "Sea temperature", "temp_c", "none"),
    TrapDriver("export_vol", "Export volume", "volume_t", "log"),
]


def build_trap(ssb_weekly: pd.DataFrame, weekly_national: pd.DataFrame) -> dict[str, Any]:
    frame = _weekly_frame(ssb_weekly, weekly_national)
    in_window = (frame.index >= _monday(TRAP_FROM)) & (frame.index <= _monday(TRAP_TO))
    log_price = apply_transform(frame["price_nok_kg"], "log")
    price_anom = anomaly(frame["price_nok_kg"], "W", "log")

    drivers: list[dict[str, Any]] = []
    series: list[dict[str, Any]] = []
    for driver in TRAP_DRIVERS:
        level = frame[driver.column] * driver.scale
        if level[in_window].isna().all():
            continue
        transformed = apply_transform(level, driver.transform)
        driver_anom = anomaly(level, "W", driver.transform)
        usable = in_window & (
            pd.concat([transformed, log_price, driver_anom, price_anom], axis=1)
            .notna()
            .all(axis=1)
            .to_numpy()
        )
        drivers.append(
            {
                "driver": driver.name,
                "label": driver.label,
                "raw_r": round_significant(_pearson(transformed[usable], log_price[usable])),
                "anom_r": round_significant(_pearson(driver_anom[usable], price_anom[usable])),
            }
        )
        if driver.name == HIGHLIGHT:
            series = [
                {
                    "week": _week_label(week_start),
                    "driver": round_significant(transformed[week_start]),
                    "price": round_significant(log_price[week_start]),
                    "driver_anom": round_significant(driver_anom[week_start]),
                    "price_anom": round_significant(price_anom[week_start]),
                }
                for week_start in frame.index[usable]
            ]

    return {
        "from": TRAP_FROM,
        "to": TRAP_TO,
        "highlight": HIGHLIGHT,
        "drivers": drivers,
        "series": series,
    }


def _weekly_frame(ssb_weekly: pd.DataFrame, weekly_national: pd.DataFrame) -> pd.DataFrame:
    ssb = ssb_weekly.assign(week_start=pd.to_datetime(ssb_weekly["week_start"]))
    ssb = ssb.set_index("week_start")[["price_nok_kg", "volume_t"]]
    weekly = weekly_national.assign(
        week_start=week_start_from_label(weekly_national["week"])
    ).set_index("week_start")
    columns = [d.column for d in TRAP_DRIVERS if d.column in weekly.columns]
    joined = ssb.join(weekly[columns], how="outer")
    grid = pd.date_range(joined.index.min(), joined.index.max(), freq="7D")
    return joined.reindex(grid)


def _pearson(left: pd.Series, right: pd.Series) -> float:
    if len(left) < 3 or left.std() == 0 or right.std() == 0:
        return np.nan
    return float(np.corrcoef(left.to_numpy(float), right.to_numpy(float))[0, 1])


def _monday(week_label: str) -> pd.Timestamp:
    return week_start_from_label(pd.Series([week_label])).iloc[0]


def _week_label(week_start: pd.Timestamp) -> str:
    iso = week_start.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--processed", type=Path, default=PROCESSED_DATA_DIR)
    parser.add_argument("--site", type=Path, default=SITE_DATA_DIR)
    args = parser.parse_args()

    weekly_path = args.processed / "weekly_national_index.parquet"
    if not weekly_path.exists():
        raise FileNotFoundError(
            f"trap.json needs the weekly national index, which hasn't landed: {weekly_path}"
        )
    trap = build_trap(
        pd.read_parquet(args.processed / "ssb_weekly.parquet"),
        pd.read_parquet(weekly_path),
    )
    write_json_atomic(trap, args.site / "trap.json")
    for driver in trap["drivers"]:
        print(f"{driver['label']:<24} raw r = {driver['raw_r']}, anomaly r = {driver['anom_r']}")


if __name__ == "__main__":
    main()
