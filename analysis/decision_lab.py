"""Data for the farmer decision cockpit: ``web/public/data/decision_lab.json``.

For each production area the cockpit shows the nowcast for the month after
the latest Directorate release, the signals behind it, and how the forecast
moves if this month's lice, treatments or sea temperature were different.

Lever effects are the Drivers model's coefficients: predictive associations
learned from public data, not causal effects of a farmer's action. Ranges come
from development-window backtest errors only, so the holdout stays untouched.

Run with ``python -m analysis.decision_lab`` after ``python -m analysis.nowcast``.
The schema is documented in ``analysis/DECISION_LAB.md``.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Final

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.stats import percentileofscore

from analysis.anomalies import Transform
from analysis.config import (
    AREAS,
    DIRECTORATE_RELEASE_DAY_OF_FOLLOWING_MONTH,
    PROCESSED_DATA_DIR,
    SITE_DATA_DIR,
)
from analysis.drivers import add_directorate_levels
from analysis.io import round_decimals, round_significant, write_json_atomic
from analysis.nowcast import (
    DRIVER_GROUPS,
    OUTCOMES,
    PreparedInputs,
    build_vintage,
    design_matrix,
    forecast_date,
    model_features,
)

AREA_NAMES: Final[dict[int, str]] = {
    1: "Svenskegrensen til Jæren",
    2: "Ryfylke",
    3: "Karmøy til Sotra",
    4: "Nordhordland til Stadt",
    5: "Stadt til Hustadvika",
    6: "Nordmøre og Sør-Trøndelag",
    7: "Nord-Trøndelag med Bindal",
    8: "Helgeland til Bodø",
    9: "Vestfjorden og Vesterålen",
    10: "Andøya til Senja",
    11: "Kvaløya til Loppa",
    12: "Vest-Finnmark",
    13: "Øst-Finnmark",
}
DISCLAIMER: Final = (
    "Scenario forecasts from a model trained on public data. They show how "
    "harvests have tended to move with these signals, not what an action will "
    "cause. Not operational advice."
)
FORMULA: Final = (
    "forecast_log[o] = baseline.log[o] + sum over levers of "
    "coef[o] * (T(scale * new) - T(scale * current)), where T is log1p or the "
    "identity; kg = exp(forecast_log.log_kg), and the range adds interval[o]."
)
INTERVAL_QUANTILES: Final = (0.1, 0.9)
FLAG_PERCENTILE: Final = 80.0
HISTORY_MONTHS: Final = 24
LEVEL_KEYS: Final = {"log_kg": "kg", "log_count": "count", "log_avg_kg": "avg_kg"}


@dataclass(frozen=True)
class Lever:
    id: str
    label: str
    unit: str
    level_column: str
    transform: Transform
    scale: float
    feature: str | None
    group: str


LEVERS: Final[list[Lever]] = [
    Lever("lice", "Mobile lice per fish", "lice per fish", "mobile_idx", "log1p", 1.0, "mobile_anom", "lice"),
    Lever("treatments", "Farm-weeks with delousing", "share of farm-weeks", "treat_rate", "log1p", 100.0, "treat_anom", "lice"),
    Lever("temperature", "Sea temperature vs normal", "degree-days over 6 weeks", "dd_anom", "none", 1.0, None, "temperature"),
    Lever("disease", "Sites with ISA or PD", "share of sites", "disease_share", "none", 1.0, "disease_share", "losses"),
]
TEMPERATURE_BANDS: Final = [
    ("below8", "dd_below8", -np.inf, 8.0),
    ("8to14", "dd_8to14", 8.0, 14.0),
    ("above14", "dd_above14", 14.0, np.inf),
]


def build_decision_lab(
    prepared: PreparedInputs,
    target: pd.Period,
    cutoff: pd.Timestamp,
    backtest: pd.DataFrame | None = None,
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    features = model_features(prepared.include_disease)["drivers"]
    vintage = build_vintage(prepared, target, made_on=cutoff)
    target_start = target.to_timestamp()
    train = vintage.loc[vintage["date"] < target_start]
    current = vintage.loc[vintage["date"] == target_start].set_index("area")

    fits = {}
    n_train = {}
    for outcome in OUTCOMES:
        rows = train[f"{outcome}_anom"].notna() & train[features].notna().all(axis=1)
        fits[outcome] = sm.OLS(
            train.loc[rows, f"{outcome}_anom"].to_numpy(float),
            design_matrix(train.loc[rows, features]),
        ).fit()
        n_train[outcome] = int(rows.sum())
    coefficients = {
        outcome: dict(zip(["const", *features], fit.params)) for outcome, fit in fits.items()
    }

    dev_errors = _development_errors(backtest)
    interval = {
        outcome: [float(np.quantile(errors, q)) for q in INTERVAL_QUANTILES]
        for outcome, errors in dev_errors.items()
    }
    levers = [lever for lever in LEVERS if lever.id != "disease" or prepared.include_disease]
    cutoff = min(cutoff, forecast_date(target))

    areas = [
        _area_entry(
            area,
            prepared,
            target,
            cutoff,
            current.loc[area],
            features,
            coefficients,
            interval,
            levers,
        )
        for area in AREAS
    ]
    return {
        "target_month": str(target),
        "made_on": cutoff.strftime("%Y-%m-%d"),
        "publishes_around": _release_date(target).strftime("%Y-%m-%d"),
        "status": "unverifiable until the Directorate publishes this month",
        "disclaimer": DISCLAIMER,
        "formula": FORMULA,
        "model": {
            "name": "drivers",
            "features": features,
            "n_train": n_train,
            "interval": (
                {
                    "level": round(INTERVAL_QUANTILES[1] - INTERVAL_QUANTILES[0], 2),
                    "source": "development-window walk-forward errors",
                    **{o: [round_significant(v) for v in interval[o]] for o in interval},
                }
                if interval
                else None
            ),
            "dev_mae": {
                outcome: round_significant(np.abs(errors).mean())
                for outcome, errors in dev_errors.items()
            }
            or None,
        },
        "levers": [
            {
                "id": lever.id,
                "label": lever.label,
                "unit": lever.unit,
                "transform": lever.transform,
                "scale": lever.scale,
                "evidence": (evidence or {}).get(lever.id),
            }
            for lever in levers
        ],
        "national": _national_entry(areas, backtest),
        "areas": areas,
    }


def _area_entry(
    area: int,
    prepared: PreparedInputs,
    target: pd.Period,
    cutoff: pd.Timestamp,
    current: pd.Series,
    features: list[str],
    coefficients: dict[str, dict[str, float]],
    interval: dict[str, list[float]],
    levers: list[Lever],
) -> dict[str, Any]:
    x = current[features].astype(float)
    complete = bool(x.notna().all())
    baseline_log: dict[str, float | None] = {}
    for outcome in OUTCOMES:
        base = current[f"{outcome}_base"]
        if complete and pd.notna(base):
            coef = coefficients[outcome]
            baseline_log[outcome] = float(
                base + coef["const"] + sum(coef[f] * x[f] for f in features)
            )
        else:
            baseline_log[outcome] = None

    monthly = _monthly_levels(prepared.weekly.get(area), cutoff)
    directorate = _directorate_levels(prepared.directorate[area], target)
    target_start = target.to_timestamp()
    temp_c = monthly["temp_c"].get(target_start, np.nan)

    lever_rows = []
    for lever in levers:
        history = monthly[lever.level_column].loc[lambda s: s.index < target_start].dropna()
        value = monthly[lever.level_column].get(target_start, np.nan)
        feature = lever.feature or _temperature_feature(temp_c)
        lever_rows.append(
            {
                "id": lever.id,
                "current": _round_level(lever, value),
                "percentile": _percentile(history, value),
                "range": [_round_level(lever, q) for q in _quantiles(history, (0.05, 0.95))],
                "band": _temperature_band(temp_c) if lever.id == "temperature" else None,
                "coef": {
                    outcome: (
                        round_significant(coefficients[outcome][feature])
                        if feature is not None and pd.notna(value)
                        else None
                    )
                    for outcome in OUTCOMES
                },
            }
        )

    signals = _signals(monthly, directorate, target)
    return {
        "area": area,
        "name": AREA_NAMES[area],
        "baseline": _forecast_entry(baseline_log, interval),
        "why": _contributions(x, coefficients, features) if complete else [],
        "levers": lever_rows,
        "signals": signals,
        "flags": _flags(signals),
        "history": _history(prepared.directorate[area], target),
    }


def _forecast_entry(
    baseline_log: dict[str, float | None], interval: dict[str, list[float]]
) -> dict[str, Any]:
    entry: dict[str, Any] = {"log": {o: round_decimals(v, 6) for o, v in baseline_log.items()}}
    for outcome, key in LEVEL_KEYS.items():
        value = baseline_log[outcome]
        entry[key] = None if value is None else round_significant(np.exp(value))
        bounds = interval.get(outcome)
        entry[f"{key}_range"] = (
            None
            if value is None or bounds is None
            else [round_significant(np.exp(value + bound)) for bound in bounds]
        )
    return entry


def _contributions(
    x: pd.Series, coefficients: dict[str, dict[str, float]], features: list[str]
) -> list[dict[str, Any]]:
    """How far each driver group moves this month's forecast from normal."""

    rows = []
    for group in DRIVER_GROUPS:
        members = [f for f in features if f.removesuffix("_l1") in group.columns]
        if not members:
            continue
        effects = {
            outcome: sum(coefficients[outcome][f] * x[f] for f in members) for outcome in OUTCOMES
        }
        rows.append(
            {
                "group": group.name,
                "label": group.label,
                **{
                    f"{LEVEL_KEYS[o]}_pct": round_significant(100 * (np.exp(v) - 1))
                    for o, v in effects.items()
                },
            }
        )
    return sorted(rows, key=lambda row: -abs(row["kg_pct"] or 0))


