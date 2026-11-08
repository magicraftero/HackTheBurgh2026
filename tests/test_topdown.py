from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from analysis.topdown import exports_kg, month_weeks, run_topdown, topdown_month

TARGET = pd.Period("2024-06", "M")


def _world(seed: int = 0) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Areas harvest a stable share of a national total that exports track exactly (ratio 1.5)."""

    rng = np.random.default_rng(seed)
    months = pd.period_range("2017-10", "2024-12", freq="M")
    weights = np.linspace(1, 3, 13)
    base_share = weights / weights.sum()
    national = 1e8 * (1 + 0.2 * np.sin(np.arange(len(months)) / 2))
    rows = []
    for i, month in enumerate(months):
        noise = np.exp(rng.normal(0, 0.05, 13))
        share = base_share * noise / (base_share * noise).sum()
        for area in range(1, 14):
            biomass = 6 * national[i] * base_share[area - 1]
            rows.append(
                {
                    "area": area,
                    "month": str(month),
                    "harvest_kg": national[i] * share[area - 1],
                    "biomass_kg": biomass,
                    "fish_stock": biomass / 4.5,
                }
            )
    directorate = pd.DataFrame(rows)

    mondays = pd.date_range("2017-09-25", "2025-01-06", freq="W-MON")
    month_of = (mondays + pd.Timedelta(days=3)).to_period("M")
    weeks_per_month = pd.Series(month_of).value_counts()
    totals = pd.Series(national, index=months)
    volume_t = [
        totals.get(m, np.nan) / 1.5 / weeks_per_month[m] / 1000 for m in month_of
    ]
    ssb = pd.DataFrame(
        {"week_start": mondays, "volume_t": volume_t, "available_at": mondays + pd.Timedelta(days=9)}
    )
    return directorate, ssb


def test_month_weeks_follow_iso_thursdays() -> None:
    weeks = month_weeks(pd.Period("2026-10", "M"))

    assert weeks[0] == pd.Timestamp("2026-09-28")
    assert weeks[-1] == pd.Timestamp("2026-10-26")
    assert len(weeks) == 5


def test_exports_wait_for_every_week_to_be_public() -> None:
    _, ssb = _world()
    last_week = month_weeks(TARGET)[-1]

    assert np.isnan(exports_kg(ssb, TARGET, last_week + pd.Timedelta(days=8)))
    assert exports_kg(ssb, TARGET, last_week + pd.Timedelta(days=9)) > 0


def test_recovers_national_total_and_shares() -> None:
    directorate, ssb = _world()

    result = topdown_month(directorate, ssb, TARGET)
    actual = directorate.loc[directorate["month"] == str(TARGET)].set_index("area")["harvest_kg"]

    assert result["national_kg"].iloc[0] == pytest.approx(actual.sum(), rel=1e-6)
    errors = (result.set_index("area")["topdown"] - np.log(actual)).abs()
    assert errors.mean() < 0.06


def test_never_uses_the_target_month_or_later() -> None:
    directorate, ssb = _world()
    baseline = topdown_month(directorate, ssb, TARGET)

    poisoned = directorate.copy()
    future = pd.PeriodIndex(poisoned["month"], freq="M") >= TARGET
    poisoned.loc[future, ["harvest_kg", "biomass_kg", "fish_stock"]] *= 7
    late_ssb = ssb.copy()
    late_ssb.loc[late_ssb["week_start"] > pd.Timestamp("2024-07-10"), "volume_t"] *= 7

    again = topdown_month(poisoned, late_ssb, TARGET)

    pd.testing.assert_frame_equal(baseline, again)


def test_run_covers_every_area_and_month() -> None:
    directorate, ssb = _world()
    months = pd.period_range("2024-01", "2024-03", freq="M")

    result = run_topdown(directorate, ssb, months)

    assert len(result) == 13 * 3
    assert result["topdown"].notna().all()
