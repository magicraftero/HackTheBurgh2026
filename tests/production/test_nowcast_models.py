"""Estimator isolation, reconstruction, and numerical failure checks."""

import json

import numpy as np
import pandas as pd
import pytest

from analysis.nowcast_inputs import forecast_date
from analysis.nowcast_models import early_stop_iterations, fit_predict


def vintage_fixture(target="2021-01", periods=36):
    rng = np.random.default_rng(7)
    months = pd.period_range(end=pd.Period(target) - 1, periods=periods, freq="M").astype(str).tolist()
    rows = []
    for month in months + [target]:
        for area in (1, 2, 13):
            x, z = rng.normal(size=2)
            is_target = month == target
            rows.append({"area": area, "month": month, "forecast_month": target,
                         "made_on": forecast_date(target), "is_target": is_target,
                         "x": x, "z": z, "log_kg_anom": np.nan if is_target else 1 + 2*x - .5*z,
                         "log_kg_base": 5.,
                         "label_available_at": pd.NaT if is_target else (pd.Period(month) + 1).to_timestamp() + pd.Timedelta(days=19),
                         "feature_available_at": forecast_date(month)})
    return pd.DataFrame(rows)


def test_ols_has_intercept_and_reconstructs_predictions():
    vintage = vintage_fixture()
    result = fit_predict(vintage, "log_kg", ["x", "z"], "ols")
    expected = 1 + 2*vintage.loc[vintage.is_target, "x"].to_numpy() - .5*vintage.loc[vintage.is_target, "z"].to_numpy()
    assert result.eligible.all()
    np.testing.assert_allclose(result.predicted_anomaly, expected, atol=1e-12)
    np.testing.assert_allclose(result.predicted_log, expected + 5)
    np.testing.assert_allclose(result.predicted_level, np.exp(expected + 5))


def test_target_labels_never_enter_any_estimator():
    vintage = vintage_fixture()
    poisoned = vintage.copy()
    poisoned.loc[poisoned.is_target, "log_kg_anom"] = 1e30
    for family, config in [("ols", {}), ("ridge", {"alpha": 1.}),
                           ("catboost", {"iterations": 20, "depth": 3})]:
        original = fit_predict(vintage, "log_kg", ["x", "z"], family, config)
        modified = fit_predict(poisoned, "log_kg", ["x", "z"], family, config)
        pd.testing.assert_frame_equal(original, modified)


def test_scaler_uses_published_training_rows_only_even_with_mask():
    vintage = vintage_fixture()
    # A fake future historical row cannot be admitted by an external mask.
    future = vintage.iloc[[0]].copy()
    future["month"] = "2021-02"
    future["x"] = 1e10
    future["z"] = 1e10
    with_future = pd.concat([vintage, future], ignore_index=True)
    with_future.loc[with_future.is_target, ["x", "z"]] = 1000
    result = fit_predict(with_future, "log_kg", ["x", "z"], "ridge", {"alpha": 1.},
                         training_mask=np.ones(len(with_future), dtype=bool))
    train = vintage.loc[~vintage.is_target]
    np.testing.assert_allclose(json.loads(result.scaler_mean.iloc[0]), train[["x", "z"]].mean().to_numpy())
    assert result.n_train.eq(len(train)).all()


def test_unpublished_labels_and_predictors_are_excluded():
    vintage = vintage_fixture()
    train_index = vintage.index[~vintage.is_target]
    vintage.loc[train_index[0], "label_available_at"] = forecast_date("2021-02")
    vintage.loc[train_index[1], "feature_available_at"] = forecast_date("2021-02")
    result = fit_predict(vintage, "log_kg", ["x", "z"], "ridge")
    assert result.n_train.eq(len(train_index)-2).all()


def test_catboost_native_missingness_and_common_training_only_restriction():
    vintage = vintage_fixture()
    vintage.loc[vintage.index[~vintage.is_target][::4], "x"] = np.nan
    vintage.loc[vintage.is_target & (vintage.area == 2), "x"] = np.nan
    native = fit_predict(vintage, "log_kg", ["x", "z"], "catboost", {"iterations": 20})
    matched = fit_predict(vintage, "log_kg", ["x", "z"], "catboost", {"iterations": 20}, sample_features=["x", "z"])
    linear = fit_predict(vintage, "log_kg", ["x", "z"], "ridge")
    assert native.n_train.iloc[0] > matched.n_train.iloc[0]
    assert matched.n_train.iloc[0] == linear.n_train.iloc[0]
    assert matched.loc[matched.area == 2, "eligible"].all()
    assert not linear.loc[linear.area == 2, "eligible"].any()


