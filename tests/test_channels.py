from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from analysis.channels import (
    build_bins,
    build_mechanism_panel,
    build_mechanism_sensitivity,
    lagged_design,
    missing_mechanism_columns,
    verdicts_by_test,
)


def _panel_with_lice_signature() -> pd.DataFrame:
    """High lice this month means more, smaller fish over the next 0-3 months."""

    rng = np.random.default_rng(3)
    months = pd.date_range("2018-01-01", periods=96, freq="MS").strftime("%Y-%m")
    frames = []
    for area in range(1, 14):
        lice = rng.normal(0, 1, len(months))
        pressure = pd.Series(lice).rolling(4, min_periods=1).mean().to_numpy()
        frames.append(
            pd.DataFrame(
                {
                    "area": area,
                    "month": months,
                    "mobile_anom": lice,
                    "count_anom": 0.1 * pressure + rng.normal(0, 0.01, len(months)),
                    "weight_anom": -0.05 * pressure + rng.normal(0, 0.01, len(months)),
                    "dd_below14": rng.normal(0, 1, len(months)),
                    "feed_rate_anom": rng.normal(0, 1, len(months)),
                    "mortality_anom": np.nan,
                }
            )
        )
    return pd.concat(frames, ignore_index=True)


def test_lice_terciles_show_more_but_smaller_fish() -> None:
    bins = build_bins(_panel_with_lice_signature())
    lice = {row["tercile"]: row for row in bins if row["driver"] == "lice"}

    assert lice[3]["count_anom"] > lice[1]["count_anom"]
    assert lice[3]["weight_anom"] < lice[1]["weight_anom"]
    assert lice[1]["window"] == "0-3"


def test_bins_match_contract_and_skip_missing_drivers() -> None:
    bins = build_bins(_panel_with_lice_signature())

    assert {row["driver"] for row in bins} == {"lice", "temp", "feed"}
    assert all(
        set(row) == {"driver", "tercile", "window", "count_anom", "weight_anom", "n"}
        for row in bins
    )
    assert {row["window"] for row in bins if row["driver"] == "temp"} == {"1-3"}
    json.dumps(bins, allow_nan=False)


def test_window_needs_every_month_present() -> None:
    panel = _panel_with_lice_signature()
    full_n = sum(row["n"] for row in build_bins(panel) if row["driver"] == "lice")
    panel.loc[(panel["area"] == 1) & (panel["month"] == "2020-06"), "count_anom"] = np.nan

    gappy_n = sum(row["n"] for row in build_bins(panel) if row["driver"] == "lice")

    assert gappy_n == pytest.approx(full_n - 4)


LICE_PER_LAG = 0.05
LICE_WEIGHT_PER_LAG = -0.03
GROWTH_PER_LAG = 0.02


def _mechanism_world(lice_weight_per_lag: float = LICE_WEIGHT_PER_LAG) -> pd.DataFrame:
    """Planted lice signature (lags 0-3) and growth effect (dd_below14, lags 1-3).

    Month-wide shocks and area x calendar-month effects are added so the fixed
    effects have something to absorb.
    """

    rng = np.random.default_rng(11)
    months = pd.date_range("2017-10-01", periods=108, freq="MS")
    month_shock = rng.normal(0, 0.3, len(months))
    frames = []
    for area in range(1, 14):
        season = rng.normal(0, 0.5, 12)[months.month - 1]
        lice = rng.normal(0, 1, len(months))
        below8 = rng.normal(0, 1, len(months))
        mid = rng.normal(0, 1, len(months))
        below14 = below8 + mid
        lice_pressure = pd.Series(lice).rolling(4, min_periods=4).sum().to_numpy()
        growth = pd.Series(below14).shift(1).rolling(3, min_periods=3).sum().to_numpy()
        frames.append(
            pd.DataFrame(
                {
                    "area": area,
                    "month": months.strftime("%Y-%m"),
                    "mobile_anom": lice,
                    "treat_anom": rng.normal(0, 1, len(months)),
                    "dd_below8": below8,
                    "dd_8to14": mid,
                    "dd_above14": rng.normal(0, 1, len(months)),
                    "dd_below14": below14,
                    "biomass_anom": rng.normal(0, 1, len(months)),
                    "fish_stock_anom": rng.normal(0, 1, len(months)),
                    "count_anom": LICE_PER_LAG * lice_pressure
                    + month_shock
                    + season
                    + rng.normal(0, 0.05, len(months)),
                    "weight_anom": lice_weight_per_lag * lice_pressure
                    + GROWTH_PER_LAG * growth
                    + month_shock
                    + season
                    + rng.normal(0, 0.05, len(months)),
                }
            )
        )
    return pd.concat(frames, ignore_index=True)


