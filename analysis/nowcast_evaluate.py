"""Post-prediction scoring and production findings; never called by a fitter.

All comparisons identify the exact common area-months. The registered F1 test
uses OLS holdout forecasts only; challenger scores cannot change its decision.
"""

from itertools import combinations

import numpy as np
import pandas as pd
from scipy.stats import norm
import statsmodels.api as sm

from analysis.config import AREAS, DEVELOPMENT_WINDOW, HOLDOUT_WINDOW

OUTCOME_LEVELS = {"log_kg": "harvest_kg", "log_count": "harvest_count", "log_avg_kg": "avg_kg"}
DISPLAY_KEYS = {"log_kg": "kg", "log_count": "count", "log_avg_kg": "avg_kg"}
MODELS = ("b0", "b1", "drivers")
KEYS = ["area", "month", "outcome", "window"]
ACTUALS_NOTE = "latest revised data, not first releases"


def _number(value):
    if value is None or value is pd.NA or value is pd.NaT:
        return None
    return float(value) if np.isfinite(float(value)) else None


def _bool_series(frame, column, default=True):
    return frame[column].fillna(False).astype(bool) if column in frame else pd.Series(default, index=frame.index)


def _valid(frame):
    if frame.empty:
        return pd.Series(False, index=frame.index)
    if "score_eligible" in frame:
        return (_bool_series(frame, "score_eligible") & _bool_series(frame, "eligible")
                & np.isfinite(frame.predicted_log) & np.isfinite(frame.actual_log))
    return (_bool_series(frame, "eligible") & np.isfinite(frame.predicted_log)
            & np.isfinite(frame.actual_log))


def attach_actuals(predictions, targets):
    """Join separate targets after prediction, keeping genuine zero levels.

    Evaluation logs are recomputed from positive levels to prevent accidental
    log1p targets or a fabricated zero log at zero harvest from entering F1.
    """
    if targets.duplicated(["area", "month"]).any():
        raise ValueError("Evaluation targets contain duplicate area-months")
    required = {"area", "month", *OUTCOME_LEVELS.values()}
    missing = required - set(targets)
    if missing:
        raise ValueError(f"Evaluation targets lack columns: {sorted(missing)}")
    if predictions.duplicated(["family", "model", "outcome", "area", "month"]).any():
        raise ValueError("Predictions contain duplicate model/outcome/area/month rows")
    parts = []
    for outcome, level in OUTCOME_LEVELS.items():
        labels = targets[["area", "month", level]].copy().rename(columns={level: "actual_level"})
        labels["actual_log"] = np.log(labels.actual_level.where(labels.actual_level > 0))
        labels["outcome"] = outcome
        parts.append(labels)
    labels = pd.concat(parts, ignore_index=True)
    clean = predictions.drop(columns=[c for c in ["actual_log", "actual_level", "error", "abs_error", "score_eligible", "score_reason"] if c in predictions])
    result = clean.merge(labels, on=["area", "month", "outcome"], how="left", validate="many_to_one")
    finite = np.isfinite(result.predicted_log) & np.isfinite(result.actual_log)
    result["score_eligible"] = _bool_series(result, "eligible") & finite
    result["score_reason"] = result.get("reason", pd.Series("", index=result.index)).fillna("").astype(str)
    missing_label = ~np.isfinite(result.actual_log)
    result.loc[missing_label, "score_reason"] = "actual_unavailable"
    result.loc[result.actual_level == 0, "score_reason"] = "zero_harvest_log_undefined"
    result.loc[result.score_eligible, "score_reason"] = "ok"
    result["error"] = (result.actual_log - result.predicted_log).where(result.score_eligible)
    result["abs_error"] = result.error.abs()
    return result


def _score(frame):
    valid = _valid(frame)
    scored = frame.loc[valid]
    return {"n_total": int(len(frame)), "n_predicted": int((_bool_series(frame, "eligible") & np.isfinite(frame.predicted_log)).sum()),
            "n_scored": int(valid.sum()), "coverage": _number(valid.mean()) if len(frame) else None,
            "mae": _number((scored.actual_log - scored.predicted_log).abs().mean()) if len(scored) else None}


