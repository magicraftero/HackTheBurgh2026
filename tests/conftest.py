from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

ZERO_HARVEST_MONTHS = ("2019-02", "2019-03", "2022-07")


@pytest.fixture
def directorate() -> pd.DataFrame:
    """Contract-shaped Directorate table, Oct 2017 - Sep 2026, areas 0-13."""

    rng = np.random.default_rng(7)
    months = pd.date_range("2017-10-01", "2026-09-01", freq="MS")
    rows: list[dict[str, object]] = []
    for area in range(14):
        scale = area + 1
        for position, month in enumerate(months):
            season = 1 + 0.3 * np.sin(2 * np.pi * month.month / 12)
            label = month.strftime("%Y-%m")
            count = int(scale * 300_000 * season * rng.uniform(0.8, 1.2))
            if area == 5 and label in ZERO_HARVEST_MONTHS:
                count = 0
            avg_kg = 4.5 + 0.4 * np.cos(2 * np.pi * month.month / 12)
            harvest_kg = count * avg_kg
            rows.append(
                {
                    "area": area,
                    "month": label,
                    "harvest_count": count,
                    "harvest_kg": float(harvest_kg),
                    "avg_kg": harvest_kg / count if count else np.nan,
                    "biomass_kg": float(scale * (1e7 + 1e4 * position) * season),
                    "fish_stock": int(scale * (2e6 + 1e3 * position)),
                    "smolt_released": int(scale * 1e5 * rng.uniform(0.5, 1.5)),
                    "dead": int(scale * 2e4 * rng.uniform(0.7, 1.3)),
                    "feed_kg": float(scale * 1e6 * season),
                    "available_at": month + pd.offsets.MonthBegin(1) + pd.Timedelta(days=19),
                }
            )
    return pd.DataFrame(rows)


@pytest.fixture
def ssb_weekly() -> pd.DataFrame:
    """Contract-shaped Statistics Norway weekly table, 2015-W01 to 2026-W44."""

    starts = pd.date_range("2014-12-29", "2026-10-26", freq="7D")
    iso = starts.isocalendar()
    angle = 2 * np.pi * starts.dayofyear / 365.25
    return pd.DataFrame(
        {
            "week": [f"{y}-W{w:02d}" for y, w in zip(iso["year"], iso["week"])],
            "week_start": starts,
            "price_nok_kg": 80 + 10 * np.sin(angle),
            "volume_t": 20_000 + 3_000 * np.cos(angle),
            "available_at": starts + pd.Timedelta(days=9),
        }
    )


@pytest.fixture
def weekly_area_index() -> pd.DataFrame:
    """Contract-shaped weekly area index for areas 1-13."""

    starts = pd.date_range("2017-01-02", "2026-09-28", freq="7D")
    iso = starts.isocalendar()
    labels = [f"{y}-W{w:02d}" for y, w in zip(iso["year"], iso["week"])]
    frames = []
    for area in range(1, 14):
        values = np.arange(len(starts), dtype=float) / 100 + area
        frames.append(
            pd.DataFrame(
                {
                    "area": area,
                    "week": labels,
                    "mobile_idx": values,
                    "mobile_anom": values / 10,
                    "treat_rate": 0.1,
                    "treat_anom": 0.0,
                    "disease_share": np.nan,
                    "temp_c": 9.0,
                    "dd_anom": 1.5,
                    "dd_below8": 0.0,
                    "dd_8to14": 1.5,
                    "dd_above14": 0.0,
                    "dd_below14": 1.5,
                    "n_reporting": 20,
                    "available_at": starts + pd.Timedelta(days=13),
                }
            )
        )
    return pd.concat(frames, ignore_index=True)


NOWCAST_LICE_EFFECT = 0.4


