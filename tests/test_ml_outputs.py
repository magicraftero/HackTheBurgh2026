from __future__ import annotations

import json

import numpy as np
import pandas as pd

from ml.bands import coverage, rolling_bands
from ml.export import cockpit_payload, supply_payload

BACKTEST_COLUMNS = ("seasonal", "drivers", "ml", "blend")  # what ml.supply writes per row


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
                        for model in BACKTEST_COLUMNS:
                            row[model] = level + rng.normal(0, 0.1)
                        for model in ("drivers", "ml"):
                            row[f"why_{model}_lice"] = 0.01
                        rows.append(row)
    return pd.DataFrame(rows)


def test_supply_json_keeps_holdout_null_in_development() -> None:
    months = [str(p) for p in pd.period_range("2019-07", "2024-12", freq="M")]
    results = _supply_results({"warmup": months[:18], "dev": months[18:]})
    payload, _ = supply_payload(results, final=False)
    text = json.dumps(payload, allow_nan=False)
    assert payload["scores"]["holdout"] is None and payload["current"] is None
    assert {row["window"] for row in payload["backtest"]} == {"dev"}
    assert '"holdout"' not in text.replace('"holdout": null', "").replace('"holdout": [', "")
    row = payload["backtest"][-1]
    assert set(row) >= {"area", "issued", "h", "target", "actual", "pred", "band", "why"}
    # Only the model and its reference line reach the site; the model's two halves stay internal.
    assert set(row["pred"]) == {"seasonal", "blend"}
    assert payload["model"] == "blend" and payload["band"]["model"] == "blend"
    assert row["why"]["lice"] > 0


def test_supply_json_after_final_has_current_outlook() -> None:
    months = [str(p) for p in pd.period_range("2019-07", "2026-09", freq="M")]
    results = _supply_results({"warmup": months[:18], "dev": months[18:66], "holdout": months[66:],
                               "current": ["2026-10"]})
    payload, _ = supply_payload(results, final=True)
    json.dumps(payload, allow_nan=False)
    assert payload["scores"]["holdout"] is not None and payload["status"] == "final"
    target = payload["current"]["targets"][0]
    assert target["target"] == "2026-10" and target["publishes_around"] == "2026-11-20"
    assert target["areas"][0]["actual"]["t"] is None and target["areas"][0]["pred"]["blend"]["t"] > 0
    assert target["areas"][0]["band"]["t"][0] is not None


def test_cockpit_payload_uses_the_model() -> None:
    grids = {"target_month": "2026-10", "made_on": "2026-11-08", "areas": [
        {"area": 3, "levers": [{"id": "lice", "feature": "mobile_anom", "current": 0.5, "grid": list(np.linspace(0.1, 0.9, 9)),
                                "delta_log": {"ml": {"log_kg": [0.0] * 9}, "blend": {"log_kg": [0.01] * 9}}}]}]}
    cockpit = cockpit_payload(grids)
    assert cockpit["model"] == "blend"
    assert cockpit["areas"][0]["levers"][0]["delta_log"]["log_kg"][0] == 0.01
