"""Production anomaly adapter, with the role-plan stand-in while it is absent."""

import importlib
import numpy as np
import pandas as pd

from price.calendar import seasonality


def fallback_anomaly(x, freq, transform="log", fit_end=None, K=3):
    """Match Production's trailing, 75%-coverage level and seasonal OLS."""
    if freq not in {"W", "M"} or transform not in {"log", "log1p", "none"}:
        raise ValueError("Unsupported anomaly frequency or transform")
    values = x.astype(float).replace([np.inf, -np.inf], np.nan)
    if transform == "log":
        values = np.log(values.where(values > 0))
    elif transform == "log1p":
        values = np.log1p(values.where(values > -1))
    window = 52 if freq == "W" else 12
    level = values.shift(1).rolling(window, min_periods=int(np.ceil(.75 * window))).mean()
    residual = values - level
    design = seasonality(x.index, freq, K)
    valid = residual.notna()
    if fit_end is not None:
        valid &= x.index <= pd.Timestamp(fit_end)
    if valid.sum() < design.shape[1]:
        raise ValueError("Not enough usable observations to fit seasonality")
    coef = np.linalg.lstsq(design.loc[valid], residual.loc[valid], rcond=None)[0]
    return (residual - design @ coef).rename(x.name)


def get_anomaly():
    try:
        module = importlib.import_module("analysis.anomalies")
    except ModuleNotFoundError as exc:
        if exc.name not in {"analysis", "analysis.anomalies"}:
            raise
        return fallback_anomaly, "Price stand-in (Production anomaly module absent)"
    return module.anomaly, "analysis.anomalies.anomaly"