def _signals(
    monthly: pd.DataFrame, directorate: pd.DataFrame, target: pd.Period
) -> dict[str, Any]:
    target_start = target.to_timestamp()
    last_known = (target - 1).to_timestamp()

    def signal(series: pd.Series, at: pd.Timestamp, unit: str, decimals: bool) -> dict[str, Any]:
        value = series.get(at, np.nan)
        history = series.loc[series.index < at].dropna()
        rounded = round_decimals(value) if decimals else round_significant(value)
        return {
            "value": rounded,
            "unit": unit,
            "month": at.strftime("%Y-%m"),
            "percentile": _percentile(history, value),
        }

    return {
        "lice": signal(monthly["mobile_idx"], target_start, "lice per fish", True),
        "treatments": signal(monthly["treat_rate"], target_start, "share of farm-weeks", False),
        "sea_temp": signal(monthly["temp_c"], target_start, "°C", True),
        "temp_anomaly": signal(monthly["dd_anom"], target_start, "degree-days over 6 weeks", True),
        "mortality": signal(directorate["mortality"], last_known, "deaths per 1,000 fish", False),
        "feed_rate": signal(directorate["feed_rate"], last_known, "kg feed per kg biomass", False),
    }


def _flags(signals: dict[str, Any]) -> list[dict[str, str]]:
    """Transparent rules: a signal in the top fifth of its own area's history."""

    rules = [
        ("lice", "lice_high", "Lice pressure is in the top fifth of this area's history"),
        ("treatments", "treatments_high", "Delousing is more frequent than in four out of five past months"),
        ("temp_anomaly", "sea_warm", "The sea is warmer than normal for the time of year"),
        ("mortality", "mortality_high", "Deaths per 1,000 fish were in the top fifth of this area's history"),
    ]
    flags = []
    for key, flag_id, label in rules:
        percentile = signals[key]["percentile"]
        if percentile is not None and percentile >= FLAG_PERCENTILE:
            flags.append({"id": flag_id, "signal": key, "label": label, "severity": "warning"})
    cold = signals["temp_anomaly"]["percentile"]
    if cold is not None and cold <= 100 - FLAG_PERCENTILE:
        flags.append(
            {"id": "sea_cold", "signal": "temp_anomaly", "label": "The sea is colder than normal for the time of year", "severity": "info"}
        )
    return flags


