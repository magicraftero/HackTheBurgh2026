"""Pooled prediction estimators, with no access to scoring-period labels.

Feature definitions belong to :mod:`analysis.nowcast_inputs`. This module
changes the estimator, not the information supplied to it. In particular,
CatBoost receives the same numerical columns as Ridge and OLS; area is omitted.
"""

from __future__ import annotations

import json
from typing import Any

import numpy as np
import pandas as pd

from analysis.nowcast_inputs import forecast_date

SEED = 2026
MIN_ROWS_PER_PARAMETER = 3
OLS_CONDITION_LIMIT = 1e12


def _configuration(config: dict | None) -> dict:
    return dict(config or {})


def _vintage_parts(vintage: pd.DataFrame, outcome: str, features: list[str],
                   family: str, training_mask=None, sample_features=None):
    """Select one vintage and publication-eligible historical training rows."""
    if family not in {"ols", "ridge", "catboost"}:
        raise ValueError(f"Unknown nowcast estimator: {family}")
    required = {"area", "month", "forecast_month", "made_on", "is_target",
                outcome + "_anom", outcome + "_base", "label_available_at",
                "feature_available_at", *features, *(sample_features or [])}
    missing = required - set(vintage)
    if missing:
        raise ValueError(f"Vintage missing columns: {sorted(missing)}")
    origins = vintage.forecast_month.dropna().astype(str).unique()
    dates = pd.to_datetime(vintage.made_on).dropna().unique()
    if len(origins) != 1 or len(dates) != 1:
        raise ValueError("Fit exactly one forecast vintage at a time")
    origin = str(origins[0])
    made_on = pd.Timestamp(dates[0])
    if made_on > forecast_date(origin):
        raise ValueError("Vintage publication cutoff exceeds its forecast date")
    target = vintage.loc[vintage.is_target.astype(bool)].copy()
    if not target.month.astype(str).eq(origin).all():
        raise ValueError("Target rows disagree with forecast_month")
    if target.area.duplicated().any():
        raise ValueError("Duplicate target area in vintage")
    numeric = vintage[features].astype(float)
    finite_label = np.isfinite(vintage[outcome + "_anom"].astype(float))
    mask = (~vintage.is_target.astype(bool) & vintage.month.astype(str).lt(origin)
            & finite_label
            & pd.to_datetime(vintage.label_available_at).le(made_on)
            & pd.to_datetime(vintage.feature_available_at).le(made_on))
    if family == "catboost":
        # Native numerical missingness is allowed; infinities are not.
        mask &= ~np.isinf(numeric).any(axis=1)
    else:
        mask &= np.isfinite(numeric).all(axis=1)
    if sample_features:
        mask &= np.isfinite(vintage[list(sample_features)].astype(float)).all(axis=1)
    if training_mask is not None:
        supplied = (training_mask.reindex(vintage.index).fillna(False)
                    if isinstance(training_mask, pd.Series)
                    else pd.Series(training_mask, index=vintage.index))
        mask &= supplied.astype(bool)
    return vintage.loc[mask].copy(), target, origin, made_on


def _design_diagnostics(values: np.ndarray):
    # Missing values are excluded only for this numerical diagnostic; CatBoost
    # still trains on all its eligible rows and handles the NaNs natively.
    finite = values[np.isfinite(values).all(axis=1)]
    if not len(finite):
        return 0, np.nan
    design = np.column_stack([np.ones(len(finite)), finite])
    rank = int(np.linalg.matrix_rank(design))
    condition = float(np.linalg.cond(design))
    return rank, condition


def _catboost(config: dict):
    from catboost import CatBoostRegressor
    return CatBoostRegressor(
        iterations=int(config.get("iterations", 250)),
        depth=int(config.get("depth", 3)),
        learning_rate=float(config.get("learning_rate", .03)),
        l2_leaf_reg=float(config.get("l2_leaf_reg", 10.)),
        loss_function="RMSE", eval_metric="MAE",
        random_seed=int(config.get("seed", SEED)),
        thread_count=1, allow_writing_files=False, verbose=False,
        nan_mode="Min",
    )


