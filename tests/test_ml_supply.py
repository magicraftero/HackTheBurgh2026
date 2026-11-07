from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from analysis.nowcast import PreparedInputs, build_vintage, model_features, nowcast_month
from ml.supply import feature_sets, forecast, target_months, window_of
from ml.vintage import build_horizon_vintage, issue_date

World = tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]
MODELS = ["seasonal", "b0", "b1", "drivers", "ml", "blend"]


def test_issue_dates_and_windows() -> None:
    target = pd.Period("2024-06", "M")
    assert issue_date(target, 0) == pd.Timestamp("2024-07-10")
    assert issue_date(target, 3) == pd.Timestamp("2024-04-10")
    assert window_of("2020-12") == "warmup"
    assert window_of("2021-01") == "dev"
    assert window_of("2025-01") == "holdout"
    assert str(target_months(final=False)[-1]) == "2024-12"
    assert str(target_months(final=True)[-1]) == "2026-09"


def test_h0_panel_and_linear_models_match_production(nowcast_world: World) -> None:
    prepared = PreparedInputs(*nowcast_world)
    target = pd.Period("2023-06", "M")
    ours = build_horizon_vintage(prepared, target, 0)
    theirs = build_vintage(prepared, target)
    for column in theirs.columns.drop("date"):
        np.testing.assert_allclose(ours[column].astype(float), theirs[column].astype(float), atol=1e-12)

    features = model_features(prepared.include_disease)
    expected = nowcast_month(theirs, target, features, features["drivers"])
    result = forecast(prepared, target, 0)
    for model in ("b0", "b1", "drivers"):
        np.testing.assert_allclose(result[model], expected[model], atol=1e-9)


@pytest.mark.parametrize("h", [0, 2])
def test_forecast_ignores_everything_not_yet_public(nowcast_world: World, h: int) -> None:
    directorate, weekly, ssb = nowcast_world
    target = pd.Period("2023-06", "M")
    made_on = issue_date(target, h)
    first_unknown = str(target - h)

    original = forecast(PreparedInputs(directorate, weekly, ssb), target, h)

    future_directorate = directorate.copy()
    later = future_directorate["month"] >= first_unknown
    future_directorate.loc[later, ["harvest_count", "harvest_kg", "biomass_kg", "feed_kg", "dead"]] *= 3
    future_weekly = weekly.copy()
    future_weekly.loc[future_weekly["available_at"] > made_on, ["mobile_idx", "temp_c"]] *= 5
    future_ssb = ssb.copy()
    future_ssb.loc[future_ssb["available_at"] > made_on, "volume_t"] *= 5
    changed = forecast(PreparedInputs(future_directorate, future_weekly, future_ssb), target, h)

    for model in MODELS:
        np.testing.assert_allclose(original[model], changed[model], atol=1e-9)
    assert original["ml"].notna().all()


def test_horizon_features_are_shifted_to_what_was_known(nowcast_world: World) -> None:
    prepared = PreparedInputs(*nowcast_world)
    target = pd.Period("2023-06", "M")
    panel = build_horizon_vintage(prepared, target, 2)
    row = panel.loc[(panel["area"] == 3) & (panel["date"] == target.to_timestamp())].iloc[0]
    known = panel.loc[(panel["area"] == 3) & (panel["date"] <= pd.Timestamp("2023-03-01"))]
    # Directorate months after M = T - 3 are unknown on D, so the target's own outcome is too.
    assert np.isnan(row["log_kg_anom"])
    assert known["log_kg_anom"].notna().iloc[-1]
    assert panel.loc[(panel["area"] == 3) & (panel["date"] == pd.Timestamp("2023-04-01")), "log_kg_anom"].isna().all()
    assert np.isfinite(row["biomass_anom_l1"]) and np.isfinite(row["log_kg_base"])


def test_ml_is_reproducible_and_why_adds_up_for_linear(nowcast_world: World) -> None:
    prepared = PreparedInputs(*nowcast_world)
    target = pd.Period("2023-06", "M")
    first = forecast(prepared, target, 1)
    second = forecast(prepared, target, 1)
    np.testing.assert_array_equal(first["ml"].to_numpy(), second["ml"].to_numpy())
    np.testing.assert_allclose(first["blend"], (first["drivers"] + first["ml"]) / 2)

    lice = first.loc[first["outcome"] == "log_kg", "why_drivers_lice"]
    assert lice.notna().all()
    assert set(feature_sets(False)["ml"]) >= set(feature_sets(False)["drivers"])


def test_no_forecast_when_the_season_has_too_few_months(nowcast_world: World) -> None:
    directorate, weekly, ssb = nowcast_world
    sparse = directorate.copy()
    # Area 4 harvests only every third month, so its season has too few usable months.
    months = pd.to_datetime(sparse["month"] + "-01")
    sparse.loc[(sparse["area"] == 4) & (months.dt.month % 3 != 0), ["harvest_count", "harvest_kg"]] = 0
    sparse.loc[(sparse["area"] == 4) & (months.dt.month % 3 != 0), "avg_kg"] = np.nan
    result = forecast(PreparedInputs(sparse, weekly, ssb), pd.Period("2021-06", "M"), 0)
    kg = result.loc[result["outcome"] == "log_kg"].set_index("area")
    assert kg.loc[4, MODELS].isna().all()
    assert kg.drop(index=4)["drivers"].notna().all()


def test_lever_grids_sweep_each_lever(nowcast_world: World) -> None:
    from ml.supply import lever_grids

    prepared = PreparedInputs(*nowcast_world)
    grids = lever_grids(prepared, pd.Period("2023-06", "M"), pd.Timestamp("2023-07-10"))
    area = next(a for a in grids["areas"] if a["area"] == 3)
    lice = next(lever for lever in area["levers"] if lever["id"] == "lice")
    assert len(lice["grid"]) == 9 and lice["grid"][0] < lice["grid"][-1]
    for model in ("ml", "blend"):
        assert set(lice["delta_log"][model]) == {"log_kg", "log_count", "log_avg_kg"}
        assert all(np.isfinite(lice["delta_log"][model]["log_kg"]))
    # The synthetic world raises harvest with lice, so the blend's kg response rises across the grid.
    kg = lice["delta_log"]["blend"]["log_kg"]
    assert kg[-1] > kg[0]
