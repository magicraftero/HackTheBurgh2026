from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from analysis.nowcast_data import VintageStore
from analysis.nowcast_inputs import OUTCOMES, forecast_date, model_features


def _frames():
    rows, targets = [], []
    for origin in ("2021-01", "2021-02", "2025-01"):
        for area in range(1, 14):
            for month in (str(pd.Period(origin, freq="M") - 1), origin):
                is_target = month == origin
                made_on = forecast_date(origin)
                row = {"area": area, "month": month, "forecast_month": origin,
                       "made_on": made_on, "is_target": is_target,
                       "feature_available_at": made_on - pd.Timedelta(days=1),
                       "label_available_at": pd.NaT if is_target else made_on - pd.Timedelta(days=1)}
                row.update({name: 0.5 for name in model_features(True)["drivers"]})
                for outcome in OUTCOMES:
                    row[outcome + "_base"] = 2.
                    row[outcome + "_anom"] = np.nan if is_target else 0.1
                    row[outcome + "_label"] = np.nan if is_target else 2.1
                rows.append(row)
            target = {"area": area, "month": origin,
                      "available_at": forecast_date(origin) + pd.Timedelta(days=10)}
            for outcome, level in OUTCOMES.items():
                target[level] = 10.
                target[outcome] = np.log(10.)
            targets.append(target)
    return pd.DataFrame(rows), pd.DataFrame(targets)


def test_default_parquet_reads_have_holdout_filters(monkeypatch, tmp_path):
    vintages, targets = _frames()
    calls = []

    def read(path, *, filters):
        calls.append((Path(path).name, filters))
        frame = vintages if "vintages" in str(path) else targets
        column, operator, cutoff = filters[0]
        assert operator == "<="
        return frame.loc[frame[column] <= cutoff].copy()

    monkeypatch.setattr(pd, "read_parquet", read)
    store = VintageStore(tmp_path)
    assert calls == [("nowcast_vintages.parquet", [("forecast_month", "<=", "2024-12")]),
                     ("nowcast_targets.parquet", [("month", "<=", "2024-12")])]
    assert store.months == ("2021-01", "2021-02")
    assert store.targets().month.max() == "2021-02"
    with pytest.raises(ValueError, match="Holdout vintages"):
        store.vintage("2025-01")


def test_months_preserve_all_areas_and_return_defensive_copies():
    store = VintageStore.from_frames(*_frames())
    snapshot = store.vintage("2021-01")
    assert set(snapshot.loc[snapshot.is_target, "area"]) == set(range(1, 14))
    snapshot.loc[:, "log_kg_base"] = 999.
    assert store.vintage("2021-01").log_kg_base.eq(2.).all()
    target = store.targets()
    target["log_kg"] = 999.
    assert store.targets().log_kg.lt(3).all()
    assert store.audit()["target_area_rows"] == 26


@pytest.mark.parametrize("corruption, message", [
    ("target_label", "Target labels leaked"),
    ("future_feature", "predictors published after"),
    ("future_label", "labels published after"),
    ("duplicate", "Duplicate vintage"),
    ("missing_area", "all 13 target areas"),
])
def test_rejects_corrupt_vintages(corruption, message):
    vintages, targets = _frames()
    if corruption == "target_label":
        vintages.loc[vintages.is_target, "log_kg_label"] = 2.
    elif corruption == "future_feature":
        vintages["feature_available_at"] = vintages.made_on + pd.Timedelta(days=1)
    elif corruption == "future_label":
        vintages.loc[~vintages.is_target, "label_available_at"] = vintages.loc[~vintages.is_target, "made_on"] + pd.Timedelta(days=1)
    elif corruption == "duplicate":
        vintages = pd.concat([vintages, vintages.iloc[[0]]])
    elif corruption == "missing_area":
        vintages = vintages.loc[~(vintages.is_target & vintages.area.eq(13))]
    with pytest.raises(ValueError, match=message):
        VintageStore.from_frames(vintages, targets)


def test_final_store_permits_expanding_test_history():
    store = VintageStore.from_frames(*_frames(), final=True)
    assert store.months[-1] == "2025-01"
    assert store.vintage("2025-01").month.max() == "2025-01"
    assert store.targets().month.max() == "2025-01"


def test_zero_actuals_cannot_be_relabelled_as_finite_logs():
    vintages, targets = _frames()
    targets.loc[0, "harvest_kg"] = 0.
    with pytest.raises(ValueError, match="ordinary logs"):
        VintageStore.from_frames(vintages, targets)
    targets.loc[0, "log_kg"] = np.nan
    store = VintageStore.from_frames(vintages, targets)
    assert store.targets().log_kg.isna().sum() == 1