def fit_predict(vintage: pd.DataFrame, outcome: str, features: list[str],
                family: str, config: dict | None = None, *, training_mask=None,
                sample_features=None, validation=None) -> pd.DataFrame:
    """Return every target row, including explicit unavailable predictions.

    ``sample_features`` applies an additional complete-case restriction to
    TRAINING rows only. It allows the registered nested OLS comparison and
    algorithm comparisons to share exactly the same training observations.
    ``training_mask`` can further restrict training but cannot override the
    date and publication guards. Target labels are never read.

    CatBoost early stopping is intentionally a separate function, so a scored
    target cannot accidentally become an evaluation set. Pass fixed iterations
    selected by :func:`early_stop_iterations` on earlier validation vintages.
    """
    if validation is not None:
        raise ValueError("Use early_stop_iterations on an earlier validation vintage, never the scored target")
    config = _configuration(config)
    train, target, origin, made_on = _vintage_parts(
        vintage, outcome, features, family, training_mask, sample_features)
    values = train[features].to_numpy(dtype=float)
    y = train[outcome + "_anom"].to_numpy(dtype=float)
    n_parameters = len(features) + 1
    minimum = max(n_parameters + 1, int(config.get("min_train", MIN_ROWS_PER_PARAMETER * n_parameters)))
    rank, condition = _design_diagnostics(values)
    result = target[["area", "month", "forecast_month", "made_on"]].reset_index(drop=True)
    result["base"] = target[outcome + "_base"].to_numpy(dtype=float)
    for name in ("predicted_anomaly", "predicted_log", "predicted_level"):
        result[name] = np.nan
    result["eligible"] = False
    result["reason"] = ""
    result["n_train"] = len(train)
    result["n_parameters"] = n_parameters
    result["rank"] = rank
    result["condition"] = condition
    result["minimum_training_rows"] = minimum
    result["iterations"] = int(config.get("iterations", 250)) if family == "catboost" else 0
    result["configuration"] = json.dumps(config, sort_keys=True, allow_nan=False)
    result["scaler_mean"] = "[]"
    result["scaler_scale"] = "[]"
    result.attrs["diagnostics"] = {"training_months": sorted(train.month.unique().tolist()),
                                    "n_train": len(train), "minimum_training_rows": minimum,
                                    "rank": rank, "condition": condition,
                                    "area_feature_included": False}
    tx = target[features].to_numpy(dtype=float)
    valid = np.isfinite(result.base.to_numpy())
    result.loc[~valid, "reason"] = "missing_base"
    target_finite = ~np.isinf(tx).any(axis=1) if family == "catboost" else np.isfinite(tx).all(axis=1)
    result.loc[valid & ~target_finite, "reason"] = "missing_predictors" if family != "catboost" else "nonfinite_predictors"
    valid &= target_finite
    public = pd.to_datetime(target.feature_available_at).le(made_on).to_numpy()
    result.loc[valid & ~public, "reason"] = "unpublished_predictors"
    valid &= public
    failure = None
    if len(train) < minimum:
        failure = "insufficient_training"
    elif family == "ols" and rank < n_parameters:
        failure = "rank_deficient"
    elif family == "ols" and (not np.isfinite(condition) or condition > OLS_CONDITION_LIMIT):
        failure = "ill_conditioned"
    if failure:
        result.loc[valid, "reason"] = failure
        return result
    if not valid.any():
        return result
    fit_errors = (ValueError, np.linalg.LinAlgError)
    if family == "catboost":
        from catboost import CatBoostError
        fit_errors += (CatBoostError,)
    try:
        if family == "ols":
            import statsmodels.api as sm
            design = np.column_stack([np.ones(len(train)), values])
            model = sm.OLS(y, design).fit()
            predicted = model.predict(np.column_stack([np.ones(int(valid.sum())), tx[valid]]))
        elif family == "ridge":
            from sklearn.linear_model import Ridge
            from sklearn.preprocessing import StandardScaler
            scaler = StandardScaler().fit(values)
            model = Ridge(alpha=float(config.get("alpha", 10.)), fit_intercept=True, solver="svd")
            model.fit(scaler.transform(values), y)
            predicted = model.predict(scaler.transform(tx[valid]))
            result["scaler_mean"] = json.dumps(scaler.mean_.tolist(), allow_nan=False)
            result["scaler_scale"] = json.dumps(scaler.scale_.tolist(), allow_nan=False)
            result.attrs["diagnostics"]["scaler_mean"] = scaler.mean_.tolist()
            result.attrs["diagnostics"]["scaler_scale"] = scaler.scale_.tolist()
        else:
            model = _catboost(config)
            model.fit(values, y)
            predicted = model.predict(tx[valid])
    except fit_errors as error:
        result.loc[valid, "reason"] = "fit_error"
        result.attrs["diagnostics"]["fit_error"] = str(error)
        return result
    positions = np.flatnonzero(valid)
    predicted = np.asarray(predicted, dtype=float)
    logs = predicted + result.loc[valid, "base"].to_numpy()
    with np.errstate(over="ignore", under="ignore", invalid="ignore"):
        levels = np.exp(logs)
    result.loc[positions, "predicted_anomaly"] = predicted
    result.loc[positions, "predicted_log"] = logs
    result.loc[positions, "predicted_level"] = levels
    finite = np.isfinite(predicted) & np.isfinite(logs)
    level_finite = np.isfinite(levels) & (levels > 0)
    result.loc[positions[~finite], "reason"] = "nonfinite_prediction"
    result.loc[positions[finite & ~level_finite], "reason"] = "level_overflow_or_underflow"
    result.loc[positions[finite & level_finite], "eligible"] = True
    # Infinity is not serializable as strict JSON and does not constitute an
    # available reconstructed prediction. Preserve finite extreme values.
    result["predicted_level"] = result.predicted_level.where(np.isfinite(result.predicted_level))
    return result


