"""Scoring tests use constructed predictions and targets, never real holdout."""

import json

import numpy as np
import pandas as pd
import pytest
from scipy.stats import norm
import statsmodels.api as sm

from analysis.nowcast_evaluate import (
    ablation_summary, attach_actuals, contract_payload, registered_f1, summarize,
)


def _world(months=None, areas=(1, 2), window="dev"):
    months = months or ["2024-01", "2024-02", "2024-03"]
    targets, rows = [], []
    rng = np.random.default_rng(2026)
    for i, month in enumerate(months):
        made_on = (pd.Period(month, freq="M") + 1).to_timestamp() + pd.Timedelta(days=9)
        for area in areas:
            actual = 5 + .03 * i + .1 * area
            targets.append({"area": area, "month": month, "harvest_kg": np.exp(actual),
                            "harvest_count": np.exp(actual - 1), "avg_kg": np.e})
            for family in ["ols", "ridge", "catboost"]:
                for model in (["b0", "b1", "drivers"] if family == "ols" else ["b1", "drivers"]):
                    error = (.15 if model == "drivers" else .3) * (1 + rng.uniform(-.4, .4))
                    for outcome, truth in [("log_kg", actual), ("log_count", actual - 1), ("log_avg_kg", 1.)]:
                        predicted = truth - error
                        rows.append({"area": area, "month": month, "window": window, "made_on": made_on,
                                     "family": family, "model": model, "outcome": outcome,
                                     "predicted_log": predicted, "predicted_level": np.exp(predicted),
                                     "predicted_anomaly": .1, "base": predicted - .1,
                                     "eligible": True, "reason": "ok", "n_train": 70 + i,
                                     "rank": 4, "condition": 10.})
    return pd.DataFrame(rows), pd.DataFrame(targets)


def test_target_join_recomputes_logs_and_preserves_zero():
    predictions, targets = _world()
    targets.loc[(targets.area == 1) & (targets.month == "2024-01"), ["harvest_kg", "harvest_count"]] = 0.
    targets.loc[(targets.area == 1) & (targets.month == "2024-01"), "avg_kg"] = np.nan
    targets["log_kg"] = 999.  # Target helper must never trust precomputed logs.
    scored = attach_actuals(predictions, targets)
    zero = scored.loc[(scored.area == 1) & (scored.month == "2024-01") & (scored.outcome == "log_kg")]
    assert zero.actual_level.eq(0).all()
    assert zero.actual_log.isna().all()
    assert not zero.score_eligible.any()
    assert zero.score_reason.eq("zero_harvest_log_undefined").all()
    assert scored.loc[scored.score_eligible, "actual_log"].max() < 999


def test_duplicate_targets_rejected():
    predictions, targets = _world()
    with pytest.raises(ValueError, match="duplicate area-months"):
        attach_actuals(predictions, pd.concat([targets, targets.iloc[[0]]]))


def test_matched_and_available_scores_use_different_coverage():
    predictions, targets = _world()
    missing = ((predictions.family == "ols") & (predictions.model == "drivers")
               & (predictions.area == 1) & (predictions.month == "2024-01"))
    predictions.loc[missing, "eligible"] = False
    predictions.loc[missing, "reason"] = "missing_base"
    scored = attach_actuals(predictions, targets)
    result = summarize(scored)
    available = next(r for r in result["available"] if r["family"] == "ols" and r["model"] == "drivers" and r["outcome"] == "log_kg")
    matched = next(r for r in result["matched"] if r["left"] == "ols_b1" and r["right"] == "ols_drivers" and r["outcome"] == "log_kg")
    assert available["n_total"] == 6 and available["n_scored"] == 5
    assert matched["n_matched"] == 5
    assert any(r["area"] == 1 for r in result["by_area"])
    assert any(r["reason"] == "missing_base" for r in result["failures"])
    json.dumps(result, allow_nan=False)


