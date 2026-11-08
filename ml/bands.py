"""Rolling conformal 80% bands: quantiles of each model's own earlier errors.

At issue date D a band uses only errors whose actuals were public by D, from
the previous window (36 months for supply, 156 weeks for price), so it is what
a forecaster could really have quoted that day.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd

from ml.config import BAND_LEVELS


def rolling_bands(
    rows: pd.DataFrame,
    *,
    models: Sequence[str],
    by: Sequence[str],
    target: str,
    known: str,
    actual: str,
    window: int,
    minimum: int,
) -> pd.DataFrame:
    """Add ``lo_<model>`` and ``hi_<model>`` (in the forecast's own units) to ``rows``.

    ``target`` and ``known`` are integer period numbers: a row's error counts
    for another row's band when its target is in ``(known - window, known]``.
    """

    result = rows.copy()
    for model in models:
        lo = np.full(len(rows), np.nan)
        hi = np.full(len(rows), np.nan)
        for _, group in rows.groupby(list(by), sort=False):
            errors = (group[actual] - group[model]).to_numpy(float)
            targets = group[target].to_numpy()
            usable = np.isfinite(errors)
            for known_value in np.unique(group[known].to_numpy()):
                pool = usable & (targets <= known_value) & (targets > known_value - window)
                if np.unique(targets[pool]).size < minimum:
                    continue
                q_lo, q_hi = np.quantile(errors[pool], BAND_LEVELS)
                here = (group[known].to_numpy() == known_value)
                positions = group.index[here]
                indexer = rows.index.get_indexer(positions)
                lo[indexer] = group.loc[positions, model].to_numpy(float) + q_lo
                hi[indexer] = group.loc[positions, model].to_numpy(float) + q_hi
        result[f"lo_{model}"] = lo
        result[f"hi_{model}"] = hi
    return result


def month_number(months: pd.Series) -> pd.Series:
    periods = pd.PeriodIndex(months.astype(str), freq="M")
    return pd.Series(periods.year * 12 + periods.month - 1, index=months.index)


def week_number(weeks: pd.Series) -> pd.Series:
    starts = pd.to_datetime([pd.Timestamp.fromisocalendar(int(w[:4]), int(w[6:]), 1) for w in weeks])
    return pd.Series(((starts - pd.Timestamp("2000-01-03")).days // 7).to_numpy(), index=weeks.index)


def coverage(rows: pd.DataFrame, model: str, actual: str) -> float | None:
    inside = rows[[actual, f"lo_{model}", f"hi_{model}"]].dropna()
    if inside.empty:
        return None
    return float(((inside[actual] >= inside[f"lo_{model}"]) & (inside[actual] <= inside[f"hi_{model}"])).mean())
