from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from ml.bands import coverage, rolling_bands
from ml.export import price_payload, supply_payload, winner
from ml.price import forecast_origin
from price.dataset import PriceDataset
from price.models import choose_lag
from price.tests.fixtures import frames as price_frames


def _band_rows(errors: np.ndarray) -> pd.DataFrame:
    n = len(errors)
    return pd.DataFrame({"h": 0, "target_n": np.arange(n), "known_n": np.arange(n) - 1,
                         "actual": errors, "m": np.zeros(n)})


def test_bands_use_only_errors_known_by_the_issue_date() -> None:
    rng = np.random.default_rng(1)
    errors = rng.normal(0, 1, 60)
    base = rolling_bands(_band_rows(errors), models=["m"], by=["h"], target="target_n", known="known_n",
                         actual="actual", window=36, minimum=12)
    changed = errors.copy()
    changed[40:] *= 100
    later = rolling_bands(_band_rows(changed), models=["m"], by=["h"], target="target_n", known="known_n",
                          actual="actual", window=36, minimum=12)
    np.testing.assert_allclose(base.loc[:40, ["lo_m", "hi_m"]], later.loc[:40, ["lo_m", "hi_m"]])
    assert base.loc[:11, "lo_m"].isna().all() and base.loc[12:, "lo_m"].notna().all()
    assert 0.6 < coverage(base, "m", "actual") < 0.95


def test_winner_needs_the_full_margin() -> None:
    def scores(challenger: float) -> list[dict]:
        return [{"h": 0, "outcome": "log_kg", "model": m, "mae_log": v}
                for m, v in {"drivers": 1.0, "ml": challenger, "blend": 1.5}.items()]

    rule = "test"
    assert winner(scores(0.98), ["drivers"], {"h": 0, "outcome": "log_kg"}, rule)["model"] == "ml"
    assert winner(scores(0.981), ["drivers"], {"h": 0, "outcome": "log_kg"}, rule)["model"] == "drivers"
    assert winner(scores(0.5), ["drivers"], {"h": 0, "outcome": "log_kg"}, rule)["leakage_check"]


def _supply_results(windows: dict[str, list[str]]) -> pd.DataFrame:
    rng = np.random.default_rng(2)
    rows = []
    for window, months in windows.items():
        for month in months:
            for h in (0, 1):
                for area in (2, 3):
                    for outcome, level in (("log_kg", 15.0), ("log_count", 13.5), ("log_avg_kg", 1.5)):
                        actual = np.nan if window == "current" else level + rng.normal(0, 0.1)
                        row = {"area": area, "month": month, "h": h, "issued": f"{month}-10",
                               "window": window, "outcome": outcome, "actual": actual, "n_train": 100}
                        for model in ("seasonal", "b0", "b1", "drivers", "ml", "blend"):
                            row[model] = level + rng.normal(0, 0.1)
                        for model in ("drivers", "ml"):
                            row[f"why_{model}_lice"] = 0.01
                        rows.append(row)
    return pd.DataFrame(rows)


def test_supply_json_keeps_holdout_null_in_development() -> None:
    months = [str(p) for p in pd.period_range("2019-07", "2024-12", freq="M")]
    results = _supply_results({"warmup": months[:18], "dev": months[18:]})
    payload, summary = supply_payload(results, final=False)
    text = json.dumps(payload, allow_nan=False)
    assert payload["scores"]["holdout"] is None and payload["current"] is None
    assert {row["window"] for row in payload["backtest"]} == {"dev"}
    assert '"holdout"' not in text.replace('"holdout": null', "").replace('"holdout": [', "")
    row = payload["backtest"][-1]
    assert set(row) >= {"area", "issued", "h", "target", "actual", "pred", "band"}
    assert set(row["pred"]) == {"seasonal", "b0", "b1", "drivers", "ml", "blend"}
    assert summary["winner"]["model"] in {"drivers", "ml", "blend"}


@pytest.fixture(scope="module")
def price_dataset() -> PriceDataset:
    return PriceDataset.from_frames(*price_frames())


def test_price_forecast_ignores_unpublished_data(price_dataset: PriceDataset) -> None:
    ssb, fx, directorate, weekly = price_frames()
    prefit = price_dataset.snapshot(pd.Timestamp("2018-12-31"))
    lags = {h: choose_lag(prefit, h)[0] for h in range(1, 9)}
    t = price_dataset.ssb.index[price_dataset.ssb.week == "2023-W10"][0]
    origin = price_dataset.ssb.loc[t, "available_at"]
    start, end = pd.Timestamp("2019-01-01"), pd.Timestamp("2024-12-30")
    before = pd.DataFrame(forecast_origin(price_dataset, t, origin, lags, start, end))

    ssb = ssb.copy()
    ssb.loc[ssb.available_at > origin, ["price_nok_kg", "volume_t"]] *= 3
    weekly = weekly.copy()
    weekly.loc[weekly.available_at > origin, "mobile_idx"] *= 5
    later = PriceDataset.from_frames(ssb, fx, directorate, weekly)
    after = pd.DataFrame(forecast_origin(later, t, origin, lags, start, end))
    for model in ("ar", "c0", "c1", "ml", "blend"):
        np.testing.assert_allclose(before[model], after[model], atol=1e-12)
    assert (before["h"] == np.arange(1, 9)).all()
    np.testing.assert_allclose(before["blend"], (before["c0"] + before["ml"]) / 2)


def test_price_json_shape(price_dataset: PriceDataset) -> None:
    prefit = price_dataset.snapshot(pd.Timestamp("2018-12-31"))
    lags = {h: choose_lag(prefit, h)[0] for h in range(1, 9)}
    rows = []
    for week in ("2022-W10", "2022-W40", "2023-W10"):
        t = price_dataset.ssb.index[price_dataset.ssb.week == week][0]
        rows += forecast_origin(price_dataset, t, price_dataset.ssb.loc[t, "available_at"], lags,
                                pd.Timestamp("2019-01-01"), pd.Timestamp("2024-12-30"))
    ssb, *_ = price_frames()
    payload, _ = price_payload(pd.DataFrame(rows), ssb, final=False)
    json.dumps(payload, allow_nan=False)
    assert payload["scores"]["holdout"] is None and payload["current"] is None
    entry = payload["backtest"][0]
    assert set(entry["pred"]) == {"rw", "ar", "c0", "c1", "ml", "blend"}
    assert entry["actual"] > 0 and entry["pred"]["rw"] > 0
