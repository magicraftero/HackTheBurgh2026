"""Count × weight channels: descriptive bins and the M1/M2 mechanism panel.

Run from the repository root with ``python -m analysis.channels`` after
``python -m analysis.panel`` has written ``area_month_panel.parquet``.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import numpy as np
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


PANEL_OUTCOMES: Final[dict[str, str]] = {"log_count": "count_anom", "log_avg_kg": "weight_anom"}
MODEL_REGRESSORS: Final[dict[str, tuple[str, ...]]] = {
    "M1": ("mobile_anom", "treat_anom", "dd_below8", "dd_8to14", "dd_above14"),
    "M2": ("dd_below14", "dd_above14"),
}
CONTROLS: Final = ("biomass_anom", "fish_stock_anom")
REGRESSOR_LAGS: Final = range(0, 4)
CONTROL_LAG: Final = 4
DRISCOLL_KRAAY_BANDWIDTH: Final = 12
Z_95: Final = 1.96


@dataclass(frozen=True)
class LagSum:
    test: str
    outcome: str
    driver: str
    column: str
    first_lag: int
    last_lag: int
    required_sign: int | None

    @property
    def lags(self) -> str:
        return f"{self.first_lag}-{self.last_lag}"


LAG_SUMS: Final[list[LagSum]] = [
    LagSum("M1", "log_count", "mobile_lice", "mobile_anom", 0, 3, +1),
    LagSum("M1", "log_avg_kg", "mobile_lice", "mobile_anom", 0, 3, -1),
    LagSum("M1", "log_count", "treatments", "treat_anom", 0, 3, None),
    LagSum("M1", "log_avg_kg", "treatments", "treat_anom", 0, 3, None),
    LagSum("M2", "log_avg_kg", "dd_below14", "dd_below14", 1, 3, +1),
    LagSum("M2", "log_count", "dd_below14", "dd_below14", 1, 3, None),
]


def missing_mechanism_columns(panel: pd.DataFrame) -> list[str]:
    needed = {
        *PANEL_OUTCOMES.values(),
        *CONTROLS,
        *(column for regressors in MODEL_REGRESSORS.values() for column in regressors),
    }
    return sorted(
        column for column in needed if column not in panel or panel[column].notna().sum() == 0
    )


def lagged_design(
    panel: pd.DataFrame,
    outcome_column: str,
    regressors: tuple[str, ...],
    areas: tuple[int, ...] | range = AREAS,
) -> pd.DataFrame:
    """Outcome, lagged regressors, t-4 controls and the area × calendar-month cell.

    Lags are taken within each area on a complete monthly grid, so a lag never
    crosses areas or skips a missing month. Incomplete rows are dropped.
    """

    frame = panel.loc[panel["area"].isin(areas)].sort_values(["area", "month"])
    month = pd.to_datetime(frame["month"], format="%Y-%m")
    for area, months in month.groupby(frame["area"]):
        expected = pd.date_range(months.iloc[0], months.iloc[-1], freq="MS")
        if len(expected) != len(months) or not (expected == months.to_numpy()).all():
            raise ValueError(f"Area {area} is not on a complete monthly grid.")

    by_area = frame.groupby("area")
    columns: dict[str, pd.Series] = {"y": frame[outcome_column]}
    for column in regressors:
        for lag in REGRESSOR_LAGS:
            columns[f"{column}_l{lag}"] = by_area[column].shift(lag)
    for column in CONTROLS:
        columns[f"{column}_l{CONTROL_LAG}"] = by_area[column].shift(CONTROL_LAG)
    design = pd.DataFrame(columns)
    design["season_cell"] = frame["area"].to_numpy() * 100 + month.dt.month.to_numpy()
    design.index = pd.MultiIndex.from_arrays(
        [frame["area"].to_numpy(), month.to_numpy()], names=["area", "month"]
    )
    return design.dropna()


def fit_mechanism_model(design: pd.DataFrame) -> Any:
    from linearmodels.panel import PanelOLS

    exog = design.drop(columns=["y", "season_cell"])
    model = PanelOLS(
        design["y"],
        exog,
        time_effects=True,
        other_effects=design[["season_cell"]],
        drop_absorbed=True,
    )
    return model.fit(cov_type="kernel", kernel="bartlett", bandwidth=DRISCOLL_KRAAY_BANDWIDTH)


def lag_sum(result: Any, column: str, first_lag: int, last_lag: int) -> tuple[float, float]:
    """Sum of lag coefficients and its standard error, sqrt(1' V 1)."""

    names = [f"{column}_l{lag}" for lag in range(first_lag, last_lag + 1)]
    missing = [name for name in names if name not in result.params.index]
    if missing:
        return math.nan, math.nan
    total = float(result.params[names].sum())
    variance = float(result.cov.loc[names, names].to_numpy().sum())
    return total, math.sqrt(variance) if variance >= 0 else math.nan


def build_mechanism_panel(
    panel: pd.DataFrame, areas: tuple[int, ...] | range = AREAS
) -> list[dict[str, Any]]:
    """Rows for ``channels.json`` → ``panel``, following prereg/PASS_MARKS.md."""

    missing = missing_mechanism_columns(panel)
    if missing:
        raise ValueError(f"Mechanism panel needs columns that are absent or empty: {missing}")

    fits: dict[tuple[str, str], Any] = {}
    rows: list[dict[str, Any]] = []
    for tested in LAG_SUMS:
        key = (tested.test, tested.outcome)
        if key not in fits:
            design = lagged_design(
                panel, PANEL_OUTCOMES[tested.outcome], MODEL_REGRESSORS[tested.test], areas
            )
            fits[key] = fit_mechanism_model(design)
        total, se = lag_sum(fits[key], tested.column, tested.first_lag, tested.last_lag)
        lo, hi = total - Z_95 * se, total + Z_95 * se
        rows.append(
            {
                "test": tested.test,
                "outcome": tested.outcome,
                "driver": tested.driver,
                "lags": tested.lags,
                "coef_sum": round_significant(total),
                "lo": round_significant(lo),
                "hi": round_significant(hi),
                "pass": _passes(tested.required_sign, lo, hi),
            }
        )
    return rows


SENSITIVITY_EXCLUDED_AREAS: Final = (1, 13)
SENSITIVITY_LABEL: Final = (
    "Sensitivity check, not a pass mark: areas 1 and 13 excluded because their many "
    "zero-harvest months give extreme count anomalies. Chosen before any M1/M2 results."
)


def build_mechanism_sensitivity(panel: pd.DataFrame) -> dict[str, Any]:
    """The same M1/M2 sums without areas 1 and 13, for RESULTS.md only."""

    areas = tuple(area for area in AREAS if area not in SENSITIVITY_EXCLUDED_AREAS)
    rows = [{**row, "pass": None} for row in build_mechanism_panel(panel, areas)]
    return {
        "label": SENSITIVITY_LABEL,
        "excluded_areas": list(SENSITIVITY_EXCLUDED_AREAS),
        "rows": rows,
    }


def _passes(required_sign: int | None, lo: float, hi: float) -> bool | None:
    if required_sign is None:
        return None
    if not (np.isfinite(lo) and np.isfinite(hi)):
        return False
    return bool(lo > 0) if required_sign > 0 else bool(hi < 0)


def verdicts_by_test(rows: list[dict[str, Any]]) -> dict[str, bool]:
    """A test passes only if every one of its rows with a pass mark passes."""

    verdicts: dict[str, bool] = {}
    for row in rows:
        if row["pass"] is None:
            continue
        verdicts[row["test"]] = verdicts.get(row["test"], True) and row["pass"]
    return verdicts


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
    channels: dict[str, Any] = {"bins": build_bins(panel)}
    missing = missing_mechanism_columns(panel)
    if missing:
        print(f"Skipping M1/M2: panel lacks {missing}; keeping any existing panel rows.")
        if "panel" in existing:
            channels["panel"] = existing["panel"]
    else:
        channels["panel"] = build_mechanism_panel(panel)
        sensitivity = build_mechanism_sensitivity(panel)
        write_json_atomic(sensitivity, args.processed / "mechanism_sensitivity.json")
        for row in sensitivity["rows"]:
            print("sensitivity:", row)
    write_json_atomic(channels, destination)
    for row in channels["bins"]:
        print(row)
    for row in channels.get("panel", []):
        print(row)
    if "panel" in channels:
        print("Verdicts:", verdicts_by_test(channels["panel"]))


if __name__ == "__main__":
    main()