def _row(rows: list[dict], test: str, outcome: str, driver: str) -> dict:
    (match,) = [
        row
        for row in rows
        if (row["test"], row["outcome"], row["driver"]) == (test, outcome, driver)
    ]
    return match


def test_mechanism_panel_recovers_planted_effects_and_passes() -> None:
    rows = build_mechanism_panel(_mechanism_world())

    lice_count = _row(rows, "M1", "log_count", "mobile_lice")
    lice_weight = _row(rows, "M1", "log_avg_kg", "mobile_lice")
    growth = _row(rows, "M2", "log_avg_kg", "dd_below14")
    assert lice_count["coef_sum"] == pytest.approx(4 * LICE_PER_LAG, abs=0.02)
    assert lice_weight["coef_sum"] == pytest.approx(4 * LICE_WEIGHT_PER_LAG, abs=0.02)
    assert growth["coef_sum"] == pytest.approx(3 * GROWTH_PER_LAG, abs=0.02)
    assert lice_count["lo"] < lice_count["coef_sum"] < lice_count["hi"]
    assert verdicts_by_test(rows) == {"M1": True, "M2": True}


def test_m1_fails_when_weight_moves_the_wrong_way() -> None:
    rows = build_mechanism_panel(_mechanism_world(lice_weight_per_lag=0.03))

    assert _row(rows, "M1", "log_count", "mobile_lice")["pass"] is True
    assert _row(rows, "M1", "log_avg_kg", "mobile_lice")["pass"] is False
    assert verdicts_by_test(rows)["M1"] is False


def test_mechanism_rows_match_contract() -> None:
    rows = build_mechanism_panel(_mechanism_world())

    assert all(
        set(row) == {"test", "outcome", "driver", "lags", "coef_sum", "lo", "hi", "pass"}
        for row in rows
    )
    assert _row(rows, "M1", "log_count", "treatments")["pass"] is None
    assert _row(rows, "M2", "log_count", "dd_below14")["pass"] is None
    assert _row(rows, "M2", "log_avg_kg", "dd_below14")["lags"] == "1-3"
    json.dumps(rows, allow_nan=False)


def test_lags_stay_within_area_and_controls_use_t_minus_4() -> None:
    world = _mechanism_world()
    design = lagged_design(world, "count_anom", ("mobile_anom",))

    area2 = world.loc[world["area"] == 2].reset_index(drop=True)
    first = design.loc[2].iloc[0]
    assert first.name == pd.Timestamp(area2.loc[4, "month"])
    assert first["mobile_anom_l3"] == area2.loc[1, "mobile_anom"]
    assert first["biomass_anom_l4"] == area2.loc[0, "biomass_anom"]


def test_mechanism_panel_reports_missing_weekly_columns() -> None:
    world = _mechanism_world().drop(columns=["mobile_anom", "treat_anom"])

    assert missing_mechanism_columns(world) == ["mobile_anom", "treat_anom"]
    with pytest.raises(ValueError, match="mobile_anom"):
        build_mechanism_panel(world)


def test_sensitivity_drops_areas_1_and_13_and_carries_no_pass_mark() -> None:
    world = _mechanism_world()
    world.loc[world["area"].isin([1, 13]), "count_anom"] *= 50

    sensitivity = build_mechanism_sensitivity(world)

    assert sensitivity["excluded_areas"] == [1, 13]
    assert all(row["pass"] is None for row in sensitivity["rows"])
    lice_count = _row(sensitivity["rows"], "M1", "log_count", "mobile_lice")
    assert lice_count["coef_sum"] == pytest.approx(4 * LICE_PER_LAG, abs=0.02)
    json.dumps(sensitivity, allow_nan=False)
