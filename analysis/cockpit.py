"""Data for the "My farm" cockpit prototype in ``cockpit/``.

Writes ``cockpit/data/cockpit.json``: per area and calendar month, the typical share of the stock
harvested and the typical harvest weight; how stock weight ranks in each area; the measured
count and weight effects of lice, deaths and sea temperature (top and bottom thirds against the
middle); and each area's live forecast and signals from ``farmer_actions.json``.

Run from the repository root with ``python -m analysis.cockpit`` after ``analysis.farmer``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Final

import numpy as np
import pandas as pd

from analysis.config import AREAS, PROCESSED_DATA_DIR, SITE_DATA_DIR
from analysis.io import write_json_atomic

COCKPIT_DIR: Final = Path("cockpit") / "data"
CONDITIONS: Final = ("lice", "mortality", "temp")
HEAVY_PERCENTILE: Final = 0.8


def bin_effects_log(channels: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Log-point count and weight effects of the low and high thirds against the middle third."""

    rows: dict[str, dict[int, dict[str, Any]]] = {}
    for row in channels.get("bins", []):
        rows.setdefault(row["driver"], {})[row["tercile"]] = row
    effects = {}
    for driver in CONDITIONS:
        terciles = rows.get(driver, {})
        if {1, 2, 3} - set(terciles):
            continue
        middle = terciles[2]
        effects[driver] = {
            "window": terciles[3]["window"],
            **{
                level: {
                    "count": round(terciles[t]["count_anom"] - middle["count_anom"], 5),
                    "weight": round(terciles[t]["weight_anom"] - middle["weight_anom"], 5),
                }
                for level, t in (("low", 1), ("high", 3))
            },
        }
    return effects


def seasonal_tables(directorate: pd.DataFrame) -> dict[int, dict[str, Any]]:
    """Median monthly harvest rate (harvest / biomass) and harvest weight per area and calendar month."""

    d = directorate.loc[directorate["area"].isin(AREAS)].copy()
    d["calendar_month"] = d["month"].str[5:7].astype(int)
    d["rate"] = d["harvest_kg"] / d["biomass_kg"].where(d["biomass_kg"] > 0)
    d["harvest_weight"] = d["harvest_kg"] / d["harvest_count"].where(d["harvest_count"] > 0)
    d["stock_weight"] = d["biomass_kg"] / d["fish_stock"].where(d["fish_stock"] > 0)

    tables = {}
    for area, group in d.groupby("area"):
        by_month = group.groupby("calendar_month")
        rate = by_month["rate"].median().reindex(range(1, 13))
        weight = by_month["harvest_weight"].median().reindex(range(1, 13))
        stock = group["stock_weight"].dropna()
        tables[int(area)] = {
            "rate": [None if not np.isfinite(v) else round(float(v), 4) for v in rate],
            "harvest_weight": [None if not np.isfinite(v) else round(float(v), 3) for v in weight],
            "stock_weight": {
                "p20": round(float(stock.quantile(0.2)), 2),
                "p50": round(float(stock.quantile(0.5)), 2),
                "p80": round(float(stock.quantile(HEAVY_PERCENTILE)), 2),
            },
        }
    return tables


def heavy_stock_effect(directorate: pd.DataFrame) -> float:
    """Log change in next month's harvest rate, against the same area and calendar month,
    when stock weight is in the area's top fifth."""

    d = directorate.loc[directorate["area"].isin(AREAS)].sort_values(["area", "month"]).copy()
    d["weight"] = d["biomass_kg"] / d["fish_stock"].where(d["fish_stock"] > 0)
    d["rate_next"] = d.groupby("area")["harvest_kg"].shift(-1) / d["biomass_kg"].where(d["biomass_kg"] > 0)
    d["calendar_month"] = d["month"].str[5:7]
    d["rank"] = d.groupby("area")["weight"].rank(pct=True)
    typical = d.groupby(["area", "calendar_month"])["rate_next"].transform("median")
    d["relative"] = d["rate_next"] / typical
    scored = d.loc[np.isfinite(d["relative"]) & (d["relative"] > 0)]
    heavy = scored.loc[scored["rank"] >= HEAVY_PERCENTILE, "relative"].median()
    middle = scored.loc[scored["rank"].between(0.2, HEAVY_PERCENTILE, inclusive="neither"), "relative"].median()
    return round(float(np.log(heavy / middle)), 4)


def latest_price(outlook_price: dict[str, Any] | None) -> dict[str, Any] | None:
    history = (outlook_price or {}).get("history") or []
    return history[-1] if history else None


def build_cockpit(
    directorate: pd.DataFrame,
    channels: dict[str, Any],
    farmer: dict[str, Any],
    outlook_price: dict[str, Any] | None = None,
) -> dict[str, Any]:
    tables = seasonal_tables(directorate)
    areas = []
    for entry in farmer["areas"]:
        area = entry["area"]
        if area not in tables:
            continue
        signals = entry.get("signals", {})
        areas.append({
            "area": area,
            "name": entry["name"],
            **tables[area],
            "forecast": entry.get("forecast"),
            "fish_weight_in_water": entry.get("fish_weight_in_water"),
            "now": {
                "lice": signals.get("lice", {}).get("percentile"),
                "mortality": signals.get("mortality", {}).get("percentile"),
                "temp": signals.get("temp_anomaly", {}).get("percentile"),
            },
        })
    return {
        "target_month": farmer["target_month"],
        "made_on": farmer["made_on"],
        "disclaimer": farmer["disclaimer"],
        "effects": bin_effects_log(channels),
        "heavy_stock": heavy_stock_effect(directorate),
        "national": farmer.get("national"),
        "price": latest_price(outlook_price),
        "areas": areas,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--processed", type=Path, default=PROCESSED_DATA_DIR)
    parser.add_argument("--site", type=Path, default=SITE_DATA_DIR)
    parser.add_argument("--out", type=Path, default=COCKPIT_DIR)
    args = parser.parse_args()

    read = lambda name: json.loads((args.site / name).read_text(encoding="utf-8"))  # noqa: E731
    directorate = pd.read_parquet(args.processed / "directorate_area_month.parquet")
    price_path = args.site / "outlook_price.json"
    outlook_price = read("outlook_price.json") if price_path.exists() else None
    result = build_cockpit(directorate, read("channels.json"), read("farmer_actions.json"), outlook_price)
    args.out.mkdir(parents=True, exist_ok=True)
    write_json_atomic(result, args.out / "cockpit.json")
    print(f"cockpit.json: {len(result['areas'])} areas, heavy stock {result['heavy_stock']:+.3f}, "
          f"effects {sorted(result['effects'])}")


if __name__ == "__main__":
    main()