def _group_scores(frame, columns):
    rows = []
    for keys, group in frame.groupby(columns, sort=True, dropna=False):
        keys = keys if isinstance(keys, tuple) else (keys,)
        row = dict(zip(columns, [int(x) if isinstance(x, (int, np.integer)) else str(x) for x in keys]))
        row.update(_score(group))
        rows.append(row)
    return rows


def _pair(frame, left_family, left_model, right_family, right_model):
    left = frame.loc[(frame.family == left_family) & (frame.model == left_model) & _valid(frame)]
    right = frame.loc[(frame.family == right_family) & (frame.model == right_model) & _valid(frame)]
    return left.merge(right, on=KEYS, suffixes=("_left", "_right"), validate="one_to_one")


def _matched_summary(frame, left_family, left_model, right_family, right_model, comparison):
    joined = _pair(frame, left_family, left_model, right_family, right_model)
    rows = []
    # Include empty comparisons explicitly for each advertised outcome/window.
    for (window, outcome), _ in frame.groupby(["window", "outcome"], sort=True):
        sample = joined.loc[(joined.window == window) & (joined.outcome == outcome)]
        left_mae = _number((sample.actual_log_left - sample.predicted_log_left).abs().mean()) if len(sample) else None
        right_mae = _number((sample.actual_log_right - sample.predicted_log_right).abs().mean()) if len(sample) else None
        improvement = 100 * (1 - right_mae / left_mae) if left_mae is not None and left_mae > 0 and right_mae is not None else None
        rows.append({"comparison": comparison, "window": str(window), "outcome": str(outcome),
                     "left": f"{left_family}_{left_model}", "right": f"{right_family}_{right_model}",
                     "n_matched": len(sample), "mae_left": left_mae, "mae_right": right_mae,
                     "right_improvement_pct": _number(improvement),
                     "months": sorted(sample.month.unique().tolist()),
                     "areas": sorted(int(a) for a in sample.area.unique())})
    return rows


def summarize(predictions):
    """Available-sample losses, matched comparisons, diagnostics and coverage."""
    frame = predictions.copy()
    columns = ["window", "family", "model", "outcome"]
    if frame.empty:
        return {"available": [], "by_year": [], "by_area": [], "failures": [], "training": [], "matched": []}
    frame["year"] = frame.month.astype(str).str[:4]
    reasons = frame.get("score_reason", frame.get("reason", pd.Series("unknown", index=frame.index))).fillna("unknown")
    failures = frame.loc[~_valid(frame)].assign(failure_reason=reasons.loc[~_valid(frame)])
    failure_rows = []
    for keys, group in failures.groupby([*columns, "failure_reason"], sort=True):
        row = dict(zip([*columns, "reason"], keys))
        row["n"] = int(len(group))
        failure_rows.append(row)
    training = []
    for keys, group in frame.groupby(columns, sort=True):
        row = dict(zip(columns, keys))
        for col in ["n_train", "rank", "condition", "n_parameters"]:
            if col in group:
                values = pd.to_numeric(group[col], errors="coerce")
                row[col + "_min"] = _number(values.min())
                row[col + "_median"] = _number(values.median())
                row[col + "_max"] = _number(values.max())
        training.append(row)
    matched = []
    families = sorted(frame.family.unique())
    for family in families:
        if {"b1", "drivers"} <= set(frame.loc[frame.family == family, "model"]):
            matched += _matched_summary(frame, family, "b1", family, "drivers", "biological_drivers")
    for left, right in combinations(families, 2):
        common = sorted(set(frame.loc[frame.family == left, "model"]) & set(frame.loc[frame.family == right, "model"]))
        for model in common:
            matched += _matched_summary(frame, left, model, right, model, "estimator_same_features")
    return {"available": _group_scores(frame, columns), "by_year": _group_scores(frame, [*columns, "year"]),
            "by_area": _group_scores(frame, [*columns, "area"]), "failures": failure_rows,
            "training": training, "matched": matched,
            "notes": ["Available results use each model's own eligible rows; matched results use identical area-months.",
                      "CatBoost may use additional training rows with missing predictors; identical feature names do not imply identical training samples."]}


