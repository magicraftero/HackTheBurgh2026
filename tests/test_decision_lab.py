from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from analysis.decision_lab import build_decision_lab
from analysis.nowcast import PreparedInputs, model_features, run_backtest

World = tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]
TARGET = pd.Period("2026-10", "M")
CUTOFF = pd.Timestamp("2026-11-07")


@pytest.fixture(scope="module")
def backtest(nowcast_world: World) -> pd.DataFrame:
    prepared = PreparedInputs(*nowcast_world)
    features = model_features(prepared.include_disease)
    months = pd.period_range("2024-07", "2024-12", freq="M")
    return run_backtest(prepared, months, features, features["drivers"])


@pytest.fixture(scope="module")
def lab(nowcast_world: World, backtest: pd.DataFrame) -> dict:
    return build_decision_lab(PreparedInputs(*nowcast_world), TARGET, CUTOFF, backtest)


def _apply_lever(area: dict, lab: dict, lever_id: str, new_value: float) -> float:
    """The cockpit's arithmetic, as documented in analysis/DECISION_LAB.md."""

    meta = next(lever for lever in lab["levers"] if lever["id"] == lever_id)
    lever = next(lever for lever in area["levers"] if lever["id"] == lever_id)
    transform = np.log1p if meta["transform"] == "log1p" else (lambda v: v)
    shift = transform(meta["scale"] * new_value) - transform(meta["scale"] * lever["current"])
    return float(np.exp(area["baseline"]["log"]["log_kg"] + lever["coef"]["log_kg"] * shift))


def test_lab_covers_every_area_and_is_valid_json(lab: dict) -> None:
    assert [area["area"] for area in lab["areas"]] == list(range(1, 14))
    assert lab["target_month"] == "2026-10"
    assert lab["made_on"] == "2026-11-07"
    assert {lever["id"] for lever in lab["levers"]} == {"lice", "treatments", "temperature"}
    assert all(area["baseline"]["kg"] is not None for area in lab["areas"])
    json.dumps(lab, allow_nan=False)


def test_raising_lice_raises_forecast_in_a_world_where_lice_drive_harvest(lab: dict) -> None:
    area = lab["areas"][5]
    lice = next(lever for lever in area["levers"] if lever["id"] == "lice")

    unchanged = _apply_lever(area, lab, "lice", lice["current"])
    higher = _apply_lever(area, lab, "lice", lice["current"] + 0.5)

    assert unchanged == pytest.approx(area["baseline"]["kg"], rel=1e-3)
    assert 0 < area["baseline"]["kg_range"][0] < unchanged
    assert lice["coef"]["log_kg"] > 0
    assert higher > unchanged


def test_forecast_range_brackets_the_baseline(lab: dict) -> None:
    for area in lab["areas"]:
        low, high = area["baseline"]["kg_range"]
        assert low < area["baseline"]["kg"] < high
    national = lab["national"]
    assert national["kg_range"][0] < national["kg"] < national["kg_range"][1]


def test_holdout_errors_never_shape_the_range(
    nowcast_world: World, backtest: pd.DataFrame, lab: dict
) -> None:
    poisoned = backtest.copy()
    holdout = poisoned.assign(window="holdout", drivers=poisoned["drivers"] + 5, month="2025-06")

    with_holdout = build_decision_lab(
        PreparedInputs(*nowcast_world), TARGET, CUTOFF, pd.concat([poisoned, holdout])
    )

    assert with_holdout["model"]["interval"] == lab["model"]["interval"]


def test_extreme_lice_this_month_raises_a_flag(nowcast_world: World, backtest: pd.DataFrame) -> None:
    directorate, weekly, ssb = nowcast_world
    weekly = weekly.copy()
    october = (weekly["area"] == 3) & weekly["week"].between("2026-W40", "2026-W44")
    weekly.loc[october, "mobile_idx"] *= 10

    lab = build_decision_lab(PreparedInputs(directorate, weekly, ssb), TARGET, CUTOFF, backtest)
    area = next(a for a in lab["areas"] if a["area"] == 3)

    assert "lice_high" in {flag["id"] for flag in area["flags"]}
    assert area["signals"]["lice"]["percentile"] >= 80
