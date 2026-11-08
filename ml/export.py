"""Site data for the harvest model: outlook_supply.json, cockpit_ml.json and ml/RESULTS.md.

Reads the walk-forward table written by ``ml.supply``, adds rolling conformal
bands, scores the model and the seasonal reference line on the same rows, and
writes the files the site reads. Holdout keys stay null until the --final table
exists.

    python -m ml.export
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from analysis.io import round_significant, write_json_atomic
from analysis.decision_lab import AREA_NAMES, DISCLAIMER, LEVERS
from ml.bands import coverage, month_number, rolling_bands
from ml.config import (
    DEVELOPMENT_WINDOW,
    HOLDOUT_WINDOW,
    MODEL,
    MODEL_LABELS,
    PROCESSED_DATA_DIR,
    SITE_DATA_DIR,
    SUPPLY_BAND_MIN_MONTHS,
    SUPPLY_BAND_MONTHS,
    SUPPLY_HORIZONS,
    SUPPLY_MODELS,
)
from ml.supply import driver_groups, feature_sets

ROOT = Path(__file__).resolve().parents[1]
NOTE = ("Harvest model: the mean of a linear model on every driver and gradient-boosted trees, fixed in "
        "prereg/ML_PLAN.md before any ML run. The seasonal normal is the reference line. "
        "Actuals are latest revised data, not first releases.")
UNITS = {"log_kg": ("t", "tonnes"), "log_count": ("count", "fish"), "log_avg_kg": ("avg_kg", "kg per fish")}
SUPPLY_HORIZON_LABELS = {0: "Last month (not yet published)", 1: "This month", 2: "Next month", 3: "In two months"}
GROUP_LABELS = {
    "stock": "Stock (biomass, fish numbers)", "market": "Market (export volume)", "pipeline": "Smolt pipeline",
    "feed": "Feed per kg of biomass", "temperature": "Sea temperature", "losses": "Losses (deaths, disease)",
    "lice": "Lice and treatments", "recent_harvest": "Recent harvests",
}
R = round_significant


def natural(outcome: str, value: Any) -> float:
    value = float(value)
    if not np.isfinite(value):
        return np.nan
    return float(np.exp(value) / 1000) if outcome == "log_kg" else float(np.exp(value))


# --------------------------------------------------------------------------- supply

def supply_frames(results: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Area rows and national rows (sums over every area forecast in that run), both with bands."""

    rows = results.dropna(subset=list(SUPPLY_MODELS), how="any").copy()
    for name in driver_groups(feature_sets(True)["ml"]):
        # A group a half does not use contributes nothing to that half of the blend.
        missing = pd.Series(np.nan, index=rows.index)
        drivers, ml = rows.get(f"why_drivers_{name}", missing), rows.get(f"why_ml_{name}", missing)
        rows[f"why_blend_{name}"] = (drivers.fillna(0) + ml.fillna(0)).where(drivers.notna() | ml.notna()) / 2
    rows["target_n"] = month_number(rows["month"])
    rows["known_n"] = rows["target_n"] - rows["h"] - 1
    area_rows = rolling_bands(rows, models=SUPPLY_MODELS, by=["h", "outcome"], target="target_n",
                              known="known_n", actual="actual", window=SUPPLY_BAND_MONTHS,
                              minimum=SUPPLY_BAND_MIN_MONTHS)

    # National = the areas forecast in every month, so the series means the same thing throughout.
    areas = sorted(national_area_set(rows))
    totals = []
    for (issued, h, month, window), group in rows.loc[rows["outcome"].isin(["log_kg", "log_count"])].groupby(
            ["issued", "h", "month", "window"]):
        group = group.loc[group["area"].isin(areas)]
        if not set(areas) <= set(group.loc[group["outcome"] == "log_kg", "area"]):
            continue
        if not set(areas) <= set(group.loc[group["outcome"] == "log_count", "area"]):
            continue
        for outcome in ("log_kg", "log_count"):
            part = group.loc[group["outcome"] == outcome]
            entry = {"issued": issued, "h": h, "month": month, "window": window, "outcome": outcome,
                     "actual": np.log(np.exp(part["actual"]).sum()) if part["actual"].notna().all() else np.nan}
            for model in SUPPLY_MODELS:
                entry[model] = np.log(np.exp(part[model]).sum())
            totals.append(entry)
    national = pd.DataFrame(totals)
    if not national.empty:
        national["target_n"] = month_number(national["month"])
        national["known_n"] = national["target_n"] - national["h"] - 1
        national = rolling_bands(national, models=SUPPLY_MODELS, by=["h", "outcome"], target="target_n",
                                 known="known_n", actual="actual", window=SUPPLY_BAND_MONTHS,
                                 minimum=SUPPLY_BAND_MIN_MONTHS)
    return area_rows, national