def test_registered_f1_exact_monthly_hac_formula_and_ols_only():
    months = pd.period_range("2025-01", periods=8, freq="M").astype(str).tolist()
    predictions, targets = _world(months, areas=(1, 2, 3), window="holdout")
    scored = attach_actuals(predictions, targets)
    result = registered_f1(scored)
    b1 = scored.loc[(scored.family == "ols") & (scored.model == "b1") & (scored.outcome == "log_kg")]
    drivers = scored.loc[(scored.family == "ols") & (scored.model == "drivers") & (scored.outcome == "log_kg")]
    joined = b1.merge(drivers, on=["area", "month"], suffixes=("_b1", "_drivers"))
    e1 = joined.actual_log_b1 - joined.predicted_log_b1
    ed = joined.actual_log_drivers - joined.predicted_log_drivers
    f = e1 ** 2 - (ed ** 2 - (joined.predicted_log_b1 - joined.predicted_log_drivers) ** 2)
    monthly = f.groupby(joined.month).mean()
    fit = sm.OLS(monthly, np.ones(len(monthly))).fit(cov_type="HAC", cov_kwds={"maxlags": 3})
    assert result["mae_b1"] == pytest.approx(e1.abs().mean())
    assert result["mae_drivers"] == pytest.approx(ed.abs().mean())
    assert result["improvement_pct"] == pytest.approx(100 * (1 - ed.abs().mean() / e1.abs().mean()))
    assert result["cw_stat"] == pytest.approx(fit.tvalues.iloc[0])
    assert result["cw_p"] == pytest.approx(norm.sf(fit.tvalues.iloc[0]))
    assert result["pass"] == (result["improvement_pct"] >= 5 and result["cw_p"] < .05)
    altered = scored.copy()
    altered.loc[altered.family != "ols", "predicted_log"] = -1e5
    assert result == registered_f1(altered)


def test_f1_matches_rows_and_returns_null_when_months_too_few():
    predictions, targets = _world(["2025-01", "2025-02"], window="holdout")
    predictions.loc[(predictions.family == "ols") & (predictions.model == "drivers") & (predictions.area == 2), "eligible"] = False
    result = registered_f1(attach_actuals(predictions, targets))
    assert result["n_matched"] == 2
    assert result["n_months"] == 2
    assert result["cw_p"] is None and result["pass"] is None
    assert result["reason"] == "too_few_months_for_hac3"


def test_f1_degenerate_variance_never_exports_nonfinite_statistic():
    predictions, targets = _world(pd.period_range("2025-01", periods=6, freq="M").astype(str).tolist(), window="holdout")
    targets["harvest_kg"] = np.exp(3.)
    predictions.loc[predictions.model == "b1", "predicted_log"] = 1.
    predictions.loc[predictions.model == "drivers", "predicted_log"] = 2.
    result = registered_f1(attach_actuals(predictions, targets))
    assert result["reason"] == "degenerate_clark_west_variance"
    assert result["cw_p"] is None and result["pass"] is None
    json.dumps(result, allow_nan=False)


def test_contract_development_nulls_and_no_holdout_export():
    predictions, targets = _world()
    scored = attach_actuals(predictions, targets)
    payload = contract_payload(scored)
    assert set(payload) == {"models", "windows", "backtest", "scores", "f1", "latest", "current"}
    assert payload["f1"] is None and payload["latest"] is None and payload["scores"]["holdout"] is None
    assert set(payload["backtest"][0]["actual"]) == {"kg", "count", "avg_kg"}
    assert set(payload["backtest"][0]["pred"]) == {"b0", "b1", "drivers"}
    json.dumps(payload, allow_nan=False)
    bad = scored.copy()
    bad["window"] = "holdout"
    with pytest.raises(ValueError, match="holdout"):
        contract_payload(bad)


def test_latest_national_requires_all_thirteen_areas():
    predictions, targets = _world(["2026-09"], areas=tuple(range(1, 14)), window="holdout")
    scored = attach_actuals(predictions, targets)
    payload = contract_payload(scored, final=True, selected_model="drivers")
    latest = payload["latest"]
    assert latest["national"]["pred_kg"] == pytest.approx(sum(row["pred_kg"] for row in latest["areas"]))
    assert len(latest["areas"]) == 13
    scored.loc[(scored.family == "ols") & (scored.model == "drivers") & (scored.area == 13), "eligible"] = False
    incomplete = contract_payload(scored, final=True, selected_model="drivers")["latest"]
    assert incomplete["national"]["pred_kg"] is None
    assert incomplete["national"]["error_pct"] is None
    assert incomplete["national"]["actual_kg"] is not None
    json.dumps(incomplete, allow_nan=False)


def test_ablation_summary_matches_exact_rows():
    predictions, targets = _world()
    removed = predictions.loc[(predictions.family == "ols") & (predictions.model == "drivers")].copy()
    removed["model"] = "without_lice"
    removed["predicted_log"] -= .1
    scored = attach_actuals(pd.concat([predictions, removed], ignore_index=True), targets)
    rows = ablation_summary(scored)
    kg = next(r for r in rows if r["outcome"] == "log_kg")
    assert kg["group"] == "lice" and kg["n_matched"] == 6
    assert kg["mae_without"] > kg["full_mae"]
    assert kg["increase_pct"] == pytest.approx(100 * (kg["mae_without"] / kg["full_mae"] - 1))