def _national_entry(areas: list[dict[str, Any]], backtest: pd.DataFrame | None) -> dict[str, Any]:
    kg = [a["baseline"]["kg"] for a in areas]
    count = [a["baseline"]["count"] for a in areas]
    complete = all(v is not None for v in kg + count)
    total_kg = float(sum(kg)) if complete else None
    total_count = float(sum(count)) if complete else None
    bounds = _national_interval(backtest)
    return {
        "label": "Areas 1-13 (the Directorate's suppressed-data row is not forecast)",
        "kg": round_significant(total_kg),
        "count": round_significant(total_count),
        "avg_kg": round_significant(total_kg / total_count) if complete and total_count else None,
        "kg_range": (
            [round_significant(total_kg * np.exp(b)) for b in bounds]
            if complete and bounds is not None
            else None
        ),
    }


def _national_interval(backtest: pd.DataFrame | None) -> list[float] | None:
    if backtest is None:
        return None
    kg = backtest.loc[(backtest["window"] == "dev") & (backtest["outcome"] == "log_kg")]
    kg = kg.loc[kg[["actual", "drivers"]].notna().all(axis=1)]
    complete = kg.groupby("month")["area"].transform("count") == len(AREAS)
    sums = kg.loc[complete].groupby("month")[["actual", "drivers"]].agg(lambda s: np.exp(s).sum())
    if sums.empty:
        return None
    errors = np.log(sums["actual"]) - np.log(sums["drivers"])
    return [float(np.quantile(errors, q)) for q in INTERVAL_QUANTILES]


