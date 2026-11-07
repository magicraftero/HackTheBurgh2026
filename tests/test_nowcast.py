from __future__ import annotations

import json
from datetime import datetime

import numpy as np
import pandas as pd
import pytest

from analysis.nowcast import (
    FREEZE_AT,
    PreparedInputs,
    build_nowcast_json,
    build_vintage,
    driver_ranking,
    f1_test,
    forecast_date,
    holdout_unlocked,
    model_features,
    nowcast_month,
    ranking_features,
    run_backtest,
    target_months,
)

LICE_EFFECT = 0.4


def _synthetic_world(seed: int = 5) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """A world where harvest volume in month m rises with lice pressure in m."""

    rng = np.random.default_rng(seed)
    months = pd.date_range("2017-10-01", "2026-09-01", freq="MS")
    weeks = pd.date_range("2012-01-02", "2026-10-26", freq="7D")
    week_month = (weeks + pd.Timedelta(days=3)).to_period("M").to_timestamp()
    iso = weeks.isocalendar()
    week_labels = [f"{y}-W{w:02d}" for y, w in zip(iso["year"], iso["week"])]
    week_season = np.sin(2 * np.pi * (weeks + pd.Timedelta(days=3)).dayofyear / 365.25)

    directorate_rows: list[dict[str, object]] = []
    weekly_frames = []
    for area in range(14):
        scale = area + 1
        lice_shock = pd.Series(
            rng.normal(0, 0.3, len(pd.date_range("2012-01-01", "2026-10-01", freq="MS"))),
            index=pd.date_range("2012-01-01", "2026-10-01", freq="MS"),
        )
        if area >= 1:
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
                        "dd_below8": rng.normal(0, 5, len(weeks)),
                        "dd_8to14": rng.normal(0, 5, len(weeks)),
                        "dd_above14": 0.0,
                        "available_at": weeks + pd.Timedelta(days=13),
                    }
                )
            )
        for month in months:
            season = 1 + 0.3 * np.sin(2 * np.pi * month.month / 12)
            count = scale * 300_000 * season * np.exp(
                LICE_EFFECT * lice_shock[month] + rng.normal(0, 0.02)
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


@pytest.fixture(scope="module")
def world() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    return _synthetic_world()


@pytest.fixture(scope="module")
def dev_results(world: tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]) -> pd.DataFrame:
    prepared = PreparedInputs(*world)
    features = model_features(prepared.include_disease)
    months = pd.period_range("2023-01", "2023-12", freq="M")
    return run_backtest(prepared, months, features, features["drivers"])


def test_forecast_date_is_tenth_of_following_month() -> None:
    assert forecast_date(pd.Period("2026-09", "M")) == pd.Timestamp("2026-10-10")


def test_holdout_is_locked_by_default() -> None:
    assert str(target_months(final=False)[-1]) == "2024-12"
    assert str(target_months(final=True)[-1]) == "2026-09"
    assert not holdout_unlocked(datetime(2026, 11, 8, 3, 59), confirm_freeze=False)
    assert holdout_unlocked(FREEZE_AT, confirm_freeze=False)


def test_nowcast_ignores_everything_not_yet_public(
    world: tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame],
) -> None:
    directorate, weekly, ssb = world
    target = pd.Period("2023-06", "M")
    made_on = forecast_date(target)
    features = model_features(include_disease=False)

    def predict(d: pd.DataFrame, w: pd.DataFrame, s: pd.DataFrame) -> pd.DataFrame:
        vintage = build_vintage(PreparedInputs(d, w, s), target)
        return nowcast_month(vintage, target, features, features["drivers"])

    original = predict(directorate, weekly, ssb)

    future_directorate = directorate.copy()
    later = future_directorate["month"] >= str(target)
    future_directorate.loc[later, ["harvest_count", "harvest_kg", "biomass_kg", "feed_kg"]] *= 3
    future_weekly = weekly.copy()
    future_weekly.loc[future_weekly["available_at"] > made_on, "mobile_idx"] *= 5
    future_ssb = ssb.copy()
    future_ssb.loc[future_ssb["available_at"] > made_on, "volume_t"] *= 5
    changed = predict(future_directorate, future_weekly, future_ssb)

    for model in ("b0", "b1", "drivers"):
        np.testing.assert_allclose(original[model], changed[model])
    assert original["drivers"].notna().all()


def test_drivers_model_finds_the_lice_signal(dev_results: pd.DataFrame) -> None:
    kg = dev_results.loc[dev_results["outcome"] == "log_kg"]
    mae = {m: (kg[m] - kg["actual"]).abs().mean() for m in ("b1", "drivers")}

    assert mae["drivers"] < 0.8 * mae["b1"]


def test_development_json_keeps_holdout_fields_null(dev_results: pd.DataFrame) -> None:
    nowcast = build_nowcast_json(dev_results, final=False)

    assert nowcast["f1"] is None
    assert nowcast["latest"] is None
    assert nowcast["scores"]["holdout"] is None
    assert {row["window"] for row in nowcast["backtest"]} == {"dev"}
    assert set(nowcast["scores"]["dev"]) == {"log_kg", "log_count", "log_avg_kg"}
    row = nowcast["backtest"][0]
    assert set(row) == {"area", "month", "window", "made_on", "actual", "pred"}
    assert set(row["pred"]) == {"b0", "b1", "drivers"}
    assert set(row["actual"]) == {"kg", "count", "avg_kg"}
    json.dumps(nowcast, allow_nan=False)


def _holdout_results(drivers_noise: float, b1_noise: float) -> pd.DataFrame:
    rng = np.random.default_rng(1)
    rows = []
    for month in pd.period_range("2025-01", "2026-09", freq="M"):
        for area in range(1, 14):
            actual = rng.normal(15, 0.5)
            rows.append(
                {
                    "area": area,
                    "month": str(month),
                    "window": "holdout",
                    "outcome": "log_kg",
                    "actual": actual,
                    "b0": actual + rng.normal(0, b1_noise),
                    "b1": actual + rng.normal(0, b1_noise),
                    "drivers": actual + rng.normal(0, drivers_noise),
                }
            )
    return pd.DataFrame(rows)


def test_f1_passes_when_drivers_clearly_beat_b1() -> None:
    f1 = f1_test(_holdout_results(drivers_noise=0.05, b1_noise=0.15))

    assert f1["improvement_pct"] > 5
    assert f1["cw_p"] < 0.05
    assert f1["pass"] is True


def test_f1_fails_when_drivers_add_nothing() -> None:
    f1 = f1_test(_holdout_results(drivers_noise=0.15, b1_noise=0.15))

    assert f1["pass"] is False


def test_driver_ranking_shape(world: tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]) -> None:
    prepared = PreparedInputs(*world)
    features = model_features(prepared.include_disease)
    features |= ranking_features(features["drivers"])
    months = pd.period_range("2023-01", "2023-04", freq="M")
    results = run_backtest(prepared, months, features, features["drivers"])

    ranking = driver_ranking(results, features["drivers"])
    lice = next(g for g in ranking["groups"] if g["group"] == "lice")
    losses = next(g for g in ranking["groups"] if g["group"] == "losses")

    assert lice["increase_pct"] > 0
    assert losses["columns"] == ["mortality_anom"]
    assert set(ranking["by_outcome"]) == {"log_count", "log_avg_kg"}
    json.dumps(ranking, allow_nan=False)