def early_stop_iterations(vintage: pd.DataFrame, outcome: str, features: list[str],
                          config: dict, validation_targets: pd.DataFrame, *,
                          selection_month: str, sample_features=None) -> dict[str, Any]:
    """Choose CatBoost iterations using one EARLIER origin's own vintage.

    The caller must supply actual log outcomes only for this historical
    validation month. Selection can occur after those outcomes were published,
    and must precede the current scored origin. Training and validation use
    that earlier vintage's seasonal adjustment, not the outer vintage's fit.
    """
    train, target, origin, made_on = _vintage_parts(vintage, outcome, features, "catboost", sample_features=sample_features)
    if pd.Period(origin, freq="M") >= pd.Period(selection_month, freq="M"):
        raise ValueError("Early-stopping vintage must precede the scored selection month")
    required = {"area", "month", "available_at", outcome}
    if required - set(validation_targets):
        raise ValueError(f"Validation targets missing {sorted(required - set(validation_targets))}")
    labels = validation_targets.loc[validation_targets.month.astype(str).eq(origin)].copy()
    labels = labels.loc[pd.to_datetime(labels.available_at) <= forecast_date(selection_month)]
    joined = target.merge(labels[["area", "month", outcome]], on=["area", "month"], how="left", validate="one_to_one")
    finite = np.isfinite(joined[outcome].astype(float)) & np.isfinite(joined[outcome + "_base"].astype(float))
    finite &= ~np.isinf(joined[features].to_numpy(dtype=float)).any(axis=1)
    finite &= pd.to_datetime(joined.feature_available_at).le(made_on)
    validation = joined.loc[finite]
    minimum = max(len(features) + 2, int(config.get("min_train", MIN_ROWS_PER_PARAMETER * (len(features) + 1))))
    info = {"iterations": int(config.get("iterations", 250)), "n_train": len(train),
            "n_validation": len(validation), "reason": "", "validation_month": origin,
            "selection_month": str(selection_month)}
    if len(train) < minimum:
        info["reason"] = "insufficient_training"
        return info
    if validation.empty:
        info["reason"] = "no_validation_labels_or_base"
        return info
    from catboost import CatBoostError
    try:
        model = _catboost(config)
        model.fit(train[features].to_numpy(dtype=float), train[outcome + "_anom"].to_numpy(dtype=float),
                  eval_set=(validation[features].to_numpy(dtype=float),
                            validation[outcome].to_numpy(dtype=float) - validation[outcome + "_base"].to_numpy(dtype=float)),
                  early_stopping_rounds=int(config.get("early_stopping_rounds", 30)), use_best_model=True)
    except (ValueError, CatBoostError) as error:
        info["reason"] = "fit_error"
        info["fit_error"] = str(error)
        return info
    best = model.get_best_iteration()
    info["iterations"] = int(best + 1) if best >= 0 else int(model.tree_count_)
    return info
