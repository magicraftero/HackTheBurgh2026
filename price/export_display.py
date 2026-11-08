"""Export the explicitly preferred pricing-results package for the website.

This packages the frozen SISALMONI v2 evaluation. It never retrains or selects a
model, and it never overwrites the legacy SSB/NOK price.json contract.
"""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from price.calendar import week_start
from price.io import atomic_write

ROOT = Path(__file__).resolve().parents[1]
DATASET_ID = "sisalmoni_v2"
DATA_FILE = "price_sisalmoni_v2.json"
MANIFEST_FILE = "price_display_manifest.json"
CHART_FILES = {
    "actual_vs_predicted": "price_sisalmoni_v2_actual_vs_predicted.vl.json",
    "forecast_errors": "price_sisalmoni_v2_forecast_errors.vl.json",
}
DISCLOSURE = (
    "Retrospective evaluation on 24 weeks. Improvement remains unconfirmed: "
    "95% paired block-bootstrap intervals include no benefit. The Ridge result "
    "is experimental; no change remains the recommended live default."
)


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    text = json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + "\n"
    atomic_write(path, lambda p: p.write_text(text, encoding="utf-8"))


def build_payload(selection, final, decision, intervals, predictions):
    model = selection["selected_challenger"]
    if model != decision["selected_challenger"] or model != final["selected_challenger"]:
        raise ValueError("Display model differs from the frozen development selection")
    if selection["dates"] != final["dates"]:
        raise ValueError("Mixed evaluation dates in the pricing display sources")
    if decision["recommended_model"] != "rw" or decision["objective_supported"] is not False:
        raise ValueError("This display version expects the recorded experimental Ridge / no-change recommendation")
    spec = next(s for s in selection["candidate_specs"] if s["id"] == model)
    if spec["kind"] != "ridge" or spec["representation"] != "level" or spec["alpha"] != 10 or spec["groups"]:
        raise ValueError("The display version must be revised explicitly if the frozen model changes")

    def score(model_id, h=4):
        matches = [r for r in final["scores"] if r["h"] == h and r["model"] == model_id]
        if len(matches) != 1:
            raise ValueError(f"Missing or ambiguous display score: {model_id}, h={h}")
        r = matches[0]
        if (r["n"] != 24 or r["planned"] != 24 or r["n_failed"] != 0 or r["coverage"] != 1
                or r["first_target"] != final["dates"]["final_start"]
                or r["last_target"] != final["dates"]["final_end"]):
            raise ValueError("Pricing comparisons must cover the same complete 24-week final segment")
        return r

    primary, rw, old = score(model), score("rw"), score("old_c1")
    h4 = predictions.loc[predictions.h == 4]
    series = []
    for model_id in [model, "rw", "old_c1"]:
        rows = h4.loc[h4.model == model_id].sort_values("target_week")
        if len(rows) != 24 or rows.failed.any() or rows.target_week.duplicated().any():
            raise ValueError("Missing, duplicated or failed display replay forecasts")
        series.append(rows.set_index("target_week"))
    selected_rows, rw_rows, old_rows = series
    if not all(rows.index.equals(selected_rows.index) for rows in series):
        raise ValueError("Pricing display replay contains mismatched target weeks")
    for rows, summary in zip(series, [primary, rw, old], strict=True):
        np.testing.assert_allclose(rows.actual_eur_kg, selected_rows.actual_eur_kg)
        np.testing.assert_allclose((rows.pred_eur_kg - rows.actual_eur_kg).abs().mean(), summary["mae_eur_kg"], rtol=1e-12)
    calls = np.sign(selected_rows.pred_eur_kg - selected_rows.origin_price)
    actual_direction = np.sign(selected_rows.actual_eur_kg - selected_rows.origin_price)
    nonzero = calls != 0
    direction_calls = int(nonzero.sum())
    correct = int((calls[nonzero] == actual_direction[nonzero]).sum())
    np.testing.assert_allclose(correct / direction_calls, primary["directional_accuracy"], rtol=1e-12)
    uncertainty = [r for r in intervals if r["h"] == 4 and r["candidate"] == model
                   and r["baseline"] in {"rw", "old_c1"}]
    if len(uncertainty) != 4 or not all(r["status"] == "estimated" for r in uncertainty):
        raise ValueError("Missing primary paired uncertainty; do not publish headline percentages alone")
    replay = [{"target_week": week, "actual_eur_kg": float(row.actual_eur_kg),
               "selected_ridge_eur_kg": float(row.pred_eur_kg),
               "no_change_eur_kg": float(rw_rows.loc[week, "pred_eur_kg"]),
               "original_biology_eur_kg": float(old_rows.loc[week, "pred_eur_kg"])}
              for week, row in selected_rows.iterrows()]
    return {
        "schema_version": 1,
        "dataset_id": DATASET_ID,
        "display_role": "primary_price_results",
        "title": "SISALMONI price forecast — Ridge v2",
        "status_label": "Experimental · retrospective evaluation",
        "target": {"index": "SISALMONI", "size_class": "3–6 kg", "currency": "EUR", "unit": "EUR/kg"},
        "display_model": {"id": model, "label": "Price-only Ridge v2", "kind": spec["kind"],
                          "target_representation": spec["representation"], "alpha": spec["alpha"],
                          "features": ["current price", "latest weekly log return", "four-week log momentum",
                                       "four-week return volatility", "annual sine", "annual cosine"]},
        "evaluation": {"type": "retrospective", "split": "final", "horizon_delivery_weeks": 4,
                       "target_weeks": [primary["first_target"], primary["last_target"]],
                       "target_dates": [week_start(primary[k]).date().isoformat() for k in ["first_target", "last_target"]],
                       "forecasts": 24, "coverage": primary["coverage"], "fresh_independent_holdout": False,
                       "horizon_note": "Four delivery-week shifts; not four complete weeks after the Thursday issue date."},
        "headline": {"mae_eur_per_kg": primary["mae_eur_kg"],
                     "improvement_vs_no_change_pct": 100 * (1 - primary["mae_eur_kg"] / rw["mae_eur_kg"]),
                     "improvement_vs_original_biology_pct": 100 * (1 - primary["mae_eur_kg"] / old["mae_eur_kg"]),
                     "direction_accuracy_pct": 100 * correct / direction_calls,
                     "direction_correct": correct, "direction_calls": direction_calls,
                     "direction_is_overall_price_accuracy": False},
        "comparisons": [{"model": r["model"], "mae_eur_kg": r["mae_eur_kg"],
                         "rmse_eur_kg": r["rmse_eur_kg"], "log_change_mae": r["log_change_mae"],
                         "n": r["n"], "coverage": r["coverage"]} for r in [primary, rw, old]],
        "uncertainty": {"method": "paired circular block bootstrap", "confidence_level": .95,
                        "intervals": uncertainty, "must_display": DISCLOSURE},
        "recommendation": {"display_model_id": model, "recommended_live_model_id": decision["recommended_model"],
                           "improvement_objective_supported": decision["objective_supported"],
                           "note": "Display the Ridge experiment; keep the no-change live recommendation distinct."},
        "secondary_horizons": [{"horizon_delivery_weeks": h, "forecasts": 24,
                                "selected_ridge_mae_eur_kg": score(model, h)["mae_eur_kg"],
                                "no_change_mae_eur_kg": score("rw", h)["mae_eur_kg"],
                                "original_biology_mae_eur_kg": score("old_c1", h)["mae_eur_kg"]} for h in range(2, 9)],
        "backtest_h4": replay,
        "charts": {name: f"charts/{filename}" for name, filename in CHART_FILES.items()},
    }