def national_area_set(rows: pd.DataFrame) -> set:
    scored = rows.loc[rows["window"] != "current"]
    per_month = scored.groupby(["month", "h"])["area"].apply(set)
    return set.intersection(*per_month) if len(per_month) else set()


def supply_scores(rows: pd.DataFrame, window: str) -> list[dict[str, Any]] | None:
    scored = rows.loc[(rows["window"] == window) & rows["actual"].notna()]
    if scored.empty:
        return None
    out = []
    for (h, outcome), group in scored.groupby(["h", "outcome"]):
        key, unit = UNITS[outcome]
        actual_natural = group["actual"].map(lambda v: natural(outcome, v))
        seasonal = (group["seasonal"] - group["actual"]).abs().mean()
        for model in SUPPLY_MODELS:
            mae_log = (group[model] - group["actual"]).abs().mean()
            mae = (group[model].map(lambda v: natural(outcome, v)) - actual_natural).abs().mean()
            out.append({"h": int(h), "outcome": outcome, "model": model, "mae_log": R(mae_log),
                        "mae": R(mae), "unit": unit, "n": int(len(group)),
                        "vs_seasonal_pct": R(100 * (1 - mae_log / seasonal)) if seasonal > 0 else None,
                        "coverage_80": R(coverage(group, model, "actual"))})
    return out


def _values(row: pd.Series | None, outcome: str, column: str) -> float | None:
    return None if row is None else R(natural(outcome, row[column]))