def registered_f1(predictions):
    """OLS F1 on holdout matched area-months; HAC is applied to monthly means."""
    frame = predictions.loc[(predictions.family == "ols") & (predictions.window == "holdout")
                            & (predictions.outcome == "log_kg")]
    matched = _pair(frame, "ols", "b1", "ols", "drivers")
    result = {"window": "holdout", "mae_b1": None, "mae_drivers": None, "improvement_pct": None,
              "cw_stat": None, "cw_p": None, "pass": None, "n_matched": len(matched), "n_months": 0,
              "reason": "no_matched_rows"}
    if matched.empty:
        return result
    if not np.allclose(matched.actual_log_left, matched.actual_log_right):
        raise ValueError("Matched models disagree on actual outcomes")
    e_b1 = matched.actual_log_left - matched.predicted_log_left
    e_drivers = matched.actual_log_right - matched.predicted_log_right
    mae_b1, mae_drivers = float(e_b1.abs().mean()), float(e_drivers.abs().mean())
    result.update(mae_b1=mae_b1, mae_drivers=mae_drivers)
    if mae_b1 <= 0:
        result["reason"] = "zero_baseline_mae"
        return result
    improvement = 100 * (1 - mae_drivers / mae_b1)
    result["improvement_pct"] = improvement
    adjustment = (matched.predicted_log_left - matched.predicted_log_right) ** 2
    monthly = (e_b1 ** 2 - (e_drivers ** 2 - adjustment)).groupby(matched.month).mean().sort_index()
    result["n_months"] = len(monthly)
    if len(monthly) < 5:
        result["reason"] = "too_few_months_for_hac3"
        return result
    if np.ptp(monthly.to_numpy()) == 0:
        result["reason"] = "degenerate_clark_west_variance"
        return result
    fit = sm.OLS(monthly.to_numpy(), np.ones((len(monthly), 1))).fit(cov_type="HAC", cov_kwds={"maxlags": 3})
    statistic = _number(fit.tvalues[0])
    if statistic is None:
        result["reason"] = "nonfinite_clark_west_statistic"
        return result
    p = float(norm.sf(statistic))
    result.update(cw_stat=statistic, cw_p=p, **{"pass": bool(improvement >= 5 and p < .05)}, reason="ok")
    return result


def _registered_scores(frame, window):
    """All three registered models share each outcome's scoring sample."""
    result = {outcome: {model: None for model in MODELS} for outcome in OUTCOME_LEVELS}
    for outcome in OUTCOME_LEVELS:
        subset = frame.loc[(frame.window == window) & (frame.outcome == outcome) & _valid(frame)]
        eligible = subset.pivot(index=["area", "month"], columns="model", values="predicted_log").reindex(columns=MODELS)
        common = eligible.dropna()
        if common.empty:
            continue
        actual = subset.drop_duplicates(["area", "month"]).set_index(["area", "month"]).actual_log.reindex(common.index)
        for model in MODELS:
            result[outcome][model] = _number((actual - common[model]).abs().mean())
    return result


def _date_string(value):
    if value is None or pd.isna(value):
        return None
    return pd.Timestamp(value).date().isoformat()