def _development_errors(backtest: pd.DataFrame | None) -> dict[str, np.ndarray]:
    if backtest is None:
        return {}
    dev = backtest.loc[backtest["window"] == "dev"]
    errors = {}
    for outcome in OUTCOMES:
        rows = dev.loc[(dev["outcome"] == outcome) & dev[["actual", "drivers"]].notna().all(axis=1)]
        if len(rows):
            errors[outcome] = (rows["actual"] - rows["drivers"]).to_numpy(float)
    return errors


def _monthly_levels(weekly: pd.DataFrame | None, cutoff: pd.Timestamp) -> pd.DataFrame:
    columns = ["mobile_idx", "treat_rate", "disease_share", "temp_c", "dd_anom"]
    if weekly is None:
        return pd.DataFrame(columns=columns, dtype=float)
    public = weekly.loc[(weekly.index <= cutoff) & (weekly["available_at"] <= cutoff)]
    present = [c for c in columns if c in public.columns]
    month = (public.index + pd.Timedelta(days=3)).to_period("M").to_timestamp()
    monthly = public[present].groupby(month).mean()
    return monthly.reindex(columns=columns)


def _directorate_levels(directorate: pd.DataFrame, target: pd.Period) -> pd.DataFrame:
    known = directorate.loc[directorate.index < target.to_timestamp()]
    grid = pd.date_range(known.index.min(), known.index.max(), freq="MS")
    return add_directorate_levels(known.reindex(grid))