def supply_payload(results: pd.DataFrame, final: bool) -> tuple[dict[str, Any], dict[str, Any]]:
    area_rows, national = supply_frames(results)
    scores = {"dev": supply_scores(area_rows, "dev"), "holdout": supply_scores(area_rows, "holdout") if final else None}
    national_scores = {"dev": supply_scores(national, "dev") if not national.empty else None,
                       "holdout": supply_scores(national, "holdout") if final and not national.empty else None}
    group_names = list(driver_groups(feature_sets(True)["ml"]))

    def entry(group: pd.DataFrame, with_why: bool) -> dict[str, Any]:
        by_outcome = {o: g.iloc[0] for o, g in group.groupby("outcome")}
        first = group.iloc[0]
        item: dict[str, Any] = {"issued": first["issued"], "h": int(first["h"]), "target": first["month"],
                                "window": first["window"]}
        if "area" in group:
            item = {"area": int(first["area"]), **item}
        item["actual"] = {UNITS[o][0]: _values(r, o, "actual") for o, r in by_outcome.items()}
        item["pred"] = {m: {UNITS[o][0]: _values(r, o, m) for o, r in by_outcome.items()} for m in SUPPLY_MODELS}
        item["band"] = {UNITS[o][0]: [_values(r, o, f"lo_{MODEL}"), _values(r, o, f"hi_{MODEL}")]
                        for o, r in by_outcome.items()}
        if with_why and "log_kg" in by_outcome:
            kg = by_outcome["log_kg"]
            item["why"] = {g: R(100 * np.expm1(kg[f"why_{MODEL}_{g}"]))
                           for g in group_names if f"why_{MODEL}_{g}" in kg and np.isfinite(kg[f"why_{MODEL}_{g}"])}
        return item

    keys = ["area", "issued", "h", "month", "window"]
    past = area_rows.loc[area_rows["window"].isin(["dev", "holdout"])]
    backtest = [entry(g, with_why=True) for _, g in past.groupby(keys, sort=True)]
    national_past = national.loc[national["window"].isin(["dev", "holdout"])] if not national.empty else national
    national_rows = [entry(g, with_why=False) for _, g in national_past.groupby(keys[1:], sort=True)] if not national.empty else []

    current = None
    now = area_rows.loc[area_rows["window"] == "current"]
    if not now.empty:
        made_on = now["issued"].iloc[0]
        targets = []
        for h, rows in now.groupby("h"):
            month = rows["month"].iloc[0]
            nat = national.loc[(national["window"] == "current") & (national["h"] == h)] if not national.empty else national
            targets.append({
                "h": int(h), "target": month,
                "publishes_around": (pd.Period(month, "M") + 1).to_timestamp().replace(day=20).strftime("%Y-%m-%d"),
                "national": entry(nat, with_why=False) if not nat.empty else None,
                "areas": [entry(g, with_why=True) for _, g in rows.groupby("area")],
            })
        current = {"made_on": made_on, "model": MODEL,
                   "status": "unverifiable until the Directorate publishes each month", "targets": targets}

    all_areas = set(range(1, 14))
    scored_areas = sorted(int(a) for a in area_rows["area"].unique())
    national_areas = sorted(int(a) for a in national_area_set(area_rows))
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": "final" if final else "development",
        "note": NOTE,
        "model": MODEL,
        "models": [{"id": m, "label": MODEL_LABELS[m]} for m in SUPPLY_MODELS],
        "horizons": [{"h": h, "label": SUPPLY_HORIZON_LABELS[h]} for h in SUPPLY_HORIZONS],
        "units": {key: unit for key, unit in UNITS.values()},
        "groups": [{"id": g, "label": GROUP_LABELS[g]} for g in group_names],
        "windows": {"dev": [DEVELOPMENT_WINDOW.start, DEVELOPMENT_WINDOW.end],
                    "holdout": [HOLDOUT_WINDOW.start, HOLDOUT_WINDOW.end]},
        "band": {"level": 0.8, "model": MODEL,
                 "method": f"rolling quantiles of the model's errors public by the issue date, last {SUPPLY_BAND_MONTHS} months"},
        "areas": {"names": {str(a): AREA_NAMES[a] for a in sorted(all_areas)},
                  "forecast": scored_areas, "not_forecast": sorted(all_areas - set(scored_areas)),
                  "reason": "an area's season needs 24 usable months; areas with many zero-harvest months rarely or never reach it"},
        "national_label": (f"Sum of areas {national_areas[0]}-{national_areas[-1]}, the areas forecast every month "
                           f"(areas {sorted(all_areas - set(national_areas))} excluded)") if national_areas else None,
        "issue_dates": sorted(past["issued"].unique().tolist()),
        "scores": scores,
        "national_scores": national_scores,
        "backtest": backtest,
        "national": national_rows,
        "current": current,
    }
    return payload, {"scores": scores, "national_scores": national_scores}


def cockpit_payload(grids: dict[str, Any]) -> dict[str, Any]:
    """Lever grids for the farmer cockpit, swept through the harvest model's nowcast."""

    def area(entry: dict[str, Any]) -> dict[str, Any]:
        return {"area": entry["area"], "levers": [
            {"id": lever["id"], "feature": lever["feature"], "current": R(lever["current"]),
             "grid": [R(v) for v in lever["grid"]],
             "delta_log": {o: [round(v, 6) for v in values] for o, values in lever["delta_log"].get(MODEL, {}).items()}}
            for lever in entry["levers"]]}

    return {
        "target_month": grids["target_month"], "made_on": grids["made_on"],
        "model": MODEL,
        "status": "unverifiable until the Directorate publishes this month",
        "disclaimer": DISCLAIMER,
        "how": ("forecast_log[o] = baseline_log[o] + sum over levers of interp(value, grid, delta_log[o]). "
                "Each lever is swept on its own with the others at their current values, so the sum is an "
                "approximation when several levers move. Outside the grid, show 'outside past experience'."),
        "levers": [{"id": lever.id, "label": lever.label, "unit": lever.unit} for lever in LEVERS],
        "areas": [area(entry) for entry in grids["areas"]],
    }


