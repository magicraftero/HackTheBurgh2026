from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from analysis.combined import backtest_records, combine, scores


def _inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    for window, month in (("dev", "2023-05"), ("holdout", "2025-05")):
        for area in (2, 3):
            truth = {"log_kg": 15.0 + area, "log_avg_kg": 1.5, "log_count": 13.5 + area}
            for outcome, actual in truth.items():
                rows.append(
                    {
                        "area": area, "month": month, "h": 0, "window": window,
                        "outcome": outcome, "actual": actual,
                        "b1": actual + 0.3, "drivers": actual + 0.2,
                        "ml": actual + (0.01 if outcome == "log_avg_kg" else 0.25),
                        "blend": actual + 0.22,
                    }
                )
            rows.append({**rows[-1], "h": 1, "ml": 99.0})
    ml = pd.DataFrame(rows)
    topdown = pd.DataFrame(
        {"area": [2, 3, 2, 3], "month": ["2023-05", "2023-05", "2025-05", "2025-05"],
         "v2": [17.05, 18.05, 17.05, 18.05]}
    )
    return ml, topdown


def test_combination_takes_v2_kg_ml_weight_and_derives_count() -> None:
    frame = combine(*_inputs())

    row = frame.loc[(frame["area"] == 2) & (frame["window"] == "dev")].iloc[0]
    assert row["combined_log_kg"] == pytest.approx(17.05)
    assert row["combined_log_avg_kg"] == pytest.approx(1.51)
    assert row["combined_log_count"] == pytest.approx(17.05 - 1.51)


def test_only_this_month_forecasts_are_used() -> None:
    frame = combine(*_inputs())

    assert (frame["ml_log_count"] < 50).all()


def test_scores_and_records_are_valid_json() -> None:
    frame = combine(*_inputs())
    result = scores(frame)
    records = backtest_records(frame)

    assert result["holdout"]["log_kg"]["combined"] == pytest.approx(0.05)
    assert result["dev"]["log_avg_kg"]["combined"] == pytest.approx(0.01)
    first = records[0]
    assert first["pred"]["kg"] == pytest.approx(first["pred"]["count"] * first["pred"]["avg_kg"], rel=1e-3)
    json.dumps({"scores": result, "backtest": records}, allow_nan=False)
