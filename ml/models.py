"""Model factory and the group-neutralisation "why" for the harvest model."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence

import numpy as np
import pandas as pd
import statsmodels.api as sm
from sklearn.ensemble import HistGradientBoostingRegressor

from ml.config import GBM_PARAMS

Predict = Callable[[pd.DataFrame], np.ndarray]


def fit_gbm(x: pd.DataFrame, y: np.ndarray, categorical: Sequence[str] = ()) -> Predict:
    """Fit the pre-registered gradient-boosted model and return its predictor."""

    columns = list(x.columns)
    mask = [column in categorical for column in columns]
    model = HistGradientBoostingRegressor(**GBM_PARAMS, categorical_features=mask if any(mask) else None)
    model.fit(x.to_numpy(float), np.asarray(y, float))
    return lambda new: model.predict(new[columns].to_numpy(float))


def fit_ols(x: pd.DataFrame, y: np.ndarray) -> Predict:
    """OLS with an explicit constant, as in analysis.nowcast.design_matrix."""

    columns = list(x.columns)
    params = sm.OLS(np.asarray(y, float), sm.add_constant(x.to_numpy(float), has_constant="add")).fit().params
    return lambda new: sm.add_constant(new[columns].to_numpy(float), has_constant="add") @ params


def normal_values(
    train: pd.DataFrame, columns: Sequence[str], level_columns: Sequence[str], group: str | None
) -> pd.DataFrame:
    """What "normal" means for each feature: 0 for anomalies, the training median for levels.

    Medians are per ``group`` (the area) when given, else over all training rows.
    """

    normals = {column: 0.0 for column in columns if column not in level_columns and column != group}
    levels = [column for column in columns if column in level_columns]
    if group is None:
        frame = pd.DataFrame([{**normals, **train[levels].median().to_dict()}])
        frame["_key"] = 0
        return frame
    medians = train.groupby(group)[levels].median().reset_index() if levels else (
        pd.DataFrame({group: train[group].unique()}))
    for column, value in normals.items():
        medians[column] = value
    return medians


def why(
    predict: Predict,
    rows: pd.DataFrame,
    groups: Mapping[str, Sequence[str]],
    normals: pd.DataFrame,
    group: str | None,
) -> dict[str, np.ndarray]:
    """For each driver group: prediction minus the prediction with that group at normal."""

    full = predict(rows)
    if group is None:
        lookup = normals.iloc[[0] * len(rows)].reset_index(drop=True)
    else:
        lookup = rows[[group]].reset_index(drop=True).merge(normals, on=group, how="left")
    result = {}
    for name, columns in groups.items():
        present = [column for column in columns if column in rows.columns]
        if not present:
            continue
        neutral = rows.reset_index(drop=True).copy()
        neutral[present] = lookup[present].to_numpy(float)
        result[name] = full - predict(neutral)
    return result
