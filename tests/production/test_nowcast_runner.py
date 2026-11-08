"""Synthetic chronological runner tests; the real holdout is never opened."""

from datetime import datetime
import json
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

import analysis.nowcast as runner
import analysis.nowcast_tuning as tuning
from analysis.nowcast_data import VintageStore
from analysis.nowcast_inputs import OUTCOMES, forecast_date, model_features


def synthetic_inputs(origins=("2024-09", "2024-10", "2024-11", "2024-12", "2025-01", "2026-09")):
    """Thirteen areas, independent numerical predictors, and sparse area 13."""
    rng = np.random.default_rng(123)
    feature_names = model_features(True)["drivers"]
    source = []
    for month in pd.period_range("2019-01", max(origins), freq="M").astype(str):
        for area in range(1, 14):
            row = dict(zip(feature_names, rng.normal(size=len(feature_names))))
            signal = .2*row["biomass_anom_l1"] + .3*row["mobile_anom"]
            row.update(area=area, month=month,
                       available_at=(pd.Period(month) + 1).to_timestamp() + pd.Timedelta(days=19))
            zero = area == 1 and month == "2024-12"
            for name, level, base, factor in [("log_kg", "harvest_kg", 5., 1.),
                                               ("log_count", "harvest_count", 3., .8),
                                               ("log_avg_kg", "avg_kg", 2., .2)]:
                row[name] = np.nan if zero else base + factor*signal
                row[level] = (np.nan if name == "log_avg_kg" else 0.) if zero else np.exp(row[name])
                row[name + "_base"] = np.nan if area == 13 else base
                row[name + "_anom"] = np.nan if zero or area == 13 else factor*signal
                row[name + "_label"] = row[name]
            source.append(row)
    source = pd.DataFrame(source)
    targets = source[["area", "month", "available_at", *OUTCOMES, *OUTCOMES.values()]].copy()
    vintages = []
    for origin in origins:
        frame = source.loc[source.month <= origin].copy()
        frame["forecast_month"] = origin
        frame["made_on"] = forecast_date(origin)
        frame["is_target"] = frame.month == origin
        frame["feature_available_at"] = frame.month.map(forecast_date)
        frame["label_available_at"] = frame.available_at.where(~frame.is_target)
        for name in OUTCOMES:
            frame.loc[frame.is_target, [name + "_anom", name + "_label"]] = np.nan
        vintages.append(frame.drop(columns=["available_at", *OUTCOMES, *OUTCOMES.values()]))
    return pd.concat(vintages, ignore_index=True), targets


def write_inputs(directory, vintages, targets):
    directory.mkdir(parents=True)
    vintages.to_parquet(directory / "nowcast_vintages.parquet", index=False)
    vintages.loc[vintages.is_target].to_parquet(directory / "nowcast_features.parquet", index=False)
    targets.to_parquet(directory / "nowcast_targets.parquet", index=False)


def fake_estimator(calls):
    def predict(vintage, outcome, features, family, config=None, **kwargs):
        origins = vintage.forecast_month.unique()
        assert len(origins) == 1
        origin = origins[0]
        target = vintage.loc[vintage.is_target]
        train = vintage.loc[~vintage.is_target]
        assert (train.month < origin).all()
        assert target.filter(regex=r"_(label|anom)$").filter(like=outcome).isna().all().all()
        calls.append((origin, family, outcome, dict(config or {}), len(train)))
        result = target[["area", "month", "forecast_month", "made_on"]].reset_index(drop=True)
        result["base"] = target[outcome + "_base"].to_numpy()
        result["predicted_anomaly"] = .1*target[features[0]].to_numpy() + .01*len(features)
        result["predicted_log"] = result.predicted_anomaly + result.base
        result["predicted_level"] = np.exp(result.predicted_log)
        result["eligible"] = result.base.notna()
        result["reason"] = np.where(result.eligible, "", "missing_base")
        result["n_train"] = len(train)
        result["n_parameters"] = len(features) + 1
        result["rank"] = len(features) + 1
        result["condition"] = 2.
        result["configuration"] = json.dumps(config or {}, sort_keys=True)
        return result
    return predict


