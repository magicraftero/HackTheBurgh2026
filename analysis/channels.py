"""Count × weight channels: descriptive bins now, mechanism panel at 01:30.

Run from the repository root with ``python -m analysis.channels`` after
``python -m analysis.panel`` has written ``area_month_panel.parquet``.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import pandas as pd

from analysis.config import AREAS, PROCESSED_DATA_DIR, SITE_DATA_DIR
from analysis.io import as_int, round_significant, write_json_atomic


@dataclass(frozen=True)
class BinDriver:
    name: str
    column: str
    first_lag: int
    last_lag: int

    @property
    def window(self) -> str:
        return f"{self.first_lag}-{self.last_lag}"


BIN_DRIVERS: Final[list[BinDriver]] = [
    BinDriver("lice", "mobile_anom", 0, 3),
    BinDriver("temp", "dd_below14", 1, 3),
    BinDriver("feed", "feed_rate_anom", 1, 3),
    BinDriver("mortality", "mortality_anom", 0, 3),
]


def build_bins(panel: pd.DataFrame) -> list[dict[str, Any]]:
    """Mean count and weight anomalies over each driver's window, by tercile.

    Terciles are pooled across areas 1-13. An area-month counts only when the
    driver and both outcomes are present for every month of the window.
    """

    frame = panel.loc[panel["area"].isin(AREAS)].sort_values(["area", "month"]).copy()
    rows: list[dict[str, Any]] = []
    for driver in BIN_DRIVERS:
        if frame[driver.column].notna().sum() < 3:
            continue
        outcomes = {
            outcome: _forward_window_mean(frame, outcome, driver.first_lag, driver.last_lag)
            for outcome in ("count_anom", "weight_anom")
        }
        usable = frame[driver.column].notna()
        for values in outcomes.values():
            usable &= values.notna()
        terciles = pd.qcut(frame.loc[usable, driver.column], 3, labels=[1, 2, 3])
        for tercile in (1, 2, 3):
            members = terciles.index[terciles == tercile]
            rows.append(
                {
                    "driver": driver.name,
                    "tercile": tercile,
                    "window": driver.window,
                    "count_anom": round_significant(outcomes["count_anom"][members].mean()),
                    "weight_anom": round_significant(outcomes["weight_anom"][members].mean()),
                    "n": as_int(len(members)),
                }
            )
    return rows


def _forward_window_mean(
    frame: pd.DataFrame, column: str, first_lag: int, last_lag: int
) -> pd.Series:
    by_area = frame.groupby("area")[column]
    leads = [by_area.shift(-lag) for lag in range(first_lag, last_lag + 1)]
    stacked = pd.concat(leads, axis=1)
    return stacked.mean(axis=1).where(stacked.notna().all(axis=1))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--processed", type=Path, default=PROCESSED_DATA_DIR)
    parser.add_argument("--site", type=Path, default=SITE_DATA_DIR)
    args = parser.parse_args()

    panel = pd.read_parquet(args.processed / "area_month_panel.parquet")
    destination = args.site / "channels.json"
    existing = (
        json.loads(destination.read_text(encoding="utf-8")) if destination.exists() else {}
    )
    channels = {"bins": build_bins(panel)}
    if "panel" in existing:
        channels["panel"] = existing["panel"]
    write_json_atomic(channels, destination)
    for row in channels["bins"]:
        print(row)


if __name__ == "__main__":
    main()