def export(experiment, public):
    experiment, public = Path(experiment), Path(public)
    selection_bytes = (experiment / "selection.json").read_bytes()
    digest = hashlib.sha256(selection_bytes).hexdigest()
    provenance = read_json(experiment / "provenance.json")
    if digest != (experiment / "selection.sha256").read_text().strip() or digest != provenance["selection_sha256"]:
        raise ValueError("The display export requires the original completed selection freeze")
    payload = build_payload(json.loads(selection_bytes), read_json(experiment / "final_metrics.json"),
                            read_json(experiment / "decision.json"), read_json(experiment / "paired_uncertainty.json"),
                            pd.read_parquet(experiment / "final_predictions.parquet"))
    payload["provenance"] = {"experiment": "price/experiments/sisalmoni_v2", "selection_sha256": digest,
                             "source_sha256": {name: hashlib.sha256((experiment / name).read_bytes()).hexdigest()
                                               for name in ["final_metrics.json", "final_predictions.parquet", "decision.json", "paired_uncertainty.json"]}}
    manifest = {
        "schema_version": 1, "primary_pricing_dataset": DATASET_ID,
        "use_for_price_results": f"data/{DATA_FILE}", "currency": "EUR", "unit": "EUR/kg",
        "display_model_id": payload["display_model"]["id"],
        "recommended_live_model_id": payload["recommendation"]["recommended_live_model_id"],
        "charts": payload["charts"], "handoff_document": "docs/PRICE_DISPLAY_HANDOFF.md",
        "older_different_results": [
            {"path": "data/price.json", "target": "SSB export price, NOK/kg", "role": "registered SSB F2 archive"},
            {"path": "data/outlook_price.json", "target": "SSB export price, NOK/kg", "role": "earlier ML/SSB outlook"},
            {"path": "price/experiments/sisalmoni/", "target": "SISALMONI EUR/kg", "role": "original unstable OLS experiment; different evaluation dates"},
        ],
        "must_display": DISCLOSURE,
    }
    for name, filename in CHART_FILES.items():
        chart = read_json(experiment / f"{name}.vl.json")
        chart["usermeta"] = {"dataset_id": DATASET_ID, "currency": "EUR", "unit": "EUR/kg",
                             "display_model_id": payload["display_model"]["id"], "evaluation": "retrospective"}
        write_json(public / "charts" / filename, chart)
    write_json(public / "data" / DATA_FILE, payload)
    write_json(public / "data" / MANIFEST_FILE, manifest)
    return payload, manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment", type=Path, default=ROOT / "price/experiments/sisalmoni_v2")
    parser.add_argument("--public", type=Path, default=ROOT / "web/public")
    args = parser.parse_args(argv)
    payload, _ = export(args.experiment, args.public)
    print(f"Primary pricing display: data/{DATA_FILE}; {payload['target']['unit']}; {payload['display_model']['id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
