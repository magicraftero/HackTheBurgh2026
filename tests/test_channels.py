from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from analysis.channels import build_bins


def _panel_with_lice_signature() -> pd.DataFrame:
    """High lice this month means more, smaller fish over the next 0-3 months."""

    rng = np.random.default_rng(3)
    months = pd.date_range("2018-01-01", periods=96, freq="MS").strftime("%Y-%m")
    frames = []
    for area in range(1, 14):
        lice = rng.normal(0, 1, len(months))
        pressure = pd.Series(lice).rolling(4, min_periods=1).mean().to_numpy()
        frames.append(
            pd.DataFrame(
                {
                    "area": area,
                    "month": months,
                    "mobile_anom": lice,
                    "count_anom": 0.1 * pressure + rng.normal(0, 0.01, len(months)),
                    "weight_anom": -0.05 * pressure + rng.normal(0, 0.01, len(months)),
                    "dd_below14": rng.normal(0, 1, len(months)),
                    "feed_rate_anom": rng.normal(0, 1, len(months)),
                    "mortality_anom": np.nan,
                }
            )
        )
    return pd.concat(frames, ignore_index=True)


def test_lice_terciles_show_more_but_smaller_fish() -> None:
    bins = build_bins(_panel_with_lice_signature())
    lice = {row["tercile"]: row for row in bins if row["driver"] == "lice"}

    assert lice[3]["count_anom"] > lice[1]["count_anom"]
    assert lice[3]["weight_anom"] < lice[1]["weight_anom"]
    assert lice[1]["window"] == "0-3"


def test_bins_match_contract_and_skip_missing_drivers() -> None:
    bins = build_bins(_panel_with_lice_signature())

    assert {row["driver"] for row in bins} == {"lice", "temp", "feed"}
    assert all(
        set(row) == {"driver", "tercile", "window", "count_anom", "weight_anom", "n"}
        for row in bins
    )
    assert {row["window"] for row in bins if row["driver"] == "temp"} == {"1-3"}
    json.dumps(bins, allow_nan=False)


def test_window_needs_every_month_present() -> None:
    panel = _panel_with_lice_signature()
    full_n = sum(row["n"] for row in build_bins(panel) if row["driver"] == "lice")
    panel.loc[(panel["area"] == 1) & (panel["month"] == "2020-06"), "count_anom"] = np.nan

    gappy_n = sum(row["n"] for row in build_bins(panel) if row["driver"] == "lice")

    assert gappy_n == pytest.approx(full_n - 4)
