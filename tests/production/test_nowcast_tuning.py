"""Chronological tuning tests use in-memory candidate forecasts only."""

import numpy as np
import pandas as pd
import pytest

import analysis.nowcast_tuning as tuning
from analysis.nowcast_inputs import forecast_date

KEY = ("common_training", "ridge", "drivers", "log_kg")


def _observe(tuner, month, losses, *, available_at=None, missing=None, areas=(1, 2)):
    """Record every candidate on the same constructed validation month."""
    if available_at is None:
        available_at = (pd.Period(month, freq="M") + 1).to_timestamp() + pd.Timedelta(days=19)
    targets = pd.DataFrame({"area": areas, "month": month, "available_at": available_at})
    for candidate in range(len(tuning.RIDGE_GRID)):
        candidate_losses = losses[candidate]
        if np.isscalar(candidate_losses):
            candidate_losses = [candidate_losses] * len(areas)
        frame = pd.DataFrame({"area": areas, "month": month,
                              "predicted_log": candidate_losses, "actual_log": 0.,
                              "score_eligible": True})
        for area in (missing or {}).get(candidate, []):
            frame.loc[frame.area == area, "score_eligible"] = False
        tuner.observe(KEY, candidate, frame, targets)


def test_calendar_partition_is_87_development_and_21_holdout_months():
    months = pd.period_range("2017-10", "2026-09", freq="M")
    partitions = pd.Series([tuning.month_partition(m) for m in months])
    assert partitions.value_counts().to_dict() == {"train_dev": 87, "holdout": 21}
    assert tuning.month_partition("2017-09") == "outside"
    assert tuning.month_partition("2026-10") == "outside"
    assert tuning.month_partition("2024-12") == "train_dev"
    assert tuning.month_partition("2025-01") == "holdout"


def test_validation_folds_are_unique_whole_months_and_only_earlier_development():
    # Thirteen repeated area rows must not become thirteen folds.
    months = np.repeat(pd.period_range("2020-01", "2026-09", freq="M").astype(str), 13)
    folds = tuning.validation_months(months, "2024-05")
    assert folds == tuple(pd.period_range("2023-05", "2024-04", freq="M").astype(str))
    assert len(folds) == len(set(folds)) == 12
    assert all(tuning.month_partition(month) == "train_dev" for month in folds)
    assert not tuning.validation_months(months, "2021-01")
    # Even a selection after the freeze may only refer to development folds.
    holdout_choice = tuning.validation_months(months, "2025-08")
    assert holdout_choice[-1] == "2024-12"
    assert all(month <= "2024-12" for month in holdout_choice)


@pytest.mark.parametrize("n_months", [0, 1, 2])
def test_fixed_documented_default_until_three_earlier_validation_months(n_months):
    tuner = tuning.OnlineTuner()
    for month in pd.period_range("2021-01", periods=n_months, freq="M").astype(str):
        _observe(tuner, month, {0: .01, 1: 1., 2: 2., 3: 3.})
    chosen, info = tuner.choose(KEY, "2021-04")
    assert chosen == tuning.DEFAULT_CANDIDATES["ridge"]
    assert info["reason"] == "fixed_default_insufficient_earlier_validation"
    assert len(info["validation_months"]) == n_months


def test_three_earlier_months_choose_best_candidate_on_all_area_rows():
    tuner = tuning.OnlineTuner()
    for month in ["2021-01", "2021-02", "2021-03"]:
        _observe(tuner, month, {0: [.1, .3], 1: [1., 1.], 2: [2., 2.], 3: [3., 3.]})
    chosen, info = tuner.choose(KEY, "2021-04")
    assert chosen == 0
    assert info["reason"] == "earlier_vintage_validation"
    assert info["validation_months"] == ["2021-01", "2021-02", "2021-03"]
    assert info["n_validation"] == 6
    assert info["candidate_mae"]["0"] == pytest.approx(.2)


def test_current_future_and_holdout_errors_cannot_change_a_past_choice():
    tuner = tuning.OnlineTuner()
    for month in ["2021-01", "2021-02", "2021-03"]:
        _observe(tuner, month, {0: .1, 1: 1., 2: 2., 3: 3.})
    before = tuner.choose(KEY, "2021-04")
    # All contamination would choose candidate 3 if those periods were used.
    for month in ["2021-04", "2021-05", "2024-12", "2025-01", "2026-09"]:
        _observe(tuner, month, {0: 10000., 1: 10000., 2: 10000., 3: 0.})
    after = tuner.choose(KEY, "2021-04")
    assert before == after
    assert not any(month >= "2021-04" for month in after[1]["validation_months"])


