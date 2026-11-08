"""As-of feature cases and compact forecasters for the SISALMONI v2 experiment.

This module never selects a model or scores a final evaluation segment. Each
historical feature row is constructed using that row's own publication date;
target values are carried separately and become training labels only on release.
"""

import numpy as np
import pandas as pd


PRICE_FEATURES = ("price", "return_1", "momentum_4", "volatility_4", "sin_year", "cos_year")
GROUP_FEATURES = {
    "fx": ("eurnok_chg", "usdnok_chg"),
    "exports": ("v_anom", "v_anom_lag1"),
    "biology": ("mobile_anom", "mortality_anom", "temperature_anom"),
}
ALL_FEATURES = PRICE_FEATURES + tuple(c for columns in GROUP_FEATURES.values() for c in columns)


def feature_columns(groups=()):
    """Return a deterministic feature order for a declared group comparison."""
    columns = list(PRICE_FEATURES)
    for group in groups:
        if group not in GROUP_FEATURES:
            raise ValueError(f"Unknown feature group: {group}")
        for column in GROUP_FEATURES[group]:
            if column not in columns:
                columns.append(column)
    return columns


def build_cases(dataset, horizons=range(2, 9)):
    """Construct one calendar-week case per origin and horizon, without fitting.

    ``dataset`` must be the SISALMONI-retargeted PriceDataset, retaining its
    original export-volume history. Its legacy ``price_nok_kg`` carrier contains
    EUR/kg. Missing weekly prices remain missing on a regular Monday grid.
    """
    horizons = tuple(int(h) for h in horizons)
    if not horizons or any(h <= 0 for h in horizons):
        raise ValueError("Forecast horizons must be positive calendar weeks")
    records = {h: [] for h in horizons}
    source = dataset.ssb
    prices = source["price_nok_kg"]
    origins = source.loc[np.isfinite(prices) & (prices > 0)]
    for t, raw in origins.iterrows():
        issue = pd.Timestamp(raw.available_at)
        frame = dataset.snapshot(issue)
        if t not in frame.index or not np.isfinite(frame.loc[t, "p"]):
            continue
        # Reindex before differencing: a missing week cannot become a shorter lag.
        dates = pd.date_range(t - pd.Timedelta(weeks=4), t, freq="W-MON")
        past = frame.p.reindex(dates)
        returns = past.diff().iloc[1:]
        momentum = float(past.iloc[-1] - past.iloc[0]) if past.notna().all() else np.nan
        volatility = float(returns.std(ddof=0)) if returns.notna().all() else np.nan
        current = frame.loc[t]
        base = {
            "origin_date": pd.Timestamp(t),
            "issue_date": issue,
            "origin_price": float(np.exp(current.p)),
            "price": float(np.exp(current.p)),
            "return_1": float(returns.iloc[-1]),
            "momentum_4": momentum,
            "volatility_4": volatility,
        }
        for name in GROUP_FEATURES["fx"] + GROUP_FEATURES["exports"]:
            base[name] = float(current.get(name, np.nan))
        for name in ("mobile_anom", "mortality_anom"):
            base[name] = float(current.get(name, np.nan))
        temperature = pd.Series([current.get(c, np.nan) for c in
                                 ("dd_below8", "dd_8to14", "dd_above14")], dtype=float)
        base["temperature_anom"] = float(temperature.sum(min_count=3))
        for h in horizons:
            target_date = pd.Timestamp(t) + pd.Timedelta(weeks=h)
            actual = float(prices.get(target_date, np.nan))
            release = source.available_at.get(target_date, pd.NaT)
            anchor = target_date + pd.Timedelta(days=3)
            angle = 2 * np.pi * anchor.dayofyear / 365.25
            records[h].append({
                **base, "target_date": target_date,
                "target_available_at": pd.Timestamp(release),
                "actual_price": actual,
                "target_log_change": float(np.log(actual) - current.p)
                if np.isfinite(actual) and actual > 0 else np.nan,
                "sin_year": float(np.sin(angle)), "cos_year": float(np.cos(angle)),
            })
    columns = ["origin_date", "issue_date", "origin_price", "target_date",
               "target_available_at", "actual_price", "target_log_change", *ALL_FEATURES]
    result = {}
    for h, rows in records.items():
        table = pd.DataFrame.from_records(rows, columns=columns).set_index("origin_date")
        table.index = pd.DatetimeIndex(table.index, name="origin_date")
        result[h] = table.sort_index()
    return result


def training_rows(frame, origin, feature_columns=ALL_FEATURES):
    """Only complete past cases whose target labels were public at this issue."""
    origin = pd.Timestamp(origin)
    if origin not in frame.index:
        raise KeyError(f"Origin absent from feature cases: {origin}")
    issue = pd.Timestamp(frame.loc[origin, "issue_date"])
    features = frame[list(feature_columns)].to_numpy(dtype=float)
    eligible = (frame.index < origin) & (frame.target_date <= origin)
    eligible &= frame.target_available_at.notna() & (frame.target_available_at <= issue)
    eligible &= np.isfinite(features).all(axis=1)
    eligible &= np.isfinite(frame.actual_price) & (frame.actual_price > 0)
    eligible &= np.isfinite(frame.target_log_change)
    return frame.loc[eligible].copy()


