from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from analysis.weekly_indices import build_weekly_indices


def _weekly_fixture(
    *,
    disease_available: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    farms = pd.DataFrame(
        [
            {"locality_no": 101, "area": 1, "capacity_t": 100.0},
            {"locality_no": 102, "area": 1, "capacity_t": 300.0},
        ]
    )
    rows: list[dict[str, object]] = []
    weeks = pd.date_range("2018-01-01", "2023-12-25", freq="7D")
    for week_start in weeks:
        iso = week_start.isocalendar()
        year_offset = iso.year - 2018
        for locality_no, mobile, treated, isa in (
            (101, 1.0, True, True),
            (102, 3.0, False, False),
        ):
            rows.append(
                {
                    "locality_no": locality_no,
                    "week": f"{iso.year}-W{iso.week:02d}",
                    "week_start": week_start,
                    "area": 1,
                    "reported": True,
                    "mobile": mobile,
                    "treated": treated,
                    "sea_temp_c": 10.0 + 0.1 * year_offset,
                    "isa": isa if disease_available else pd.NA,
                    "pd": False if disease_available else pd.NA,
                    "available_at": week_start + pd.Timedelta(days=13),
                }
            )
    return pd.DataFrame(rows), farms


def test_capacity_weighted_indices_and_reporting_counts() -> None:
    farm_week, farms = _weekly_fixture()

    area, national = build_weekly_indices(farm_week, farms)
    first_area = area.loc[
        (area["area"] == 1) & (area["week"] == "2018-W01")
    ].iloc[0]
    first_national = national.loc[national["week"] == "2018-W01"].iloc[0]

    assert first_area["mobile_idx"] == pytest.approx(2.5)
    assert first_area["treat_rate"] == pytest.approx(0.5)
    assert first_area["disease_share"] == pytest.approx(0.5)
    assert first_area["temp_c"] == pytest.approx(10.0)
    assert first_area["n_reporting"] == 2
    assert first_national["mobile_idx"] == pytest.approx(2.5)


def test_temperature_normal_uses_at_least_three_previous_years() -> None:
    farm_week, farms = _weekly_fixture()

    area, _ = build_weekly_indices(farm_week, farms)
    area_one = area.loc[area["area"] == 1].set_index("week")

    assert np.isnan(area_one.loc["2020-W20", "dd_anom"])
    assert area_one.loc["2021-W20", "dd_anom"] == pytest.approx(8.4)
    assert area_one.loc["2021-W20", "dd_8to14"] == pytest.approx(8.4)
    assert area_one.loc["2021-W20", "dd_below8"] == pytest.approx(0.0)
    assert area_one.loc["2021-W20", "dd_above14"] == pytest.approx(0.0)
    assert area_one.loc["2021-W20", "dd_below14"] == pytest.approx(8.4)


def test_anomalies_are_generated_on_regular_weekly_grid() -> None:
    farm_week, farms = _weekly_fixture()

    area, national = build_weekly_indices(farm_week, farms)
    area_one = area.loc[area["area"] == 1]

    assert area_one["mobile_anom"].notna().sum() > 200
    assert area_one["treat_anom"].notna().sum() > 200
    assert national["mobile_anom"].notna().sum() > 200


def test_disease_is_null_when_source_has_no_flags() -> None:
    farm_week, farms = _weekly_fixture(disease_available=False)

    area, national = build_weekly_indices(farm_week, farms)

    assert area["disease_share"].isna().all()
    assert national["disease_share"].isna().all()


def test_missing_capacity_uses_area_median() -> None:
    farm_week, farms = _weekly_fixture()
    farms.loc[farms["locality_no"] == 102, "capacity_t"] = np.nan

    area, _ = build_weekly_indices(farm_week, farms)
    first = area.loc[(area["area"] == 1) & (area["week"] == "2018-W01")].iloc[0]

    assert first["mobile_idx"] == pytest.approx(2.0)
