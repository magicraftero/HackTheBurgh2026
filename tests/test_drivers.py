from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from analysis.drivers import build_directorate_driver_tables


def _directorate_fixture(periods: int = 120) -> pd.DataFrame:
    months = pd.date_range("2017-01-01", periods=periods, freq="MS")
    rows: list[dict[str, float | int | str]] = []
    for area in range(14):
        scale = area + 1
        for position, month in enumerate(months):
            rows.append(
                {
                    "area": area,
                    "month": month.strftime("%Y-%m"),
                    "biomass_kg": scale * (1_000_000 + 1_000 * position),
                    "fish_stock": scale * (200_000 + 100 * position),
                    "smolt_released": scale * (10_000 + position),
                    "feed_kg": scale**2 * (100_000 + 100 * position),
                    "dead": scale**2 * (1_000 + position),
                }
            )
    return pd.DataFrame(rows)


def test_builds_area_and_national_driver_tables() -> None:
    source = _directorate_fixture()

    area, national = build_directorate_driver_tables(source)

    assert len(area) == 13 * 120
    assert area["area"].drop_duplicates().tolist() == list(range(1, 14))
    assert len(national) == 120
    assert set(
        [
            "biomass_anom",
            "fish_stock_anom",
            "smolt_pipe_anom",
            "feed_rate_anom",
            "mortality_anom",
        ]
    ).issubset(area.columns)


def test_smolt_pipeline_uses_months_23_through_12_before_target() -> None:
    source = _directorate_fixture()

    area, _ = build_directorate_driver_tables(source)
    area_one = area.loc[area["area"] == 1].reset_index(drop=True)
    expected = np.log1p(
        source.loc[
            (source["area"] == 1)
            & source["month"].between("2017-01", "2017-12"),
            "smolt_released",
        ].sum()
    )

    assert np.isnan(area_one.loc[22, "smolt_pipe"])
    assert area_one.loc[23, "smolt_pipe"] == pytest.approx(expected)


def test_national_rates_are_ratios_of_sums() -> None:
    source = _directorate_fixture()

    _, national = build_directorate_driver_tables(source)
    first_month = source.loc[source["month"] == "2017-01"]
    expected_feed_rate = (
        first_month["feed_kg"].sum() / first_month["biomass_kg"].sum()
    )
    mean_area_rate = (first_month["feed_kg"] / first_month["biomass_kg"]).mean()

    assert national.loc[0, "feed_rate"] == pytest.approx(expected_feed_rate)
    assert national.loc[0, "feed_rate"] != pytest.approx(mean_area_rate)


def test_release_date_is_twentieth_of_following_month() -> None:
    area, _ = build_directorate_driver_tables(_directorate_fixture())

    first = area.loc[(area["area"] == 1) & (area["month"] == "2017-01")].iloc[0]

    assert first["available_at_dir"] == pd.Timestamp("2017-02-20")


def test_rejects_missing_production_area() -> None:
    source = _directorate_fixture()
    source = source.loc[source["area"] != 13]

    with pytest.raises(ValueError, match="missing production areas: 13"):
        build_directorate_driver_tables(source)
