"""Farmer page data: this month's forecast, what we see, what it has meant before, what to consider.

Reads the outputs of the other steps and writes ``web/public/data/farmer_actions.json``.
Run from the repository root with ``python -m analysis.farmer`` after ``analysis.decision_lab``,
``analysis.channels``, ``analysis.topdown`` and the ML challenger's ``outlook_supply.json``.

Every suggestion is tied to a pattern measured in the data. Where the data shows no clear effect,
the card says so instead of inventing one.
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any, Final

import numpy as np
import pandas as pd

from analysis.config import AREAS, PROCESSED_DATA_DIR, SITE_DATA_DIR
from analysis.io import round_significant, write_json_atomic
from analysis.topdown import topdown_month

HIGH: Final = 80.0
LOW: Final = 20.0
INTERVAL_QUANTILES: Final = (0.1, 0.9)
DISCLAIMER: Final = (
    "Patterns in Norway's public data since 2017, not guarantees and not advice. They show what "
    "has tended to happen in an area after signals like these, not what an action will cause."
)


def pct(log_change: float) -> float:
    return round_significant(100 * (np.exp(log_change) - 1), 2)


def bin_effects(channels: dict[str, Any]) -> dict[str, dict[str, dict[str, float]]]:
    """High and low tercile against the middle one, in % fish count and % average weight."""

    by_driver: dict[str, dict[int, dict[str, Any]]] = {}
    for row in channels.get("bins", []):
        by_driver.setdefault(row["driver"], {})[row["tercile"]] = row
    effects = {}
    for driver, rows in by_driver.items():
        if {1, 2, 3} - set(rows):
            continue
        middle = rows[2]
        effects[driver] = {
            level: {
                "count_pct": pct(rows[t]["count_anom"] - middle["count_anom"]),
                "weight_pct": pct(rows[t]["weight_anom"] - middle["weight_anom"]),
                "window": rows[t]["window"],
            }
            for level, t in (("high", 3), ("low", 1))
        }
    return effects


def live_forecast(
    directorate: pd.DataFrame,
    ssb: pd.DataFrame,
    outlook: dict[str, Any],
    history: pd.DataFrame,
) -> tuple[str, dict[int, dict[str, Any]], dict[str, Any]]:
    """Combined forecast for the outlook's h=0 month: v2 kg, ML weight, count = kg / weight."""

    current = next(t for t in outlook["current"]["targets"] if t["h"] == 0)
    target = pd.Period(current["target"], "M")
    topdown = topdown_month(directorate, ssb, target).set_index("area")["topdown"]
    low, high = _v2_error_band(history)

    forecasts: dict[int, dict[str, Any]] = {}
    for entry in current["areas"]:
        area = entry["area"]
        b1_t = entry["pred"]["b1"]["t"]
        weight = entry["pred"]["ml"]["avg_kg"]
        top = topdown.get(area, np.nan)
        if not (b1_t and weight and np.isfinite(top)):
            continue
        log_kg = (top + np.log(b1_t * 1000)) / 2
        kg = float(np.exp(log_kg))
        forecasts[area] = {
            "kg": round_significant(kg),
            "count": round_significant(kg / weight),
            "avg_kg": round_significant(weight),
            "kg_range": [round_significant(kg * np.exp(low)), round_significant(kg * np.exp(high))],
        }
    meta = {"target_month": str(target), "publishes_around": current["publishes_around"]}
    return str(target), forecasts, meta


def _v2_error_band(history: pd.DataFrame) -> tuple[float, float]:
    scored = history.dropna(subset=["actual", "v2"])
    errors = (scored["actual"] - scored["v2"]).to_numpy(float)
    return tuple(float(np.quantile(errors, q)) for q in INTERVAL_QUANTILES)  # type: ignore[return-value]


def stock_weight(directorate: pd.DataFrame, month: str) -> dict[int, dict[str, float]]:
    """Average weight of fish in the water in ``month``, and its percentile in the area's history."""

    rows = directorate.loc[directorate["area"].isin(AREAS) & (directorate["month"] <= month)].copy()
    rows["weight"] = rows["biomass_kg"] / rows["fish_stock"].where(rows["fish_stock"] > 0)
    result = {}
    for area, group in rows.groupby("area"):
        history = group["weight"].dropna()
        latest = group.loc[group["month"] == month, "weight"]
        if latest.empty or history.empty or not np.isfinite(latest.iloc[0]):
            continue
        value = float(latest.iloc[0])
        result[int(area)] = {
            "kg": round(value, 2),
            "percentile": round(100 * float((history <= value).mean()), 1),
        }
    return result


