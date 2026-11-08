import numpy as np
import pandas as pd
import pytest

from analysis.cockpit import bin_effects_log, build_cockpit, heavy_stock_effect, latest_price, seasonal_tables


def _bins(driver, counts, weights):
    return [
        {"driver": driver, "tercile": t, "count_anom": c, "weight_anom": w, "window": "0-3"}
        for t, c, w in zip((1, 2, 3), counts, weights)
    ]


def _directorate(heavy_jump=False):
    rows = []
    for i, period in enumerate(pd.period_range("2019-01", "2023-12", freq="M")):
        weight = 2.0 + 0.5 * np.sin(i)
        rows.append({
            "area": 3, "month": str(period), "harvest_count": 1000.0, "harvest_kg": 5000.0,
            "biomass_kg": 50000.0 * (1 + 0.1 * (period.month % 3)), "fish_stock": 50000.0 / weight,
        })
    return pd.DataFrame(rows)


def test_effects_are_against_the_middle_third():
    effects = bin_effects_log({"bins": _bins("lice", (-0.05, 0.01, 0.09), (0.02, 0.0, -0.01))})
    assert effects["lice"]["high"] == {"count": pytest.approx(0.08), "weight": pytest.approx(-0.01)}
    assert effects["lice"]["low"]["count"] == pytest.approx(-0.06)
    assert "temp" not in effects


def test_seasonal_tables_have_twelve_months_and_weights():
    tables = seasonal_tables(_directorate())
    assert len(tables[3]["rate"]) == 12
    assert tables[3]["harvest_weight"][0] == pytest.approx(5.0)
    assert tables[3]["rate"][2] == pytest.approx(5000 / 50000)
    sw = tables[3]["stock_weight"]
    assert sw["p20"] < sw["p50"] < sw["p80"]


def test_heavy_stock_effect_is_finite():
    assert np.isfinite(heavy_stock_effect(_directorate()))


def test_latest_price_takes_the_newest_week():
    assert latest_price({"history": [{"week": "2026-W43"}, {"week": "2026-W44"}]}) == {"week": "2026-W44"}
    assert latest_price(None) is None


def test_build_cockpit_shape():
    farmer = {
        "target_month": "2026-10", "made_on": "2026-11-08", "disclaimer": "d", "national": None,
        "areas": [{"area": 3, "name": "Three", "forecast": None, "fish_weight_in_water": None,
                   "signals": {"lice": {"percentile": 90}}}],
    }
    result = build_cockpit(_directorate(), {"bins": _bins("lice", (0, 0, 0.1), (0, 0, -0.01))}, farmer)
    area = result["areas"][0]
    assert area["now"] == {"lice": 90, "mortality": None, "temp": None}
    assert {"rate", "harvest_weight", "stock_weight"} <= set(area)
    assert result["price"] is None