def fit_scaled_ridge(X, y, alpha):
    """Fit the sum-squared-error + alpha * squared-coefficient Ridge objective.

    The intercept is unpenalized. All means and population standard deviations
    are estimated on the supplied training rows, never on a prediction row.
    """
    columns = tuple(X.columns) if isinstance(X, pd.DataFrame) else None
    x = np.asarray(X, dtype=float)
    response = np.asarray(y, dtype=float)
    if x.ndim != 2 or response.ndim != 1 or len(x) != len(response) or not len(x):
        raise ValueError("Ridge requires a nonempty 2D design and matching 1D target")
    if not np.isfinite(alpha) or alpha <= 0:
        raise ValueError("Ridge alpha must be finite and strictly positive")
    if not np.isfinite(x).all() or not np.isfinite(response).all():
        raise ValueError("Ridge training rows must be finite")
    mean = x.mean(axis=0)
    scale = x.std(axis=0, ddof=0)
    scale = np.where(scale == 0, 1.0, scale)
    intercept = float(response.mean())
    z = (x - mean) / scale
    gram = z.T @ z + float(alpha) * np.eye(x.shape[1])
    coef = np.linalg.solve(gram, z.T @ (response - intercept))
    if not np.isfinite(coef).all():
        raise ValueError("Non-finite Ridge coefficients")
    return {"mean": mean, "scale": scale, "coef": coef, "intercept": intercept,
            "columns": columns, "n_train": len(x), "alpha": float(alpha),
            "condition": float(np.linalg.cond(gram))}


def predict_ridge(state, X):
    if isinstance(X, pd.DataFrame) and state["columns"] is not None:
        if tuple(X.columns) != state["columns"]:
            raise ValueError("Prediction feature order differs from Ridge training")
    x = np.asarray(X, dtype=float)
    if x.ndim == 1:
        x = x.reshape(1, -1)
    if x.ndim != 2 or x.shape[1] != len(state["coef"]) or not np.isfinite(x).all():
        raise ValueError("Ridge prediction rows must have matching finite features")
    prediction = state["intercept"] + ((x - state["mean"]) / state["scale"]) @ state["coef"]
    if not np.isfinite(prediction).all():
        raise ValueError("Non-finite Ridge prediction")
    return prediction


def predict_spec(spec, train, current):
    """Return an un-clipped EUR/kg forecast and training diagnostics.

    Finite nonpositive level forecasts are returned with ``positive_price``
    false so evaluation can count them explicitly rather than remove the week.
    """
    kind = spec["kind"]
    p0 = float(current.origin_price)
    if not np.isfinite(p0) or p0 <= 0:
        raise ValueError("Origin price must be finite and positive")
    diagnostics = {"n_train": len(train), "n_features": 0}
    if kind == "rw":
        predicted = p0
    elif kind == "ar1":
        x = np.column_stack([np.ones(len(train)), train.return_1.to_numpy(float)])
        y = train.target_log_change.to_numpy(float)
        if not len(train) or not np.isfinite(x).all() or not np.isfinite(y).all():
            raise ValueError("AR(1) training rows must be nonempty and finite")
        coef = np.linalg.lstsq(x, y, rcond=None)[0]
        log_change = float(np.array([1.0, current.return_1]) @ coef)
        with np.errstate(over="ignore"):
            predicted = float(p0 * np.exp(log_change))
        diagnostics.update(n_features=1, coef=coef.tolist())
    elif kind == "ridge":
        columns = feature_columns(spec.get("groups", ()))
        representation = spec["representation"]
        if representation not in {"log_change", "level"}:
            raise ValueError(f"Unknown target representation: {representation}")
        y = train.target_log_change if representation == "log_change" else train.actual_price
        state = fit_scaled_ridge(train[columns], y, spec["alpha"])
        result = float(predict_ridge(state, current[columns].to_frame().T)[0])
        with np.errstate(over="ignore"):
            predicted = float(p0 * np.exp(result)) if representation == "log_change" else result
        diagnostics.update(n_features=len(columns), ridge_condition=state["condition"],
                           max_abs_coef=float(np.abs(state["coef"]).max()),
                           min_scale=float(state["scale"].min()))
    elif kind == "blend":
        component = {"kind": "ridge", "representation": "log_change", "alpha": 100.0, "groups": []}
        ridge_prediction, component_diagnostics = predict_spec(component, train, current)
        predicted = 0.5 * p0 + 0.5 * ridge_prediction
        diagnostics.update(component_diagnostics)
        diagnostics["blend_weight_ridge"] = 0.5
    else:
        raise ValueError(f"Unknown model kind: {kind}")
    if not np.isfinite(predicted):
        raise ValueError("Non-finite price forecast")
    diagnostics["positive_price"] = bool(predicted > 0)
    return float(predicted), diagnostics
