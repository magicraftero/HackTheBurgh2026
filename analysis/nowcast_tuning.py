"""Small, chronological challenger searches using earlier origins' own fits."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from analysis.nowcast_inputs import forecast_date
from analysis.nowcast_models import early_stop_iterations

SEED = 2026
RIDGE_GRID = [{"alpha": value} for value in [.1, 1., 10., 100.]]
CATBOOST_GRID = [
    {"depth": 3, "l2_leaf_reg": 10., "learning_rate": .04, "iterations": 200,
     "early_stopping_rounds": 20, "seed": SEED},
    {"depth": 4, "l2_leaf_reg": 20., "learning_rate": .04, "iterations": 200,
     "early_stopping_rounds": 20, "seed": SEED},
]
GRIDS = {"ridge": RIDGE_GRID, "catboost": CATBOOST_GRID}
DEFAULT_CANDIDATES = {"ridge": 2, "catboost": 0}
VALIDATION_MONTHS = 12
MIN_VALIDATION_MONTHS = 3


def month_partition(month):
    """Partition calendar months, never individual area rows."""
    month = str(pd.Period(month, freq="M"))
    if "2017-10" <= month <= "2024-12":
        return "train_dev"
    if "2025-01" <= month <= "2026-09":
        return "holdout"
    return "outside"


def validation_months(months, selection_month):
    """At most 12 earlier whole months, restricted to registered development."""
    return tuple(sorted({str(m) for m in months
                         if "2021-01" <= str(m) < str(selection_month) and str(m) <= "2024-12"})[-VALIDATION_MONTHS:])


class OnlineTuner:
    """Cache each candidate's one-month-ahead validation fold once.

    Each cached prediction was trained on its own historical vintage. Later
    scored months may select from earlier published validation errors only;
    their own errors are added after the predictions have been generated.
    """

    def __init__(self):
        self.history = {}
        self.decisions = []

    def observe(self, key, candidate, scored, targets):
        # Copy only the evaluation fields required for chronological selection.
        rows = scored[["area", "month", "predicted_log", "actual_log", "score_eligible"]].copy()
        rows = rows.merge(targets[["area", "month", "available_at"]], on=["area", "month"], how="left", validate="many_to_one")
        rows["candidate"] = int(candidate)
        rows["loss"] = (rows.predicted_log - rows.actual_log).abs()
        self.history.setdefault(tuple(key), []).append(rows)

    def choose(self, key, selection_month):
        track, family, model, outcome = key
        chosen = DEFAULT_CANDIDATES[family]
        pieces = self.history.get(tuple(key), [])
        info = {"track": track, "family": family, "model": model, "outcome": outcome,
                "selection_month": str(selection_month), "candidate": chosen,
                "validation_months": [], "n_validation": 0, "candidate_mae": {},
                "reason": "fixed_default_insufficient_earlier_validation"}
        if pieces:
            past = pd.concat(pieces, ignore_index=True)
            months = validation_months(past.month, selection_month)
            past = past.loc[past.month.isin(months) & past.score_eligible
                            & (pd.to_datetime(past.available_at) <= forecast_date(selection_month))]
            if not past.empty:
                # A candidate cannot win merely by failing on difficult rows.
                common = past.pivot(index=["month", "area"], columns="candidate", values="loss")
                common = common.reindex(columns=range(len(GRIDS[family]))).dropna()
                if not common.empty:
                    used = sorted(common.index.get_level_values("month").unique())
                    scores = common.mean()
                    info.update(validation_months=used, n_validation=len(common),
                                candidate_mae={str(int(c)): float(loss) for c, loss in scores.items()})
                    if len(used) >= MIN_VALIDATION_MONTHS:
                        chosen = int(scores.idxmin())
                        info.update(candidate=chosen, reason="earlier_vintage_validation")
        self.decisions.append(info)
        return chosen, info


def candidate_config(store, key, candidate, selection_month, targets, sample_features=None):
    """Early-stop CatBoost only on an earlier origin's own training vintage."""
    _, family, model, outcome = key
    config = dict(GRIDS[family][candidate])
    if family != "catboost":
        return config, None
    earlier = validation_months(store.months, selection_month)
    if not earlier:
        config["iterations"] = 100  # fixed cold-start choice, not tuned on scored month
        return config, {"reason": "fixed_cold_start", "iterations": 100, "validation_month": None}
    inner_month = earlier[-1]
    vintage = store.vintage(inner_month)
    features = store.feature_sets(inner_month)[model]
    labels = targets.loc[(targets.month == inner_month) & (pd.to_datetime(targets.available_at) <= forecast_date(selection_month))]
    info = early_stop_iterations(vintage, outcome, features, config, labels,
                                 selection_month=str(selection_month), sample_features=sample_features)
    config["iterations"] = int(info["iterations"])
    return config, info


def key_string(key):
    return "/".join(key)


def configuration_json(config):
    return json.dumps(config, sort_keys=True, allow_nan=False)
