from __future__ import annotations

import json

import numpy as np
import pandas as pd

from analysis.trap import build_trap


def _seasonal_world() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Lice and price share a seasonal cycle but have independent noise."""

    rng = np.random.default_rng(11)
    starts = pd.date_range("2012-01-02", "2026-10-26", freq="7D")
    iso = starts.isocalendar()
    labels = [f"{y}-W{w:02d}" for y, w in zip(iso["year"], iso["week"])]
    season = np.sin(2 * np.pi * (starts + pd.Timedelta(days=3)).dayofyear / 365.25)
    n = len(starts)

    ssb = pd.DataFrame(
        {
            "week": labels,
            "week_start": starts,
            "price_nok_kg": np.exp(4.3 + 0.15 * season + rng.normal(0, 0.03, n)),
            "volume_t": np.exp(10 - 0.2 * season + rng.normal(0, 0.05, n)),
            "available_at": starts + pd.Timedelta(days=9),
        }
    )
    weekly = pd.DataFrame(
        {
            "week": labels,
            "mobile_idx": np.expm1(0.5 + 0.3 * season + rng.normal(0, 0.03, n)),
            "treat_rate": 0.1 + 0.05 * season + rng.normal(0, 0.005, n),
            "disease_share": np.nan,
            "temp_c": 9 + 4 * season + rng.normal(0, 0.3, n),
        }
    )
    return ssb, weekly


def test_seasonal_correlation_disappears_in_anomalies() -> None:
    ssb, weekly = _seasonal_world()

    trap = build_trap(ssb, weekly)
    lice = next(d for d in trap["drivers"] if d["driver"] == "mobile_idx")

    assert lice["raw_r"] > 0.8
    assert abs(lice["anom_r"]) < 0.15


def test_trap_json_matches_contract() -> None:
    ssb, weekly = _seasonal_world()

    trap = build_trap(ssb, weekly)

    assert set(trap) == {"from", "to", "highlight", "drivers", "series"}
    assert trap["highlight"] == "mobile_idx"
    assert [d["driver"] for d in trap["drivers"]] == [
        "mobile_idx",
        "treat_rate",
        "temp_c",
        "export_vol",
    ]
    assert all(set(d) == {"driver", "label", "raw_r", "anom_r"} for d in trap["drivers"])
    assert set(trap["series"][0]) == {"week", "driver", "price", "driver_anom", "price_anom"}
    assert trap["series"][0]["week"] >= "2017-W01"
    assert trap["series"][-1]["week"] <= "2026-W44"
    json.dumps(trap, allow_nan=False)
