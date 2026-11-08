import numpy as np
import pandas as pd
import pytest

from analysis.farmer import area_actions, bin_effects, same_month_last_year, stock_weight


def _bins(driver, counts, weights, window="0-3"):
    return [
        {"driver": driver, "tercile": t, "count_anom": c, "weight_anom": w, "window": window}
        for t, c, w in zip((1, 2, 3), counts, weights)
    ]


@pytest.fixture
def effects():
    channels = {"bins": _bins("lice", (0.0, 0.0, np.log(1.1)), (0.0, 0.0, np.log(0.98)))
                + _bins("mortality", (0.0, 0.0, 0.08), (0.0, 0.0, -0.02))
                + _bins("temp", (-0.06, 0.0, 0.03), (-0.01, 0.0, 0.01), "1-3")}
    return bin_effects(channels)


def test_bin_effects_are_percent_against_middle_tercile(effects):
    assert effects["lice"]["high"]["count_pct"] == pytest.approx(10)
    assert effects["lice"]["high"]["weight_pct"] == pytest.approx(-2)
    assert effects["temp"]["low"]["window"] == "1-3"


def test_bin_effects_skip_drivers_missing_a_tercile():
    channels = {"bins": _bins("lice", (0, 0, 0), (0, 0, 0))[:2]}
    assert bin_effects(channels) == {}


def test_quiet_month_says_nothing_unusual(effects):
    signals = {"lice": {"percentile": 50}, "mortality": {"percentile": 50},
               "temp_anomaly": {"percentile": 50}}
    actions = area_actions(signals, effects, {"kg": 2.0, "percentile": 50})
    assert [a["id"] for a in actions] == ["all_normal"]


def test_high_signals_raise_cards_with_measured_numbers(effects):
    signals = {"lice": {"percentile": 90}, "mortality": {"percentile": 85},
               "temp_anomaly": {"percentile": 10}, "treatments": {"percentile": 95}}
    actions = area_actions(signals, effects, {"kg": 2.6, "percentile": 90})
    ids = [a["id"] for a in actions]
    assert ids == ["lice_high", "mortality_high", "sea_cold", "near_harvest_size", "treatments_high"]
    assert "+10%" in actions[0]["pattern"]
    assert all({"severity", "title", "pattern", "consider"} <= set(a) for a in actions)


def test_cards_need_a_measured_pattern():
    actions = area_actions({"lice": {"percentile": 99}}, {}, None)
    assert [a["id"] for a in actions] == ["all_normal"]


def _directorate():
    months = [str(p) for p in pd.period_range("2024-01", "2025-10", freq="M")]
    rows = []
    for i, month in enumerate(months):
        rows.append({"area": 3, "month": month, "harvest_kg": 1000.0 + i,
                     "biomass_kg": 100.0 * (i + 1), "fish_stock": 100.0})
    return pd.DataFrame(rows)


def test_stock_weight_ranks_against_the_areas_own_past():
    weights = stock_weight(_directorate(), "2025-10")
    assert weights[3]["kg"] == pytest.approx(22.0)
    assert weights[3]["percentile"] == pytest.approx(100.0)
    earlier = stock_weight(_directorate(), "2024-02")
    assert earlier[3]["percentile"] == pytest.approx(100.0)
    assert 2 not in weights


def test_same_month_last_year():
    assert same_month_last_year(_directorate(), "2025-10") == {3: 1009.0}
