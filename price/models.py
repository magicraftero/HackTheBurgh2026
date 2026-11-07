"""Nested direct OLS models, with lag selection restricted to pre-2019 data."""

import numpy as np
import pandas as pd
import statsmodels.api as sm

from price.calendar import seasonality
from price.dataset import C0_FEATURES, driver_features


def design(frame, h, p, model, drivers):
    target_dates = frame.index + pd.Timedelta(weeks=h)
    result = seasonality(target_dates)
    result.index = frame.index
    for lag in range(p):
        result[f"dp_lag{lag}"] = frame[f"dp_lag{lag}"]
    if model in {"c0", "c1"}:
        columns = C0_FEATURES + (driver_features(drivers) if model == "c1" else [])
        result[columns] = frame[columns]
    return result.astype(float)


def target(frame, h):
    """Calendar shift, not row shift: a missing ISO week cannot shorten h."""
    future = frame.p.reindex(frame.index + pd.Timedelta(weeks=h)).to_numpy()
    return pd.Series(future - frame.p.to_numpy(), index=frame.index)


def choose_lag(frame, h):
    y = target(frame, h)
    largest = design(frame, h, 8, "ar", [])
    dates = frame.index + pd.Timedelta(weeks=h)
    releases = frame.available_at.reindex(dates).to_numpy()
    valid = (frame.index >= pd.Timestamp("2012-01-02")) & (frame.index < pd.Timestamp("2019-01-01"))
    valid &= dates < pd.Timestamp("2019-01-01")
    valid &= releases <= np.datetime64("2018-12-31")
    valid &= y.notna() & largest.notna().all(axis=1)
    n = int(valid.sum())
    if n <= largest.shape[1]:
        raise ValueError(f"h={h}: insufficient 2012–2018 rows for BIC ({n}); lag selection cannot use later data")
    scores = {}
    for p in range(1, 9):
        x = design(frame, h, p, "ar", [])
        scores[p] = float(sm.OLS(y.loc[valid], x.loc[valid]).fit().bic)
    best = min(scores, key=scores.get)
    return best, {"p": best, "n": n, "bic": scores}


def fit_predict(x, y, new):
    # The constant is explicit in seasonality(), including for a one-row X_new.
    result = sm.OLS(y, x).fit()
    return float(result.predict(new).iloc[0])