@pytest.fixture(scope="session")
def nowcast_world() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Directorate, weekly area index and SSB tables for nowcast tests.

    Harvest volume in month m rises with lice pressure in month m, so a
    correct nowcast should find a positive lice coefficient.
    """

    rng = np.random.default_rng(5)
    months = pd.date_range("2017-10-01", "2026-09-01", freq="MS")
    shock_months = pd.date_range("2012-01-01", "2026-10-01", freq="MS")
    weeks = pd.date_range("2012-01-02", "2026-10-26", freq="7D")
    week_month = (weeks + pd.Timedelta(days=3)).to_period("M").to_timestamp()
    iso = weeks.isocalendar()
    week_labels = [f"{y}-W{w:02d}" for y, w in zip(iso["year"], iso["week"])]
    week_season = np.sin(2 * np.pi * (weeks + pd.Timedelta(days=3)).dayofyear / 365.25)

    directorate_rows: list[dict[str, object]] = []
    weekly_frames = []
    for area in range(14):
        scale = area + 1
        lice_shock = pd.Series(rng.normal(0, 0.3, len(shock_months)), index=shock_months)
        if area >= 1:
            temp_c = 9 + 4 * week_season + rng.normal(0, 0.5, len(weeks))
            dd_anom = rng.normal(0, 5, len(weeks))
            weekly_frames.append(
                pd.DataFrame(
                    {
                        "area": area,
                        "week": week_labels,
                        "mobile_idx": np.expm1(
                            0.5
                            + 0.2 * week_season
                            + lice_shock.reindex(week_month).to_numpy()
                            + rng.normal(0, 0.02, len(weeks))
                        ),
                        "treat_rate": np.clip(0.1 + rng.normal(0, 0.02, len(weeks)), 0, 1),
                        "disease_share": np.nan,
                        "temp_c": temp_c,
                        "dd_anom": dd_anom,
                        "dd_below8": np.where(temp_c < 8, dd_anom, 0.0),
                        "dd_8to14": np.where((temp_c >= 8) & (temp_c < 14), dd_anom, 0.0),
                        "dd_above14": np.where(temp_c >= 14, dd_anom, 0.0),
                        "available_at": weeks + pd.Timedelta(days=13),
                    }
                )
            )
        for month in months:
            season = 1 + 0.3 * np.sin(2 * np.pi * month.month / 12)
            count = scale * 300_000 * season * np.exp(
                NOWCAST_LICE_EFFECT * lice_shock[month] + rng.normal(0, 0.02)
            )
            avg_kg = 4.5 * np.exp(rng.normal(0, 0.01))
            directorate_rows.append(
                {
                    "area": area,
                    "month": month.strftime("%Y-%m"),
                    "harvest_count": count,
                    "harvest_kg": count * avg_kg,
                    "avg_kg": avg_kg,
                    "biomass_kg": scale * 1e7 * season * rng.uniform(0.9, 1.1),
                    "fish_stock": scale * 2e6 * rng.uniform(0.9, 1.1),
                    "smolt_released": scale * 1e5 * rng.uniform(0.5, 1.5),
                    "dead": scale * 2e4 * rng.uniform(0.7, 1.3),
                    "feed_kg": scale * 1e6 * season * rng.uniform(0.9, 1.1),
                    "available_at": month + pd.offsets.MonthBegin(1) + pd.Timedelta(days=19),
                }
            )

    angle = 2 * np.pi * weeks.dayofyear / 365.25
    ssb = pd.DataFrame(
        {
            "week": week_labels,
            "week_start": weeks,
            "price_nok_kg": 80 + 10 * np.sin(angle),
            "volume_t": 20_000 * np.exp(0.1 * np.cos(angle) + rng.normal(0, 0.03, len(weeks))),
            "available_at": weeks + pd.Timedelta(days=9),
        }
    )
    return pd.DataFrame(directorate_rows), pd.concat(weekly_frames, ignore_index=True), ssb


@pytest.fixture
def weekly_national_index(weekly_area_index: pd.DataFrame) -> pd.DataFrame:
    return (
        weekly_area_index.loc[weekly_area_index["area"] == 1]
        .drop(columns="area")
        .reset_index(drop=True)
    )
