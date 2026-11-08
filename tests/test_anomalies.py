from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from analysis.anomalies import (
    _christmas_dummy,
    _easter_dummy,
    _fit_season,
    _seasonal_design,
    anomaly,
)


def _weekly_residual(values: pd.Series) -> pd.Series:
    logged = np.log(values)
    level = logged.shift(1).rolling(52, min_periods=39).mean()
    return logged - level


def test_weekly_anomaly_removes_linear_trend_and_annual_cycle() -> None:
    index = pd.date_range("2016-01-04", periods=520, freq="7D")
    t = np.arange(len(index), dtype=float)
    annual_angle = 2 * np.pi * (index + pd.Timedelta(days=3)).dayofyear / 365.25
    rng = np.random.default_rng(2026)
    log_values = (
        5.0
        + 0.002 * t
        + 0.45 * np.sin(annual_angle)
        - 0.2 * np.cos(annual_angle)
        + rng.normal(0, 0.015, len(index))
    )
    values = pd.Series(np.exp(log_values), index=index, name="synthetic")

    adjusted = anomaly(values, "W").dropna()
    elapsed = np.arange(len(adjusted), dtype=float)
    remaining_trend = np.polyfit(elapsed, adjusted.to_numpy(), deg=1)[0]
    seasonal_coefficients, *_ = np.linalg.lstsq(
        _seasonal_design(adjusted.index, freq="W", K=3),
        adjusted.to_numpy(),
        rcond=None,
    )

    assert abs(remaining_trend) < 0.0001
    assert np.max(np.abs(seasonal_coefficients[1:7])) < 1e-10
    assert adjusted.name == "synthetic"


def test_values_after_fit_end_do_not_change_fitted_season() -> None:
    index = pd.date_range("2018-01-01", periods=312, freq="7D")
    t = np.arange(len(index), dtype=float)
    values = pd.Series(
        np.exp(4 + 0.001 * t + 0.3 * np.sin(2 * np.pi * t / 52)),
        index=index,
    )
    fit_end = pd.Timestamp("2022-12-26")
    changed = values.copy()
    changed.loc[changed.index > fit_end] *= 50

    original_season = _fit_season(
        _weekly_residual(values),
        freq="W",
        fit_end=fit_end,
        K=3,
    )
    changed_season = _fit_season(
        _weekly_residual(changed),
        freq="W",
        fit_end=fit_end,
        K=3,
    )

    pd.testing.assert_series_equal(original_season, changed_season)


def test_weekly_holiday_dummies_follow_iso_weeks() -> None:
    index = pd.date_range("2024-03-18", "2025-01-06", freq="7D")
    easter_weeks = index[_easter_dummy(index, "W").astype(bool)]
    christmas_weeks = index[_christmas_dummy(index).astype(bool)]

    assert easter_weeks.tolist() == [
        pd.Timestamp("2024-03-25"),
        pd.Timestamp("2024-04-01"),
    ]
    assert christmas_weeks.tolist() == [
        pd.Timestamp("2024-12-23"),
        pd.Timestamp("2024-12-30"),
    ]


def test_monthly_anomaly_preserves_missing_observations() -> None:
    index = pd.date_range("2018-01-01", periods=72, freq="MS")
    values = pd.Series(np.exp(3 + np.arange(72) / 100), index=index)
    values.iloc[40] = np.nan

    adjusted = anomaly(values, "M")

    assert np.isnan(adjusted.iloc[40])


def test_rejects_an_irregular_weekly_grid() -> None:
    values = pd.Series(
        [1.0, 2.0, 3.0],
        index=pd.to_datetime(["2024-01-01", "2024-01-08", "2024-01-22"]),
    )

    with pytest.raises(ValueError, match="regular grid"):
        anomaly(values, "W")


def test_season_needs_three_rows_per_parameter() -> None:
    rng = np.random.default_rng(5)

    def monthly(periods: int) -> pd.Series:
        index = pd.date_range("2018-01-01", periods=periods, freq="MS")
        return pd.Series(np.exp(3 + rng.normal(0, 0.1, periods)), index=index)

    with pytest.raises(ValueError, match="need at least 24"):
        anomaly(monthly(30), "M")
    assert anomaly(monthly(40), "M").notna().sum() > 0