def _history(directorate: pd.DataFrame, target: pd.Period) -> list[dict[str, Any]]:
    known = directorate.loc[directorate.index < target.to_timestamp()].tail(HISTORY_MONTHS)
    return [
        {
            "month": index.strftime("%Y-%m"),
            "kg": round_significant(row["harvest_kg"]),
            "count": round_significant(row["harvest_count"]),
            "avg_kg": round_significant(row["avg_kg"]),
        }
        for index, row in known.iterrows()
    ]


def _temperature_band(temp_c: float) -> str | None:
    if pd.isna(temp_c):
        return None
    return next(name for name, _, low, high in TEMPERATURE_BANDS if low <= temp_c < high)


def _temperature_feature(temp_c: float) -> str | None:
    if pd.isna(temp_c):
        return None
    return next(feature for _, feature, low, high in TEMPERATURE_BANDS if low <= temp_c < high)


def _round_level(lever: Lever, value: float) -> float | int | None:
    return round_decimals(value) if lever.id in {"lice", "temperature"} else round_significant(value)


def _percentile(history: pd.Series, value: float) -> float | None:
    if pd.isna(value) or len(history) < 12:
        return None
    return round_significant(percentileofscore(history.to_numpy(float), value, kind="mean"))


def _quantiles(history: pd.Series, quantiles: tuple[float, ...]) -> list[float]:
    if len(history) < 12:
        return [np.nan for _ in quantiles]
    return [float(np.quantile(history, q)) for q in quantiles]


def _release_date(target: pd.Period) -> pd.Timestamp:
    return (target + 1).to_timestamp() + pd.Timedelta(days=DIRECTORATE_RELEASE_DAY_OF_FOLLOWING_MONTH - 1)


def _read_evidence(site: Path) -> dict[str, Any]:
    """Driver ranking and mechanism results, once they exist after the freeze."""

    evidence: dict[str, Any] = {}
    ranking_path = site / "drivers.json"
    channels_path = site / "channels.json"
    ranking = json.loads(ranking_path.read_text(encoding="utf-8")) if ranking_path.exists() else {}
    channels = json.loads(channels_path.read_text(encoding="utf-8")) if channels_path.exists() else {}
    increase = {g["group"]: g["increase_pct"] for g in ranking.get("groups", [])}
    tests = channels.get("panel", [])
    for lever in LEVERS:
        mechanism = [
            row
            for row in tests
            if (lever.id == "lice" and row.get("driver") == "mobile_lice")
            or (lever.id == "temperature" and row.get("driver", "").startswith("dd_below14"))
        ]
        if lever.group in increase or mechanism:
            evidence[lever.id] = {
                "ranking_increase_pct": increase.get(lever.group),
                "mechanism_tests": mechanism,
            }
    return evidence


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--processed", type=Path, default=PROCESSED_DATA_DIR)
    parser.add_argument("--site", type=Path, default=SITE_DATA_DIR)
    parser.add_argument("--cutoff", type=date.fromisoformat, default=date.today(), help="data public by this date")
    args = parser.parse_args()

    directorate = pd.read_parquet(args.processed / "directorate_area_month.parquet")
    prepared = PreparedInputs(
        directorate,
        pd.read_parquet(args.processed / "weekly_area_index.parquet"),
        pd.read_parquet(args.processed / "ssb_weekly.parquet"),
    )
    target = pd.Period(directorate["month"].max(), "M") + 1
    backtest_path = args.processed / "nowcast_backtest.parquet"
    backtest = pd.read_parquet(backtest_path) if backtest_path.exists() else None
    if backtest is None:
        print("NOTE: no nowcast_backtest.parquet yet, so forecast ranges are null.")

    lab = build_decision_lab(
        prepared, target, pd.Timestamp(args.cutoff), backtest, _read_evidence(args.site)
    )
    write_json_atomic(lab, args.site / "decision_lab.json")
    national = lab["national"]
    print(f"Wrote decision_lab.json for {lab['target_month']}, made on {lab['made_on']}")
    print(f"National forecast: {national['kg']} kg, range {national['kg_range']}")


if __name__ == "__main__":
    main()
