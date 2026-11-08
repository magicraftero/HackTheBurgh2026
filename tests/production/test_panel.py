from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from analysis.io import round_significant
from analysis.panel import (
    WEEKLY_COLUMNS,
    area_month_records,
    build_production_tables,
    monthly_export_volume,
    week_month,
)
ZERO_HARVEST_COUNT = 3  # area 5's zero-harvest months in conftest.py

AREA_MONTH_KEYS = {
    "area",
    "month",
    "kg",
    "count",
    "avg_kg",
    "volume_anom",
    "count_anom",
    "weight_anom",
    "mobile_idx",
    "dd_anom",
    "feed_rate_anom",
    "mortality_anom",
}


def test_week_belongs_to_month_containing_its_thursday() -> None:
    mondays = pd.Series(pd.to_datetime(["2024-09-23", "2024-09-30"]))

    assert week_month(mondays).tolist() == ["2024-09", "2024-10"]


def test_export_volume_sums_complete_months_only(ssb_weekly: pd.DataFrame) -> None:
    september_2024 = ssb_weekly.loc[
        week_month(ssb_weekly["week_start"]) == "2024-09", "volume_t"
    ]
    gappy = ssb_weekly.loc[ssb_weekly["week"] != "2023-W10"]

    complete = monthly_export_volume(ssb_weekly).set_index("month")
    incomplete = monthly_export_volume(gappy).set_index("month")

    assert complete.loc["2024-09", "export_vol"] == pytest.approx(september_2024.sum())
    assert np.isnan(incomplete.loc["2023-03", "export_vol"])
    assert complete["export_vol_anom"].notna().sum() > 100


def test_panel_ships_without_weekly_indices(
    directorate: pd.DataFrame, ssb_weekly: pd.DataFrame
) -> None:
    tables = build_production_tables(directorate, ssb_weekly)
    panel = tables.area_month_panel

    assert len(panel) == 13 * 108
    assert sorted(panel["area"].unique()) == list(range(1, 14))
    assert panel[WEEKLY_COLUMNS].isna().all().all()
    assert panel["count_anom"].notna().sum() > 1000
    assert any("Weekly farm indices not available" in note for note in tables.notes)
    assert any(
        note.startswith(f"{ZERO_HARVEST_COUNT} area-months have zero harvest")
        for note in tables.notes
    )
    assert "export_vol_anom" in tables.drivers_national_month.columns


def test_weekly_values_are_averaged_into_months(
    directorate: pd.DataFrame,
    ssb_weekly: pd.DataFrame,
    weekly_area_index: pd.DataFrame,
    weekly_national_index: pd.DataFrame,
) -> None:
    tables = build_production_tables(
        directorate, ssb_weekly, weekly_area_index, weekly_national_index
    )
    weeks = weekly_area_index.loc[weekly_area_index["area"] == 3].copy()
    weeks["week_start"] = pd.to_datetime(
        [pd.Timestamp.fromisocalendar(int(w[:4]), int(w[6:]), 1) for w in weeks["week"]]
    )
    october = weeks.loc[week_month(weeks["week_start"]) == "2024-10"]
    row = tables.drivers_area_month.set_index(["area", "month"]).loc[(3, "2024-10")]

    assert row["mobile_idx"] == pytest.approx(october["mobile_idx"].mean())
    assert row["available_at_bw"] == october["available_at"].max()
    assert tables.drivers_national_month["mobile_idx"].notna().sum() > 100


def test_area_month_json_matches_contract(
    directorate: pd.DataFrame, ssb_weekly: pd.DataFrame
) -> None:
    records = area_month_records(build_production_tables(directorate, ssb_weekly).area_month_panel)

    assert len(records) == 13 * 108
    assert all(set(record) == AREA_MONTH_KEYS for record in records)
    assert isinstance(records[0]["area"], int)
    zero_harvest = [r for r in records if r["area"] == 5 and r["month"] == "2019-02"]
    assert zero_harvest[0]["avg_kg"] is None
    json.dumps(records, allow_nan=False)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (17_712_345.0, 17_710_000),
        (4.3149, 4.315),
        (-0.0123456, -0.01235),
        (0.0, 0),
        (float("nan"), None),
        (None, None),
    ],
)
def test_round_significant(value: float | None, expected: float | None) -> None:
    assert round_significant(value) == expected
