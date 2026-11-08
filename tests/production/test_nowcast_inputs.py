"""Publication timing and leakage tests use synthetic observations only."""

import numpy as np
import pandas as pd
import pytest

from analysis.drivers import build_directorate_driver_tables
from analysis.nowcast_inputs import NowcastInputs, build_targets, forecast_date, model_features
from analysis.panel import monthly_export_levels
from analysis.weekly_indices import build_weekly_indices


def test_vintage_ignores_target_outcomes_future_sources_and_stored_anomalies(
    directorate, weekly_area_index, ssb_weekly
):
    target = "2024-09"
    original = NowcastInputs(directorate, weekly_area_index, ssb_weekly).build_vintage(target)
    changed_d = directorate.copy()
    cols = ["harvest_kg", "harvest_count", "avg_kg", "biomass_kg", "fish_stock", "feed_kg", "dead", "smolt_released"]
    changed_d.loc[changed_d.month >= target, cols] *= 100
    changed_w = weekly_area_index.copy()
    changed_w.loc[changed_w.available_at > forecast_date(target), ["mobile_idx", "treat_rate", "temp_c", "disease_share"]] = 999
    # Poison every stored full-sample feature, including the temperature bands.
    for col in ["mobile_anom", "treat_anom", "dd_anom", "dd_below8", "dd_8to14", "dd_above14"]:
        changed_w[col] = 987654.0
    changed_s = ssb_weekly.copy()
    changed_s.loc[changed_s.available_at > forecast_date(target), "volume_t"] *= 100
    changed = NowcastInputs(changed_d, changed_w, changed_s).build_vintage(target)
    pd.testing.assert_frame_equal(original, changed)
    current = original.loc[original.is_target]
    assert current.filter(like="_label").isna().all().all()
    assert (current.feature_available_at <= current.made_on).all()
    assert current.drivers_ready.all()


def test_late_directorate_release_is_not_used(directorate, weekly_area_index, ssb_weekly):
    target = "2024-09"
    directorate.loc[(directorate.area == 3) & (directorate.month == "2024-08"), "available_at"] = forecast_date(target) + pd.Timedelta(days=1)
    result = NowcastInputs(directorate, weekly_area_index, ssb_weekly).build_vintage(target)
    row = result.loc[result.is_target & (result.area == 3)].iloc[0]
    assert np.isnan(row.biomass_anom_l1)
    assert not row.b0_ready
    assert not row.drivers_ready


def test_target_weeks_cannot_change_past_seasonal_adjustment(directorate, weekly_area_index, ssb_weekly):
    # 30 September is a Monday but its Thursday belongs to October.
    target = "2024-10"
    original = NowcastInputs(directorate, weekly_area_index, ssb_weekly).build_vintage(target)
    changed = weekly_area_index.copy()
    changed.loc[changed.week == "2024-W40", "mobile_idx"] *= 10
    modified = NowcastInputs(directorate, changed, ssb_weekly).build_vintage(target)
    past = ~original.is_target
    pd.testing.assert_series_equal(original.loc[past, "mobile_anom"], modified.loc[past, "mobile_anom"])
    assert not original.loc[~past, "mobile_anom"].equals(modified.loc[~past, "mobile_anom"])


def test_missing_directorate_month_does_not_shift_lags(directorate, weekly_area_index, ssb_weekly):
    directorate = directorate.loc[~((directorate.area == 1) & (directorate.month == "2024-08"))]
    result = NowcastInputs(directorate, weekly_area_index, ssb_weekly).build_vintage("2024-09")
    row = result.loc[result.is_target & (result.area == 1)].iloc[0]
    assert np.isnan(row.biomass_anom_l1)
    assert not row.b0_ready


def test_zero_harvest_has_no_log_target_and_areas_exclude_zero(directorate):
    targets = build_targets(directorate)
    zeros = targets.loc[targets.zero_harvest]
    assert len(zeros) == 3
    assert zeros[["log_kg", "log_count", "log_avg_kg"]].isna().all().all()
    assert not zeros.log_targets_valid.any()
    assert set(targets.area) == set(range(1, 14))


def test_missing_suppressed_area_never_makes_smaller_national_total(directorate):
    gappy = directorate.loc[~((directorate.area == 0) & (directorate.month == "2024-05"))]
    _, national = build_directorate_driver_tables(gappy)
    row = national.loc[national.month == "2024-05"].iloc[0]
    assert np.isnan(row.biomass_kg)
    assert np.isnan(row.feed_rate)


def test_export_missing_week_is_null_and_duplicate_week_is_error(ssb_weekly):
    gappy = ssb_weekly.loc[ssb_weekly.week != "2024-W10"]
    assert np.isnan(monthly_export_levels(gappy).loc["2024-03-01"])
    with pytest.raises(ValueError, match="duplicate weeks"):
        monthly_export_levels(pd.concat([ssb_weekly, ssb_weekly.iloc[[0]]]))


def test_no_reporting_keeps_missing_indices_and_dated_week():
    weeks = pd.date_range("2024-01-01", periods=3, freq="W-MON")
    farms = pd.DataFrame({"locality_no": [1], "area": [1], "capacity_t": [100.]})
    fw = pd.DataFrame({"locality_no": 1, "area": 1, "week_start": weeks,
                       "week": [f"{d.isocalendar().year}-W{d.isocalendar().week:02d}" for d in weeks],
                       "reported": [True, False, True], "mobile": [1., np.nan, 2.],
                       "treated": False, "sea_temp_c": 10., "isa": False, "pd": False,
                       "available_at": weeks + pd.Timedelta(days=13)})
    area, national = build_weekly_indices(fw, farms)
    for result in (area.loc[area.area == 1], national):
        row = result.loc[result.week == "2024-W02"].iloc[0]
        assert row.n_reporting == 0
        assert np.isnan(row.mobile_idx)
        assert np.isnan(row.treat_rate)
        assert row.available_at == pd.Timestamp("2024-01-21")


def test_disease_columns_dropped_only_when_unavailable():
    assert "disease_share" in model_features(True)["drivers"]
    assert not any(c.startswith("disease_share") for c in model_features(False)["drivers"])