def test_unpublished_validation_outcomes_and_missing_dates_are_excluded():
    tuner = tuning.OnlineTuner()
    for month in ["2021-01", "2021-02"]:
        _observe(tuner, month, {0: .1, 1: 1., 2: 2., 3: 3.})
    _observe(tuner, "2021-03", {0: .1, 1: 1., 2: 2., 3: 3.},
             available_at=forecast_date("2021-04") + pd.Timedelta(days=1))
    chosen, info = tuner.choose(KEY, "2021-04")
    assert chosen == tuning.DEFAULT_CANDIDATES["ridge"]
    assert info["validation_months"] == ["2021-01", "2021-02"]
    # NaT is not a license to use an unavailable actual.
    unavailable = tuning.OnlineTuner()
    for month in ["2021-01", "2021-02", "2021-03"]:
        _observe(unavailable, month, {0: .1, 1: 1., 2: 2., 3: 3.}, available_at=pd.NaT)
    chosen, info = unavailable.choose(KEY, "2021-04")
    assert chosen == tuning.DEFAULT_CANDIDATES["ridge"]
    assert info["n_validation"] == 0


def test_candidate_cannot_win_merely_by_failing_on_difficult_rows():
    tuner = tuning.OnlineTuner()
    for month in ["2021-01", "2021-02", "2021-03"]:
        # Candidate 1's own mean is 2 versus candidate 0's 5.5, but it failed
        # on area 2. On the identical available area rows candidate 0 wins.
        _observe(tuner, month, {0: [1., 10.], 1: [2., 0.], 2: [20., 20.], 3: [30., 30.]},
                 missing={1: [2]})
    chosen, info = tuner.choose(KEY, "2021-04")
    assert chosen == 0
    assert info["n_validation"] == 3
    assert info["candidate_mae"]["0"] == 1.
    assert info["candidate_mae"]["1"] == 2.


def test_early_stopping_uses_earlier_vintage_and_public_labels_only(monkeypatch):
    class Store:
        months = ["2021-01", "2021-02", "2021-03", "2021-04", "2025-01"]

        def vintage(self, month):
            return pd.DataFrame({"forecast_month": [month], "marker": [f"own-{month}"]})

        def feature_sets(self, month):
            return {"drivers": ["biomass_anom_l1", "mobile_anom"]}

    calls = []

    def fake_early_stop(vintage, outcome, features, config, labels, **kwargs):
        calls.append((vintage.copy(), outcome, features, labels.copy(), kwargs))
        return {"iterations": 77, "reason": "synthetic_validation", "validation_month": "2021-03"}

    monkeypatch.setattr(tuning, "early_stop_iterations", fake_early_stop)
    targets = pd.DataFrame({"area": [1, 2, 1, 1], "month": ["2021-03", "2021-03", "2021-04", "2025-01"],
                            "available_at": [pd.Timestamp("2021-04-20"), pd.Timestamp("2021-05-11"),
                                             pd.Timestamp("2021-05-20"), pd.Timestamp("2025-02-20")]})
    key = ("available", "catboost", "drivers", "log_kg")
    config, info = tuning.candidate_config(Store(), key, 0, "2021-04", targets)
    assert config["iterations"] == info["iterations"] == 77
    vintage, outcome, features, labels, kwargs = calls[0]
    assert vintage.forecast_month.tolist() == ["2021-03"]
    assert vintage.marker.tolist() == ["own-2021-03"]
    assert labels.month.tolist() == ["2021-03"]
    assert labels.area.tolist() == [1]
    assert (labels.available_at <= forecast_date("2021-04")).all()
    assert kwargs["selection_month"] == "2021-04"


def test_catboost_cold_start_does_not_consult_current_target(monkeypatch):
    class Store:
        months = ["2021-01", "2021-02", "2025-01"]

        def vintage(self, month):
            raise AssertionError("Cold start must not load a scored target vintage for early stopping")

    monkeypatch.setattr(tuning, "early_stop_iterations", lambda *args, **kwargs: pytest.fail("must not early-stop on current target"))
    key = ("available", "catboost", "b1", "log_kg")
    config, info = tuning.candidate_config(Store(), key, 0, "2021-01", pd.DataFrame())
    assert config["iterations"] == 100
    assert info == {"reason": "fixed_cold_start", "iterations": 100, "validation_month": None}