# --------------------------------------------------------------------------- results

def _score_table(title: str, scores: dict[str, Any]) -> list[str]:
    lines = [f"## {title}", "",
             "| Window | h | Outcome | " + " | ".join(SUPPLY_MODELS) + " | better than seasonal | 80% band hit | n |",
             "| --- | --- | --- | " + " | ".join("---" for _ in SUPPLY_MODELS) + " | --- | --- | --- |"]
    for window in ("dev", "holdout"):
        rows = scores.get(window) or []
        for (h, outcome), group in pd.DataFrame(rows).groupby(["h", "outcome"]) if rows else []:
            values = group.set_index("model")
            cells = [f"{values.loc[m, 'mae_log']} ({values.loc[m, 'mae']} {values.loc[m, 'unit']})" for m in SUPPLY_MODELS]
            lines.append(f"| {window} | {h} | {outcome} | " + " | ".join(cells)
                         + f" | {values.loc[MODEL, 'vs_seasonal_pct']}% | {values.loc[MODEL, 'coverage_80']}"
                         + f" | {values['n'].iloc[0]} |")
    return lines + [""]


def results_markdown(supply: dict[str, Any] | None, final: bool) -> str:
    lines = ["# Harvest model results", "",
             "The model is the mean of the linear Drivers model and gradient-boosted trees, fixed in "
             "`prereg/ML_PLAN.md` before any ML run; `ml/README.md` says why this model. The seasonal normal is "
             "the reference line.", "",
             f"Run: {'final (holdout scored)' if final else 'development window only; holdout locked'}.", ""]
    if supply:
        lines += _score_table("Areas (matched rows)", supply["scores"])
        if supply.get("national_scores", {}).get("dev"):
            lines += _score_table("Norway total (the areas forecast every month)", supply["national_scores"])
        lines += ["MAE in log points (and natural units per area-month or per national month). "
                  "h = 0 is last month (not yet published), 1 this month, 2 next month, 3 in two months.", ""]
    record = ROOT / "ml" / "final_supply.json"
    if record.exists():
        lines += ["## Final run", "", f"- Holdout scored at {json.loads(record.read_text())['run_at'][:16]}.", ""]
    lines += ["## Caveats", "",
              "- **Season guard (added after the first dev run, before any holdout run).** Area 1's season was "
              "fitted on 11-20 usable months, because its zero-harvest months drop out, and exploded "
              "(season terms of -1884 log points in early 2021). No forecast is made for an area-outcome until its "
              "season has 24 usable months. This leaves out area 13 and all but a few months of area 1.",
              "- At h=0 the model's linear half reproduces the Drivers model in `analysis.nowcast` exactly (tested).",
              "- Bands use only errors public by each issue date; the warm-up (from 2019) is never scored.",
              "- Actuals are latest revised data, not first releases.", ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--processed", type=Path, default=PROCESSED_DATA_DIR)
    parser.add_argument("--site", type=Path, default=SITE_DATA_DIR)
    args = parser.parse_args(argv)

    supply_summary = None
    supply_path = args.processed / "ml_supply_backtest.parquet"
    if supply_path.exists():
        results = pd.read_parquet(supply_path)
        final = bool(results["window"].isin(["holdout", "current"]).any())
        payload, supply_summary = supply_payload(results, final)
        write_json_atomic(payload, args.site / "outlook_supply.json")
        print(f"outlook_supply.json: {len(payload['backtest'])} area rows; model {MODEL}")
        levers = args.processed / "ml_levers.json"
        if levers.exists():
            cockpit = cockpit_payload(json.loads(levers.read_text(encoding="utf-8")))
            write_json_atomic(cockpit, args.site / "cockpit_ml.json")
            print(f"cockpit_ml.json: {len(cockpit['areas'])} areas")
    final = bool(supply_summary and supply_summary["scores"].get("holdout"))
    (ROOT / "ml" / "RESULTS.md").write_text(results_markdown(supply_summary, final), encoding="utf-8")


if __name__ == "__main__":
    main()