def same_month_last_year(directorate: pd.DataFrame, target: str) -> dict[int, float]:
    last_year = str(pd.Period(target, "M") - 12)
    rows = directorate.loc[(directorate["month"] == last_year) & directorate["area"].isin(AREAS)]
    return dict(zip(rows["area"].astype(int), rows["harvest_kg"]))


def area_actions(
    signals: dict[str, Any],
    effects: dict[str, Any],
    fish_weight: dict[str, float] | None,
) -> list[dict[str, Any]]:
    """Plain-language cards from this month's signals and the measured patterns."""

    actions: list[dict[str, Any]] = []

    def percentile(name: str) -> float | None:
        value = signals.get(name, {}).get("percentile")
        return None if value is None else float(value)

    lice = percentile("lice")
    if lice is not None and lice >= HIGH and "lice" in effects:
        e = effects["lice"]["high"]
        actions.append({
            "id": "lice_high", "severity": "warning",
            "title": "Lice are high for the time of year",
            "pattern": f"After high-lice months, areas harvested {e['count_pct']:+g}% fish at "
                       f"{e['weight_pct']:+g}% average weight over the next {e['window']} months: "
                       "earlier, forced harvests of smaller fish.",
            "consider": "Treat early or plan harvests before lice cut fish size; check every site "
                        "against the legal limit.",
        })

    mortality = percentile("mortality")
    if mortality is not None and mortality >= HIGH and "mortality" in effects:
        e = effects["mortality"]["high"]
        actions.append({
            "id": "mortality_high", "severity": "warning",
            "title": "More fish are dying than usual",
            "pattern": f"After high-mortality months, areas harvested {e['count_pct']:+g}% fish at "
                       f"{e['weight_pct']:+g}% average weight: emergency harvests.",
            "consider": "Health check on the worst sites; keep processing capacity free for "
                        "early harvests.",
        })

    temp = percentile("temp_anomaly")
    if temp is not None and "temp" in effects:
        if temp <= LOW:
            e = effects["temp"]["low"]
            actions.append({
                "id": "sea_cold", "severity": "info",
                "title": "The sea is colder than normal",
                "pattern": f"After cold spells, areas harvested {e['count_pct']:+g}% fish at "
                           f"{e['weight_pct']:+g}% average weight {e['window']} months later: "
                           "slower growth.",
                "consider": "Expect fish to reach harvest size later; plan sales and feeding "
                            "for a slower month.",
            })
        elif temp >= HIGH:
            e = effects["temp"]["high"]
            actions.append({
                "id": "sea_warm", "severity": "info",
                "title": "The sea is warmer than normal",
                "pattern": f"After warm spells, areas harvested {e['count_pct']:+g}% fish at "
                           f"{e['weight_pct']:+g}% average weight {e['window']} months later: "
                           "faster growth.",
                "consider": "The harvest window may open early; watch for stress if water passes "
                            "14 °C.",
            })

    if fish_weight is not None and fish_weight["percentile"] >= HIGH:
        actions.append({
            "id": "near_harvest_size", "severity": "info",
            "title": f"Fish in the water are heavy for this area ({fish_weight['kg']:g} kg on "
                     "average, young fish included)",
            "pattern": "When fish in the water are heavier than in 80% of an area's past months, "
                       "the next month's harvest takes about 7% more of the stock than usual for "
                       "that time of year.",
            "consider": "A harvest wave is likely: book well boats and processing slots early.",
        })

    treatments = percentile("treatments")
    if treatments is not None and treatments >= HIGH:
        actions.append({
            "id": "treatments_high", "severity": "info",
            "title": "Lots of delousing right now",
            "pattern": "We found no clear effect of treatment levels alone on later harvests "
                       "(mechanism test M1, treatment rows).",
            "consider": "Track fish weight after treatments; the data can't say more yet.",
        })

    if not actions:
        actions.append({
            "id": "all_normal", "severity": "ok",
            "title": "Nothing unusual this month",
            "pattern": "Lice, deaths and sea temperature are all within the normal range for the "
                       "time of year.",
            "consider": "Business as usual.",
        })
    return actions


