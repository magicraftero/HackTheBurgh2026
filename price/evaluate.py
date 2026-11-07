"""Matched-sample forecast scores and pre-registered F2 inference."""

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.stats import norm
from statsmodels.stats.multitest import multipletests

from price.calendar import iso_week, week_start


def clark_west(pair, h):
    if len(pair) < max(3, h + 1):
        return None, None
    f = pair.error_c0 ** 2 - (pair.error_c1 ** 2 - (pair.y_hat_c0 - pair.y_hat_c1) ** 2)
    result = sm.OLS(f, np.ones(len(f))).fit(cov_type="HAC", cov_kwds={"maxlags": h - 1})
    stat = float(result.tvalues.iloc[0])
    if not np.isfinite(stat):
        return None, None
    return stat, float(norm.sf(stat))


def paired(rows, h, window):
    rows = rows.loc[(rows.h == h) & (rows.window == window)]
    c0 = rows.loc[rows.model == "c0"].set_index("origin_week")
    c1 = rows.loc[rows.model == "c1"].set_index("origin_week")
    return c0.merge(c1, left_index=True, right_index=True, suffixes=("_c0", "_c1"), how="inner").sort_index()


def evaluate(rows, final=False):
    scorecard, cw, by_year = [], [], []
    for (window, h), group in rows.groupby(["window", "h"], sort=True):
        rw = group.loc[group.model == "rw", "error"].abs().mean()
        for model, values in group.groupby("model", sort=True):
            mae = float(values.error.abs().mean())
            nonzero = values.loc[values.y_hat != 0]
            hit = float((np.sign(nonzero.y_hat) == np.sign(nonzero.y)).mean()) if len(nonzero) else None
            scorecard.append({"window": window, "h": int(h), "model": model, "mae": mae,
                              "mae_ratio": mae / rw if rw > 0 else None,
                              "hit_rate": hit if model != "rw" else None})
        pair = paired(rows, h, window)
        if not pair.empty:
            stat, p = clark_west(pair, h)
            cw.append({"window": window, "h": int(h), "stat": stat, "p": p,
                       "p_holm": None, "primary": h == 4})
    for window in rows.window.unique():
        other = [row for row in cw if row["window"] == window and row["h"] != 4 and row["p"] is not None]
        if other:
            adjusted = multipletests([row["p"] for row in other], method="holm")[1]
            for row, value in zip(other, adjusted, strict=True):
                row["p_holm"] = float(value)
    h4 = rows.loc[(rows.h == 4) & rows.model.isin(["c0", "c1"])].copy()
    if not h4.empty:
        h4["year"] = h4.origin_week.map(lambda w: int(iso_week(week_start(w) + pd.Timedelta(weeks=4))[:4]))
        for year, group in h4.groupby("year"):
            scores = group.groupby("model").error.agg(lambda x: x.abs().mean())
            by_year.append({"year": int(year), "mae_c0": float(scores["c0"]),
                            "mae_c1": float(scores["c1"]) if "c1" in scores else None})
    f2 = None
    if final:
        pair = paired(rows, 4, "holdout")
        if not pair.empty:
            mae0, mae1 = float(pair.error_c0.abs().mean()), float(pair.error_c1.abs().mean())
            stat, p = clark_west(pair, 4)
            # Null means not evaluable, never a claimed pass or fail.
            decision = bool(mae1 <= .95 * mae0 and p < .05) if p is not None else None
            f2 = {"window": "holdout", "mae_c0": mae0, "mae_c1": mae1,
                  "cw_p": p, "pass": decision}
    return {"scorecard": scorecard, "cw": cw, "by_year": by_year, "f2": f2}


def backtest_prices(rows, ssb, f2, window="holdout"):
    """NOK/kg replay; interval errors always come from development targets."""
    pair = paired(rows, 4, window)
    if pair.empty:
        return []
    band_model = "c1" if f2 and f2["pass"] else "c0"
    errors = rows.loc[(rows.window == "dev") & (rows.h == 4) & (rows.model == band_model), "error"]
    if errors.empty:
        raise ValueError("Development errors are required for the 80% interval")
    q10, q90 = np.quantile(errors, [.1, .9])
    records = []
    for origin, row in pair.iterrows():
        start = week_start(origin)
        end = start + pd.Timedelta(weeks=4)
        p = np.log(ssb.loc[start, "price_nok_kg"])
        median = p + row["y_hat_" + band_model]
        records.append({"week": iso_week(end), "actual": float(ssb.loc[end, "price_nok_kg"]),
                        "pred_c0": float(np.exp(p + row.y_hat_c0)),
                        "pred_c1": float(np.exp(p + row.y_hat_c1)), "band_model": band_model,
                        "p10": float(np.exp(median + q10)), "p90": float(np.exp(median + q90))})
    return records