def test_default_parquet_filters_holdout_before_validation_or_fit(tmp_path, monkeypatch):
    vintages, targets = synthetic_inputs()
    # Invalid holdout-only labels would fail validation if materialised.
    vintages.loc[vintages.forecast_month >= "2025-01", "log_kg_label"] = np.inf
    targets.loc[targets.month >= "2025-01", "log_kg"] = np.inf
    source = tmp_path / "input"
    write_inputs(source, vintages, targets)
    original_read = pd.read_parquet
    reads = []
    def read(path, **kwargs):
        reads.append((str(path), kwargs.get("filters")))
        frame = original_read(path, **kwargs)
        column = "forecast_month" if "vintages" in str(path) else "month"
        assert (frame[column] <= "2024-12").all()
        return frame
    monkeypatch.setattr(pd, "read_parquet", read)
    store = VintageStore(source)
    calls = []
    monkeypatch.setattr(runner, "fit_predict", fake_estimator(calls))
    rows, _, _ = runner.run_development(store, families=("ols",))
    assert len(reads) == 2
    assert reads[0][1] == [("forecast_month", "<=", "2024-12")]
    assert reads[1][1] == [("month", "<=", "2024-12")]
    assert rows.window.eq("dev").all()
    assert all(month <= "2024-12" for month, *_ in calls)
    with pytest.raises(ValueError, match="protected"):
        store.vintage("2025-01")


def test_real_ols_runner_expands_history_reconstructs_and_handles_sparse_areas():
    vintages, targets = synthetic_inputs(origins=("2024-10", "2024-11"))
    store = VintageStore.from_frames(vintages, targets)
    rows, candidates, selection = runner.run_development(store, families=("ols",))
    assert candidates.empty
    assert selection["configurations"] == {}
    assert rows.loc[rows.area == 13, "reason"].eq("missing_base").all()
    valid = rows.loc[rows.eligible]
    np.testing.assert_allclose(valid.predicted_log, valid.predicted_anomaly + valid.base)
    np.testing.assert_allclose(valid.predicted_level, np.exp(valid.predicted_log))
    counts = rows.groupby("month").n_train.mean()
    assert counts.loc["2024-11"] > counts.loc["2024-10"]
    assert rows.loc[rows.model == "drivers", "abs_error"].dropna().max() < 1e-10


def test_tuning_decisions_use_only_earlier_published_whole_months():
    tuner = tuning.OnlineTuner()
    key = ("common_training", "ridge", "drivers", "log_kg")
    for month in ("2024-08", "2024-09", "2024-10", "2024-11"):
        for candidate in range(len(tuning.GRIDS["ridge"])):
            # Candidate zero is perfect but November labels are deliberately
            # unavailable at the December-origin selection date.
            frame = pd.DataFrame({"area": [1, 2, 13], "month": month,
                                  "predicted_log": float(candidate), "actual_log": 0., "score_eligible": True})
            labels = pd.DataFrame({"area": [1, 2, 13], "month": month,
                                   "available_at": pd.Timestamp("2025-03-20") if month == "2024-11" else forecast_date(month) + pd.Timedelta(days=10)})
            tuner.observe(key, candidate, frame, labels)
    chosen, info = tuner.choose(key, "2024-12")
    assert chosen == 0
    assert info["validation_months"] == ["2024-08", "2024-09", "2024-10"]
    assert info["n_validation"] == 9  # all three areas in each selected month
    assert tuning.month_partition("2024-12") == "train_dev"
    assert tuning.month_partition("2025-01") == "holdout"


def test_final_clock_timezone_and_once_guard(tmp_path):
    with pytest.raises(ValueError, match="timezone"):
        runner.check_final_allowed(tmp_path, datetime(2026, 11, 8, 5))
    with pytest.raises(ValueError, match="04:00"):
        runner.check_final_allowed(tmp_path, datetime(2026, 11, 8, 3, 59, tzinfo=ZoneInfo("Europe/London")))
    runner.check_final_allowed(tmp_path, datetime(2026, 11, 8, 4, tzinfo=ZoneInfo("Europe/London")))
    runner.check_final_allowed(tmp_path, datetime(2026, 11, 8, 5, tzinfo=ZoneInfo("Europe/Paris")))
    (tmp_path / "analysis").mkdir()
    (tmp_path / "analysis/nowcast_final_run.json").write_text("{}")
    with pytest.raises(ValueError, match="already recorded"):
        runner.check_final_allowed(tmp_path, datetime(2026, 11, 8, 6, tzinfo=ZoneInfo("Europe/London")))


