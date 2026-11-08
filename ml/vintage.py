"""As-of feature panels for production forecasts h = 0..3 months ahead.

A horizon-h forecast of target month T is issued on D = the 10th of month
T - h + 1, when the latest Directorate month is M = T - h - 1. The panel is the
h = 0 nowcast panel of ``analysis.nowcast.build_vintage`` built with what was
public on D, shifted by h. A ``_l1`` column is therefore always shift(h + 1)
and a bare column shift(h), and the feature names (and the B0, B1 and Drivers
feature sets) are Production's. At h = 0 the panel equals Production's.

The outcome base for horizon h is the trailing level at T - h (known on D)
plus the season at T, so ``y = base + anom`` and the model predicts ``anom``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from analysis.config import AREAS
from analysis.drivers import add_directorate_levels
from analysis.nowcast import (
    DIRECTORATE_FEATURES,
    OUTCOMES,
    WEEKLY_FEATURES,
    PreparedInputs,
    _components,
    _monthly_weekly_features,
    forecast_date,
)
from analysis.panel import monthly_export_levels

LAGGED_OUTCOMES = [f"{outcome}_anom_{lag}" for outcome in OUTCOMES for lag in ("m", "m1", "y")]
ML_EXTRA_FEATURES = [*LAGGED_OUTCOMES, "log_avg_kg_level_m", "temp_c", "moy_sin", "moy_cos"]
LEVEL_FEATURES = ("temp_c", "log_avg_kg_level_m", "disease_share", "disease_share_l1")
# The season has 8 parameters. With fewer usable months it explodes (area 1 in
# 2021: season terms of -1884 log points), so no forecast until it has 24.
MIN_SEASON_MONTHS = 24


def issue_date(target: pd.Period, h: int) -> pd.Timestamp:
    """D for a horizon-h forecast of ``target``: the nowcast date of T - h."""

    return forecast_date(target - h)


def build_horizon_vintage(
    prepared: PreparedInputs,
    target: pd.Period,
    h: int,
    made_on: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Every area-month up to ``target`` as it looked on the issue date.

    ``made_on`` defaults to D; a live outlook passes an earlier date (today).
    """

    if h < 0:
        raise ValueError("h must be 0 or more")
    issued = issue_date(target, h)
    made_on = issued if made_on is None else min(pd.Timestamp(made_on), issued)
    known_period = target - h - 1
    last_known = known_period.to_timestamp()
    weekly_fit_end = known_period.to_timestamp(how="end").normalize()
    grid = pd.date_range(prepared.first_month, target.to_timestamp(), freq="MS")

    public_ssb = prepared.ssb.loc[prepared.ssb["available_at"] <= made_on]
    export = monthly_export_levels(public_ssb).reindex(grid)
    export_anom = _components(export, "M", "log", last_known)["anomaly"]
    angle = 2 * np.pi * (grid.month - 1) / 12

    frames = []
    for area in AREAS:
        full = prepared.directorate[area].reindex(grid)
        known = full.copy()
        known.loc[known.index > last_known] = np.nan
        levels = add_directorate_levels(known)

        frame = pd.DataFrame(index=grid)
        for level, name, transform in DIRECTORATE_FEATURES:
            parts = _components(levels[level], "M", transform, last_known)
            frame[f"{name}_l1"] = parts["anomaly"].shift(h + 1)
        frame["export_vol_anom"] = export_anom.shift(h)
        area_weekly = prepared.weekly.get(area)
        weekly = _monthly_weekly_features(area_weekly, made_on, weekly_fit_end, grid)
        for column in WEEKLY_FEATURES:
            frame[column] = weekly[column].shift(h)
            frame[f"{column}_l1"] = weekly[column].shift(h + 1)
        frame["temp_c"] = _monthly_temperature(area_weekly, made_on, grid).shift(h)

        for outcome, column in OUTCOMES.items():
            parts = _components(known[column], "M", "log", last_known)
            base = parts["level"].shift(h) + parts["season"]
            if season_months(parts, last_known) < MIN_SEASON_MONTHS:
                base[:] = np.nan
            frame[f"{outcome}_anom"] = parts["y"] - base
            frame[f"{outcome}_base"] = base
            frame[f"{outcome}_actual"] = np.log(full[column].where(full[column] > 0))
            frame[f"{outcome}_anom_m"] = parts["anomaly"].shift(h + 1)
            frame[f"{outcome}_anom_m1"] = parts["anomaly"].shift(h + 2)
            frame[f"{outcome}_anom_y"] = parts["anomaly"].shift(12)
        frame["log_avg_kg_level_m"] = np.log(known["avg_kg"].where(known["avg_kg"] > 0)).shift(h + 1)
        frame["moy_sin"] = np.sin(angle)
        frame["moy_cos"] = np.cos(angle)
        frame.insert(0, "area", area)
        frame.insert(1, "date", grid)
        frames.append(frame.reset_index(drop=True))
    return pd.concat(frames, ignore_index=True)


def season_months(parts: pd.DataFrame, last_known: pd.Timestamp) -> int:
    """Usable months behind the fitted season: level and value both known."""

    residual = (parts["y"] - parts["level"]).loc[parts.index <= last_known]
    return int(residual.notna().sum())


def _monthly_temperature(
    weekly: pd.DataFrame | None, made_on: pd.Timestamp, grid: pd.DatetimeIndex
) -> pd.Series:
    """Mean sea temperature per month, from weeks public by ``made_on``."""

    if weekly is None:
        return pd.Series(np.nan, index=grid)
    public = weekly.loc[(weekly.index <= made_on) & (weekly["available_at"] <= made_on), "temp_c"]
    month = (public.index + pd.Timedelta(days=3)).to_period("M").to_timestamp()
    return public.groupby(month).mean().reindex(grid)