def test_sparse_area_base_is_unavailable_and_missing_predictors_explicit():
    vintage = vintage_fixture()
    vintage.loc[vintage.is_target & (vintage.area == 13), "log_kg_base"] = np.nan
    vintage.loc[vintage.is_target & (vintage.area == 1), "x"] = np.nan
    result = fit_predict(vintage, "log_kg", ["x", "z"], "ols").set_index("area")
    assert result.loc[13, "reason"] == "missing_base"
    assert result.loc[1, "reason"] == "missing_predictors"
    assert result.loc[2, "eligible"]


def test_rank_deficiency_rejected_for_ols_but_regularized_ridge_can_fit():
    vintage = vintage_fixture()
    vintage["z"] = vintage.x
    ols = fit_predict(vintage, "log_kg", ["x", "z"], "ols")
    ridge = fit_predict(vintage, "log_kg", ["x", "z"], "ridge")
    assert ols.reason.eq("rank_deficient").all()
    assert not ols.eligible.any()
    assert ridge.eligible.all()


def test_insufficient_training_and_overflow_are_not_clipped():
    small = vintage_fixture(periods=1)
    result = fit_predict(small, "log_kg", ["x", "z"], "ridge")
    assert result.reason.eq("insufficient_training").all()
    vintage = vintage_fixture()
    vintage.loc[vintage.is_target, "log_kg_base"] = 1000.
    result = fit_predict(vintage, "log_kg", ["x", "z"], "ols")
    assert result.reason.eq("level_overflow_or_underflow").all()
    assert not result.eligible.any()
    assert (result.predicted_log > 900).all()
    assert result.predicted_level.isna().all()


def test_early_stopping_uses_earlier_own_vintage_and_published_validation_labels():
    vintage = vintage_fixture()
    target = vintage.loc[vintage.is_target, ["area", "month", "x", "z"]].copy()
    target["log_kg"] = 6 + 2*target.x - .5*target.z
    target["available_at"] = pd.Timestamp("2021-02-20")
    config = {"iterations": 30, "depth": 3, "early_stopping_rounds": 5}
    info = early_stop_iterations(vintage, "log_kg", ["x", "z"], config, target, selection_month="2021-02")
    assert 1 <= info["iterations"] <= 30
    assert info["n_validation"] == 3
    delayed = vintage.copy()
    delayed.loc[delayed.is_target, "feature_available_at"] = forecast_date("2021-01") + pd.Timedelta(days=1)
    excluded = early_stop_iterations(delayed, "log_kg", ["x", "z"], config, target, selection_month="2021-02")
    assert excluded["n_validation"] == 0
    # January actuals are not public at the January nowcast itself.
    with pytest.raises(ValueError, match="must precede"):
        early_stop_iterations(vintage, "log_kg", ["x", "z"], config, target, selection_month="2021-01")
    target["available_at"] = pd.Timestamp("2021-04-20")
    info = early_stop_iterations(vintage, "log_kg", ["x", "z"], config, target, selection_month="2021-02")
    assert info["reason"] == "no_validation_labels_or_base"


def test_cannot_concatenate_vintages_or_stop_on_scored_target():
    first = vintage_fixture("2021-01")
    second = vintage_fixture("2021-02")
    with pytest.raises(ValueError, match="one forecast vintage"):
        fit_predict(pd.concat([first, second]), "log_kg", ["x", "z"], "ridge")
    with pytest.raises(ValueError, match="earlier validation vintage"):
        fit_predict(first, "log_kg", ["x", "z"], "catboost", validation=first)


def test_catboost_fit_errors_become_recorded_unavailable_predictions():
    vintage = vintage_fixture()
    vintage[["x", "z"]] = 0.
    predicted = fit_predict(vintage, "log_kg", ["x", "z"], "catboost", {"iterations": 5})
    assert predicted.reason.eq("fit_error").all()
    assert not predicted.eligible.any()
    target = vintage.loc[vintage.is_target, ["area", "month"]].copy()
    target["log_kg"] = 6.
    target["available_at"] = pd.Timestamp("2021-02-20")
    info = early_stop_iterations(vintage, "log_kg", ["x", "z"], {"iterations": 5}, target,
                                  selection_month="2021-02")
    assert info["reason"] == "fit_error"