def test_synthetic_cli_locks_then_final_never_retunes_and_preserves_incomplete_totals(tmp_path, monkeypatch):
    vintages, targets = synthetic_inputs()
    source, output = tmp_path / "input", tmp_path / "output"
    write_inputs(source, vintages, targets)
    calls, stopping_calls = [], []
    # Other agents may be editing implementation files concurrently; the
    # changed-code rejection is tested separately from this CLI happy path.
    monkeypatch.setattr(runner, "code_hashes", lambda: {"synthetic_fixture": "fixed"})
    monkeypatch.setattr(runner, "fit_predict", fake_estimator(calls))
    def early(vintage, outcome, features, config, labels, *, selection_month, sample_features=None):
        inner = vintage.forecast_month.unique().item()
        assert inner < selection_month
        assert (labels.month == inner).all()
        assert (labels.available_at <= forecast_date(selection_month)).all()
        stopping_calls.append((inner, selection_month))
        return {"iterations": 7, "n_train": len(vintage.loc[~vintage.is_target]),
                "n_validation": len(labels), "reason": "", "validation_month": inner,
                "selection_month": selection_month}
    monkeypatch.setattr(tuning, "early_stop_iterations", early)
    before = datetime(2026, 11, 8, 3, tzinfo=ZoneInfo("Europe/London"))
    after = datetime(2026, 11, 8, 4, tzinfo=ZoneInfo("Europe/London"))
    args = ["--input-dir", str(source), "--output-root", str(output)]
    with pytest.raises(ValueError, match="04:00"):
        runner.main([*args, "--final"], now=before)
    runner.main(args, now=before)
    assert calls and all(month <= "2024-12" for month, *_ in calls)
    development = json.loads((output / "web/public/data/nowcast.json").read_text())
    assert development["scores"]["holdout"] is None
    assert development["f1"] is None and development["latest"] is None
    assert all(row["month"] <= "2024-12" for row in development["backtest"])
    lock_file = output / "analysis/nowcast_selection.json"
    lock_bytes = lock_file.read_bytes()
    frozen = json.loads(lock_bytes)
    assert stopping_calls

    def forbidden(*args, **kwargs):
        raise AssertionError("The final path must not tune or rerun development")
    monkeypatch.setattr(runner, "run_development", forbidden)
    monkeypatch.setattr(tuning.OnlineTuner, "choose", forbidden)
    monkeypatch.setattr(tuning, "early_stop_iterations", forbidden)
    calls.clear()
    runner.main([*args, "--final"], now=after)
    final = json.loads((output / "web/public/data/nowcast.json").read_text())
    assert final["scores"]["holdout"] is not None
    assert final["latest"]["national"]["pred_kg"] is None
    assert final["latest"]["national"]["error_pct"] is None
    assert len(final["latest"]["areas"]) == 13
    assert final["latest"]["areas"][-1]["pred_kg"] is None
    assert lock_file.read_bytes() == lock_bytes
    assert (output / "analysis/nowcast_final_run.json").exists()
    groups = json.loads((output / "web/public/data/drivers.json").read_text())
    assert {group["group"] for group in groups["groups"]} == set(runner.GROUPS)
    holdout_calls = [call for call in calls if call[0] >= "2025-01"]
    assert holdout_calls
    # For challengers, every final fitted configuration is one of the exact
    # development-locked configurations. Ablations are OLS only.
    locked_configs = {json.dumps(value["config"], sort_keys=True) for value in frozen["configurations"].values()}
    assert all(json.dumps(config, sort_keys=True) in locked_configs
               for _, family, _, config, _ in holdout_calls if family != "ols")
    with pytest.raises(ValueError, match="already recorded"):
        runner.main([*args, "--final"], now=after)
    with pytest.raises(ValueError, match="development cannot replace"):
        runner.main(args, now=after)


@pytest.mark.parametrize("changed", ["inputs", "code", "versions"])
def test_final_rejects_changed_inputs_before_unlocked_store_is_opened(tmp_path, monkeypatch, changed):
    output = tmp_path / "output"
    (output / "analysis").mkdir(parents=True)
    versions = {name: runner.importlib.metadata.version(name) for name in ["pandas", "numpy", "pyarrow", "statsmodels", "scikit-learn", "catboost"]}
    locked = {"inputs": {}, "code": {}, "versions": versions.copy()}
    locked[changed] = {"old": "hash"}
    (output / "analysis/nowcast_selection.json").write_text(json.dumps(locked))
    monkeypatch.setattr(runner, "input_hashes", lambda directory: {})
    monkeypatch.setattr(runner, "code_hashes", lambda: {})
    def forbidden(*args, **kwargs):
        raise AssertionError("Changed inputs must be rejected before reading a final store")
    monkeypatch.setattr(runner, "VintageStore", forbidden)
    with pytest.raises(ValueError, match="changed after selection"):
        runner.main(["--final", "--input-dir", str(tmp_path), "--output-root", str(output)],
                    now=datetime(2026, 11, 8, 5, tzinfo=ZoneInfo("Europe/London")))
