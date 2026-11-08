"""Leakage-safe level and seasonality adjustment.

The public :func:`anomaly` function implements the definition fixed in
``docs/plans/00-shared.md``. Forecasting callers must pass ``fit_end`` so that
seasonal coefficients are estimated only from information available then.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Literal

import numpy as np
import pandas as pd
from dateutil.easter import easter

Frequency = Literal["W", "M"]
Transform = Literal["log", "log1p", "none"]

_WINDOWS: dict[Frequency, int] = {"W": 52, "M": 12}
_MINIMUM_COVERAGE = 0.75
_MIN_ROWS_PER_SEASON_PARAMETER = 3


def anomaly(
    x: pd.Series,
    freq: Frequency,
    transform: Transform = "log",
    fit_end: pd.Timestamp | None = None,
    K: int = 3,
) -> pd.Series:
    """Return a trailing-level and seasonally adjusted series.

    Parameters
    ----------
    x:
        Values on a regular ``DatetimeIndex``. Weekly observations must be
        Mondays and monthly observations must be the first of the month.
        Missing periods must be present as ``NaN`` rows.
    freq:
        ``"W"`` for weekly data or ``"M"`` for monthly data.
    transform:
        Transformation applied before adjustment.
    fit_end:
        Last date allowed when fitting the seasonal regression. The fitted
        season is evaluated for the entire index.
    K:
        Number of annual Fourier harmonics.
    """

    result = decompose(x, freq, transform, fit_end, K)["anomaly"]
    result.name = x.name
    return result


def decompose(
    x: pd.Series,
    freq: Frequency,
    transform: Transform = "log",
    fit_end: pd.Timestamp | None = None,
    K: int = 3,
) -> pd.DataFrame:
    """Split ``transform(x)`` into level, season and anomaly.

    Returns columns ``y``, ``level``, ``season`` and ``anomaly``, where
    ``y = level + season + anomaly``. A forecast of the anomaly at t becomes a
    forecast of ``y`` by adding back ``level + season``, both of which are
    known before t when the series ends at t - 1 and ``fit_end`` is t - 1.
    """

    _validate_inputs(x, freq, transform, fit_end, K)

    y = apply_transform(x.astype(float), transform)
    window = _WINDOWS[freq]
    minimum_periods = int(np.ceil(window * _MINIMUM_COVERAGE))
    level = y.shift(1).rolling(window=window, min_periods=minimum_periods).mean()
    residual = y - level
    season = _fit_season(residual, freq=freq, fit_end=fit_end, K=K)
    return pd.DataFrame(
        {"y": y, "level": level, "season": season, "anomaly": residual - season},
        index=x.index,
    )


def apply_transform(x: pd.Series, transform: Transform) -> pd.Series:
    """Apply a transform while converting values outside its domain to NaN."""

    if transform == "none":
        return x.replace([np.inf, -np.inf], np.nan)
    if transform == "log":
        return np.log(x.where(x > 0))
    return np.log1p(x.where(x > -1))


def _fit_season(
    residual: pd.Series,
    *,
    freq: Frequency,
    fit_end: pd.Timestamp | None,
    K: int,
) -> pd.Series:
    """Fit the registered seasonal model and return its fitted component."""

    design = _seasonal_design(residual.index, freq=freq, K=K)
    fit_mask = residual.notna()
    if fit_end is not None:
        fit_mask &= residual.index <= pd.Timestamp(fit_end)

    needed = _MIN_ROWS_PER_SEASON_PARAMETER * design.shape[1]
    if int(fit_mask.sum()) < needed:
        raise ValueError(
            "Not enough usable observations to fit seasonality: "
            f"need at least {needed}, found {int(fit_mask.sum())}."
        )

    coefficients, *_ = np.linalg.lstsq(
        design[fit_mask.to_numpy()],
        residual.loc[fit_mask].to_numpy(dtype=float),
        rcond=None,
    )
    return pd.Series(design @ coefficients, index=residual.index, dtype=float)


def _seasonal_design(
    index: pd.DatetimeIndex,
    *,
    freq: Frequency,
    K: int,
) -> np.ndarray:
    anchor_dates = _anchor_dates(index, freq)
    day_of_year = np.fromiter(
        (anchor.dayofyear for anchor in anchor_dates),
        dtype=float,
        count=len(anchor_dates),
    )

    columns: list[np.ndarray] = [np.ones(len(index), dtype=float)]
    for harmonic in range(1, K + 1):
        angle = 2 * np.pi * harmonic * day_of_year / 365.25
        columns.extend((np.sin(angle), np.cos(angle)))

    columns.append(_easter_dummy(index, freq))
    if freq == "W":
        columns.append(_christmas_dummy(index))
    return np.column_stack(columns)


def _anchor_dates(index: pd.DatetimeIndex, freq: Frequency) -> pd.DatetimeIndex:
    if freq == "W":
        return index + pd.Timedelta(days=3)
    return pd.DatetimeIndex(
        [timestamp.replace(day=15) for timestamp in index],
        name=index.name,
    )


def _easter_dummy(index: pd.DatetimeIndex, freq: Frequency) -> np.ndarray:
    values = np.zeros(len(index), dtype=float)
    for position, timestamp in enumerate(index):
        easter_sunday = easter(timestamp.year)
        if freq == "M":
            values[position] = float(
                timestamp.year == easter_sunday.year
                and timestamp.month == easter_sunday.month
            )
            continue

        week_start = timestamp.date()
        week_end = week_start + timedelta(days=6)
        good_friday = easter_sunday - timedelta(days=2)
        easter_monday = easter_sunday + timedelta(days=1)
        values[position] = float(
            week_start <= good_friday <= week_end
            or week_start <= easter_monday <= week_end
        )
    return values


def _christmas_dummy(index: pd.DatetimeIndex) -> np.ndarray:
    values = np.zeros(len(index), dtype=float)
    for position, timestamp in enumerate(index):
        week_start = timestamp.date()
        week_end = week_start + timedelta(days=6)
        candidate_years = range(week_start.year - 1, week_end.year + 1)
        values[position] = float(
            any(
                _intervals_overlap(
                    week_start,
                    week_end,
                    date(year, 12, 24),
                    date(year + 1, 1, 1),
                )
                for year in candidate_years
            )
        )
    return values


def _intervals_overlap(
    left_start: date,
    left_end: date,
    right_start: date,
    right_end: date,
) -> bool:
    return left_start <= right_end and right_start <= left_end


def _validate_inputs(
    x: pd.Series,
    freq: str,
    transform: str,
    fit_end: pd.Timestamp | None,
    K: int,
) -> None:
    if not isinstance(x, pd.Series):
        raise TypeError("x must be a pandas Series.")
    if not isinstance(x.index, pd.DatetimeIndex):
        raise TypeError("x must use a DatetimeIndex.")
    if freq not in _WINDOWS:
        raise ValueError("freq must be 'W' or 'M'.")
    if transform not in {"log", "log1p", "none"}:
        raise ValueError("transform must be 'log', 'log1p', or 'none'.")
    if not isinstance(K, int) or K < 1:
        raise ValueError("K must be a positive integer.")
    if x.empty:
        raise ValueError("x must contain at least one observation.")
    if not x.index.is_monotonic_increasing or not x.index.is_unique:
        raise ValueError("x must have a sorted, unique index.")
    if fit_end is not None and pd.isna(pd.Timestamp(fit_end)):
        raise ValueError("fit_end must be a valid timestamp.")

    if freq == "W":
        if not bool((x.index.dayofweek == 0).all()):
            raise ValueError("Weekly observations must be indexed by Monday.")
        if len(x.index) > 1 and not bool(
            (x.index.to_series().diff().iloc[1:] == pd.Timedelta(days=7)).all()
        ):
            raise ValueError("Weekly observations must be on a regular grid.")
        return

    if not bool((x.index.day == 1).all()):
        raise ValueError("Monthly observations must be indexed by month start.")
    if len(x.index) > 1:
        periods = x.index.to_period("M").astype(int)
        if not bool((np.diff(periods) == 1).all()):
            raise ValueError("Monthly observations must be on a regular grid.")