def _latest(frame, selected_model=None):
    if selected_model is not None and selected_model not in MODELS:
        raise ValueError("latest selected_model must be a registered OLS model")
    if selected_model is None:
        f1 = registered_f1(frame)
        selected_model = "b1" if (f1["mae_b1"] is not None and f1["mae_drivers"] is not None
                                  and f1["mae_b1"] < f1["mae_drivers"]) else "drivers"
    sample = frame.loc[(frame.month == HOLDOUT_WINDOW.end) & (frame.outcome == "log_kg")
                       & (frame.model == selected_model) & (frame.family == "ols")].set_index("area")
    areas = []
    for area in AREAS:
        if area not in sample.index:
            areas.append({"area": area, "pred_kg": None, "actual_kg": None, "error_pct": None})
            continue
        row = sample.loc[area]
        predicted = _number(row.predicted_level) if bool(row.eligible) else None
        actual = _number(row.actual_level)
        error = 100 * (predicted - actual) / actual if predicted is not None and actual is not None and actual > 0 else None
        areas.append({"area": area, "pred_kg": predicted, "actual_kg": actual, "error_pct": _number(error)})
    complete_pred = all(row["pred_kg"] is not None for row in areas)
    complete_actual = all(row["actual_kg"] is not None for row in areas)
    pred_total = sum(row["pred_kg"] for row in areas) if complete_pred else None
    actual_total = sum(row["actual_kg"] for row in areas) if complete_actual else None
    error = 100 * (pred_total - actual_total) / actual_total if pred_total is not None and actual_total is not None and actual_total > 0 else None
    return {"month": HOLDOUT_WINDOW.end, "made_on": "2026-10-10", "model": selected_model,
            "national": {"pred_kg": _number(pred_total), "actual_kg": _number(actual_total), "error_pct": _number(error)},
            "areas": areas}


def contract_payload(predictions, final=False, selected_model=None):
    """Return the shared nowcast.json schema, rejecting accidental holdout export."""
    if not final and ((predictions.window == "holdout") | (predictions.month > DEVELOPMENT_WINDOW.end)).any():
        raise ValueError("Development payload cannot contain holdout predictions")
    frame = predictions.loc[predictions.family == "ols"].copy()
    rows = []
    for (area, month, window), group in frame.groupby(["area", "month", "window"], sort=True):
        record = {"area": int(area), "month": str(month), "window": str(window),
                  "made_on": _date_string(group.made_on.iloc[0]),
                  "actual": {key: None for key in DISPLAY_KEYS.values()},
                  "pred": {model: {key: None for key in DISPLAY_KEYS.values()} for model in MODELS}}
        for row in group.itertuples(index=False):
            key = DISPLAY_KEYS[row.outcome]
            record["actual"][key] = _number(row.actual_level)
            if row.model in MODELS and bool(row.eligible):
                record["pred"][row.model][key] = _number(row.predicted_level)
        rows.append(record)
    return {"models": list(MODELS),
            "windows": {"dev": [DEVELOPMENT_WINDOW.start, DEVELOPMENT_WINDOW.end],
                        "holdout": [HOLDOUT_WINDOW.start, HOLDOUT_WINDOW.end]},
            "backtest": rows,
            "scores": {"dev": _registered_scores(frame, "dev"),
                       "holdout": _registered_scores(frame, "holdout") if final else None,
                       "actuals": ACTUALS_NOTE},
            "f1": registered_f1(frame) if final else None,
            "latest": _latest(frame, selected_model) if final else None,
            "current": None}


def ablation_summary(predictions, full_model="drivers"):
    """Registered OLS driver ablations on matched full/removed-group rows."""
    frame = predictions.loc[predictions.family == "ols"]
    groups = []
    for model in sorted(frame.model.unique()):
        if not str(model).startswith("without_"):
            continue
        joined = _pair(frame, "ols", full_model, "ols", model)
        for outcome in OUTCOME_LEVELS:
            rows = joined.loc[joined.outcome == outcome]
            full = _number((rows.actual_log_left - rows.predicted_log_left).abs().mean()) if len(rows) else None
            without = _number((rows.actual_log_right - rows.predicted_log_right).abs().mean()) if len(rows) else None
            increase = 100 * (without / full - 1) if full is not None and full > 0 and without is not None else None
            groups.append({"group": str(model)[len("without_"):], "outcome": outcome, "n_matched": len(rows),
                           "full_mae": full, "mae_without": without, "increase_pct": _number(increase)})
    return groups