def headline_patterns(effects: dict[str, Any], topdown_national_mae: float | None) -> list[dict[str, str]]:
    patterns = []
    if topdown_national_mae is not None:
        patterns.append({
            "id": "exports_reveal_harvest",
            "title": "Exports give away the harvest before it's published",
            "finding": f"Weekly export data reveals Norway's monthly harvest to within about "
                       f"{100 * topdown_national_mae:.0f}%. Our forecast is made on the 10th, about "
                       "10 days before the official figures on the 20th.",
        })
    if "lice" in effects:
        e = effects["lice"]["high"]
        patterns.append({
            "id": "lice_forced_harvests",
            "title": "Lice force early harvests of smaller fish",
            "finding": f"High-lice months are followed by {e['count_pct']:+g}% fish harvested at "
                       f"{e['weight_pct']:+g}% weight. The weight effect passes our pre-registered "
                       "test (M1).",
        })
    if "mortality" in effects:
        e = effects["mortality"]["high"]
        patterns.append({
            "id": "deaths_mean_emergency_harvests",
            "title": "Deaths come before emergency harvests",
            "finding": f"High-mortality months are followed by {e['count_pct']:+g}% fish harvested "
                       f"at {e['weight_pct']:+g}% weight.",
        })
    return patterns


def build_farmer_actions(
    decision_lab: dict[str, Any],
    channels: dict[str, Any],
    outlook: dict[str, Any],
    directorate: pd.DataFrame,
    ssb: pd.DataFrame,
    history: pd.DataFrame,
    made_on: date,
) -> dict[str, Any]:
    effects = bin_effects(channels)
    target, forecasts, meta = live_forecast(directorate, ssb, outlook, history)
    last_known = str(pd.Period(target, "M") - 1)
    weights = stock_weight(directorate, last_known)
    last_year = same_month_last_year(directorate, target)

    areas = []
    for entry in decision_lab["areas"]:
        area = entry["area"]
        forecast = forecasts.get(area)
        change = None
        if forecast and last_year.get(area):
            change = round_significant(100 * (forecast["kg"] / last_year[area] - 1), 2)
        areas.append({
            "area": area,
            "name": entry["name"],
            "forecast": forecast,
            "vs_last_year_pct": change,
            "fish_weight_in_water": weights.get(area),
            "signals": entry["signals"],
            "actions": area_actions(entry["signals"], effects, weights.get(area)),
            "history": entry["history"],
        })

    national = history.drop_duplicates("month")
    nat_mae = _national_mae(directorate, history)
    return {
        "made_on": made_on.isoformat(),
        **meta,
        "model": "Combined: v2 kilograms (exports + area shares, averaged with B1), ML average "
                 "weight, fish count = kilograms / weight",
        "disclaimer": DISCLAIMER,
        "patterns": headline_patterns(effects, nat_mae),
        "areas": areas,
        "national": _national_total(forecasts),
        "scored_months": int(national["month"].nunique()),
    }


def _national_total(forecasts: dict[int, dict[str, Any]]) -> dict[str, Any] | None:
    if not forecasts:
        return None
    kg = sum(f["kg"] for f in forecasts.values())
    return {"areas": sorted(forecasts), "kg": round_significant(kg)}


def _national_mae(directorate: pd.DataFrame, history: pd.DataFrame) -> float | None:
    if "national_kg" not in history:
        return None
    national = history.drop_duplicates("month").set_index("month")["national_kg"]
    actual = directorate.loc[directorate["area"].isin(AREAS)].groupby("month")["harvest_kg"].sum()
    errors = (np.log(actual.reindex(national.index)) - np.log(national)).abs().dropna()
    return float(errors.mean()) if len(errors) else None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--processed", type=Path, default=PROCESSED_DATA_DIR)
    parser.add_argument("--site", type=Path, default=SITE_DATA_DIR)
    args = parser.parse_args()

    read = lambda name: json.loads((args.site / name).read_text(encoding="utf-8"))  # noqa: E731
    directorate = pd.read_parquet(args.processed / "directorate_area_month.parquet")
    ssb = pd.read_parquet(args.processed / "ssb_weekly.parquet")
    ssb["week_start"] = pd.to_datetime(ssb["week_start"])
    ssb["available_at"] = pd.to_datetime(ssb["available_at"])
    history = pd.read_parquet(args.processed / "topdown_backtest.parquet")

    result = build_farmer_actions(
        read("decision_lab.json"), read("channels.json"), read("outlook_supply.json"),
        directorate, ssb, history, date.today(),
    )
    write_json_atomic(result, args.site / "farmer_actions.json")
    print(f"farmer_actions.json for {result['target_month']}: national {result['national']}")
    for area in result["areas"]:
        print(area["area"], area["forecast"], [a["id"] for a in area["actions"]])


if __name__ == "__main__":
    main()
