"""Registered production OLS nowcasts and separately evaluated challengers.

Default execution evaluates development only. Real holdout evaluation is a
separate, time-guarded, once-only CLI operation using a saved development lock.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import importlib.metadata
import json
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from analysis.config import DEVELOPMENT_WINDOW, HOLDOUT_WINDOW, PROCESSED_DATA_DIR, REPO_ROOT
from analysis.io import write_json_atomic, write_parquet_atomic
from analysis.nowcast_data import VintageStore
from analysis.nowcast_evaluate import attach_actuals, summarize, contract_payload, ablation_summary
from analysis.nowcast_inputs import OUTCOMES
from analysis.nowcast_models import fit_predict
from analysis.nowcast_tuning import OnlineTuner, GRIDS, SEED, candidate_config, key_string

FREEZE = datetime(2026, 11, 8, 4, tzinfo=ZoneInfo("Europe/London"))
TRACKS = ("common_training", "available")
FAMILIES = ("ols", "ridge", "catboost")
SOURCE_FILES = ("nowcast_vintages.parquet", "nowcast_features.parquet", "nowcast_targets.parquet")
GROUPS = {
    "stock": ("Stock", ["biomass_anom", "fish_stock_anom"]),
    "market": ("Market", ["export_vol_anom"]),
    "pipeline": ("Smolt pipeline", ["smolt_pipe_anom"]),
    "feed": ("Feed per kg of biomass", ["feed_rate_anom"]),
    "temperature": ("Sea temperature", ["dd_below8", "dd_8to14", "dd_above14"]),
    "losses": ("Mortality and disease", ["mortality_anom", "disease_share"]),
    "lice": ("Mobile lice and treatments", ["mobile_anom", "treat_anom"]),
}


def clean_json(value):
    if isinstance(value, dict):
        return {str(k): clean_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean_json(v) for v in value]
    if isinstance(value, np.generic):
        value = value.item()
    if value is pd.NA or value is pd.NaT:
        return None
    if isinstance(value, float) and not np.isfinite(value):
        return None
    if isinstance(value, (datetime, pd.Timestamp)):
        return value.isoformat()
    return value


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def input_hashes(input_dir):
    return {name: digest(input_dir / name) for name in SOURCE_FILES}


def code_hashes():
    names = ("nowcast.py", "nowcast_models.py", "nowcast_tuning.py", "nowcast_data.py", "nowcast_evaluate.py", "nowcast_inputs.py", "anomalies.py")
    return {name: digest(Path(__file__).parent / name) for name in names}


def check_final_allowed(root, now=None):
    now = now or datetime.now(ZoneInfo("Europe/London"))
    if now.tzinfo is None:
        raise ValueError("Final-run clock must include a timezone")
    if now < FREEZE:
        raise ValueError("Holdout locked until 04:00 Europe/London on 8 November 2026; run development without --final")
    if (Path(root) / "analysis/nowcast_final_run.json").exists():
        raise ValueError("Final nowcast already recorded; preserve the frozen results")


def _tag(frame, family, model, outcome, track):
    diagnostic = frame.attrs.get("diagnostics", {})
    frame = frame.copy()
    frame.attrs = {}
    months = diagnostic.get("training_months", [])
    frame["training_start"] = months[0] if months else None
    frame["training_end"] = months[-1] if months else None
    frame["family"], frame["model"], frame["outcome"], frame["track"] = family, model, outcome, track
    frame["window"] = np.where(frame.month <= DEVELOPMENT_WINDOW.end, "dev", "holdout")
    return frame


def run_development(store, *, families=FAMILIES, progress=None):
    """Nested chronological search; no holdout fit or label is accessible."""
    if store.final or any(m > DEVELOPMENT_WINDOW.end for m in store.months):
        raise ValueError("Development runner requires a partition-protected development store")
    targets = store.targets()
    if (targets.month > DEVELOPMENT_WINDOW.end).any():
        raise ValueError("Development tuning cannot read holdout labels")
    tuner, selected, candidate_rows, decision_rows = OnlineTuner(), [], [], []
    for index, month in enumerate(store.months):
        if month < DEVELOPMENT_WINDOW.start:
            continue
        vintage, feature_sets = store.vintage(month), store.feature_sets(month)
        common = feature_sets["drivers"]
        for track in TRACKS:
            restriction = common if track == "common_training" else None
            for family in families:
                models = ("b0", "b1", "drivers") if family == "ols" else ("b1", "drivers")
                for model in models:
                    for outcome in OUTCOMES:
                        if family == "ols":
                            predicted = _tag(fit_predict(vintage, outcome, feature_sets[model], family,
                                                         sample_features=restriction), family, model, outcome, track)
                            # Actuals are joined only after the forecast exists.
                            selected.append(attach_actuals(predicted, targets.loc[targets.month == month]))
                            continue
                        key = (track, family, model, outcome)
                        chosen, selection = tuner.choose(key, month)
                        candidates = []
                        for candidate in range(len(GRIDS[family])):
                            config, stopping = candidate_config(store, key, candidate, month, targets,
                                                                 sample_features=restriction)
                            raw = fit_predict(vintage, outcome, feature_sets[model], family, config,
                                              sample_features=restriction)
                            predicted = _tag(raw, family, model, outcome, track)
                            scored = attach_actuals(predicted, targets.loc[targets.month == month])
                            audit = scored.copy()
                            audit["candidate"] = candidate
                            audit["early_stopping"] = json.dumps(clean_json(stopping), sort_keys=True)
                            candidate_rows.append(audit)
                            candidates.append(scored)
                        # Selection was fixed BEFORE any current-month labels
                        # were attached; observing errors only affects later months.
                        selected.append(candidates[chosen])
                        decision_rows.append(selection)
                        for candidate, scored in enumerate(candidates):
                            tuner.observe(key, candidate, scored, targets.loc[targets.month == month])
        if progress:
            progress(f"Evaluated {index + 1}/{len(store.months)} development origins ({month})")
    rows = pd.concat(selected, ignore_index=True)
    candidates = pd.concat(candidate_rows, ignore_index=True) if candidate_rows else pd.DataFrame()
    # Lock challenger features and hyperparameters using development alone.
    frozen = {}
    selection_month = str(pd.Period(DEVELOPMENT_WINDOW.end, freq="M") + 1)
    for track in TRACKS:
        restriction = store.feature_sets(store.months[-1])["drivers"] if track == "common_training" else None
        for family in families:
            if family == "ols":
                continue
            for model in ("b1", "drivers"):
                for outcome in OUTCOMES:
                    key = (track, family, model, outcome)
                    chosen, info = tuner.choose(key, selection_month)
                    config, stopping = candidate_config(store, key, chosen, selection_month, targets,
                                                         sample_features=restriction)
                    frozen[key_string(key)] = {"config": config, "selection": info, "early_stopping": stopping,
                                               "features": store.feature_sets(store.months[-1])[model]}
    return rows, candidates, {"configurations": frozen, "online_decisions": decision_rows,
                              "best_challenger": best_challenger(rows),
                              "selection_outcome": "log_kg", "selection_feature_sets": ["b1", "drivers"]}


def best_challenger(predictions):
    part = predictions.loc[(predictions.track == "common_training") & predictions.model.isin(["b1", "drivers"])
                           & (predictions.outcome == "log_kg") & (predictions.window == "dev")
                           & predictions.score_eligible & predictions.family.isin(["ridge", "catboost"])]
    part = part.assign(candidate=part.family + "_" + part.model)
    choices = [family + "_" + model for family in ("ridge", "catboost") for model in ("b1", "drivers")]
    common = part.pivot(index=["area", "month"], columns="candidate", values="abs_error").reindex(columns=choices).dropna()
    if common.empty:
        return {"family": None, "reason": "no_matched_challenger_rows", "n_matched": 0}
    scores = common.mean()
    family, model = str(scores.idxmin()).split("_", 1)
    return {"family": family, "model": model, "reason": "matched_development_log_kg_mae",
            "n_matched": len(common), "mae": {str(k): float(v) for k, v in scores.items()}}


def run_holdout(store, selection, *, families=FAMILIES, progress=None):
    if not store.final:
        raise ValueError("Holdout runner requires an unlocked final store")
    frames = []
    targets = store.targets()
    months = [m for m in store.months if HOLDOUT_WINDOW.start <= m <= HOLDOUT_WINDOW.end]
    for index, month in enumerate(months):
        vintage, sets = store.vintage(month), store.feature_sets(month)
        for track in TRACKS:
            restriction = sets["drivers"] if track == "common_training" else None
            for family in families:
                for model in (("b0", "b1", "drivers") if family == "ols" else ("b1", "drivers")):
                    for outcome in OUTCOMES:
                        config = {} if family == "ols" else selection["configurations"][key_string((track, family, model, outcome))]["config"]
                        if family != "ols" and sets[model] != selection["configurations"][key_string((track, family, model, outcome))]["features"]:
                            raise ValueError("Feature definition changed after the development lock")
                        predicted = _tag(fit_predict(vintage, outcome, sets[model], family, config,
                                                     sample_features=restriction), family, model, outcome, track)
                        frames.append(attach_actuals(predicted, targets.loc[targets.month == month]))
        if progress:
            progress(f"Evaluated {index + 1}/{len(months)} locked holdout origins ({month})")
    if not frames:
        raise ValueError("No holdout vintages available")
    return pd.concat(frames, ignore_index=True)


def run_ablations(store, official, progress=None):
    """Final-only, registered OLS group removals on complete Drivers training."""
    if not store.final:
        raise ValueError("Driver-group ablations run only on the final path")
    frames = [official]
    targets = store.targets()
    for index, month in enumerate(store.months):
        vintage = store.vintage(month)
        full = store.feature_sets(month)["drivers"]
        for group, (_, bases) in GROUPS.items():
            features = [c for c in full if not any(c == b or c == b + "_l1" for b in bases)]
            for outcome in OUTCOMES:
                prediction = _tag(fit_predict(vintage, outcome, features, "ols", sample_features=full),
                                  "ols", "without_" + group, outcome, "common_training")
                frames.append(attach_actuals(prediction, targets.loc[targets.month == month]))
        if progress and index % 12 == 0:
            progress(f"Prepared driver-group ablations through {month}")
    rows = pd.concat(frames, ignore_index=True)
    values = ablation_summary(rows)
    kg = [v for v in values if v["outcome"] == "log_kg"]
    for value in kg:
        value["label"], value["columns"] = GROUPS[value["group"]]
    full = official.loc[(official.model == "drivers") & (official.outcome == "log_kg") & official.score_eligible]
    payload = {"outcome": "log_kg", "window": "2021-01 to 2026-09",
               "full_mae": float(full.abs_error.mean()) if len(full) else None, "groups": kg,
               "by_outcome": {o: [v for v in values if v["outcome"] == o] for o in OUTCOMES if o != "log_kg"}}
    return rows, payload


def report_text(predictions, summaries, selection, audit, final):
    fmt = lambda x: "unavailable" if x is None or not np.isfinite(x) else f"{x:.5g}"
    lines = ["# Production nowcast results", "", "Real observations; expanding monthly windows; no random row split.",
             "Development: 2021-01–2024-12, with eligible pre-2021 training. Holdout: 2025-01–2026-09.",
             "Training/development covers 87 calendar months (2017-10–2024-12); the 21-month test remains separate.", "",
             "## Available-row performance", "", "MAE is in log units. Coverage counts scored area-months, out of 624 per development model/outcome.", "",
             "| Training sample | Window | Family | Predictors | Outcome | MAE | Scored / total |",
             "| --- | --- | --- | --- | --- | ---: | ---: |"]
    for track, summary in summaries.items():
        for row in summary["available"]:
            lines.append(f"| {track} | {row['window']} | {row['family']} | {row['model']} | {row['outcome']} | {fmt(row['mae'])} | {row['n_scored']} / {row['n_total']} |")
    lines += ["", "## Matched-row comparisons", "", "Positive improvement means the right-hand model has lower MAE.", "",
              "| Training sample | Window | Outcome | Left | Right | Rows | MAE left | MAE right | Improvement % |",
              "| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: |"]
    for track, summary in summaries.items():
        for row in summary["matched"]:
            lines.append(f"| {track} | {row['window']} | {row['outcome']} | {row['left']} | {row['right']} | {row['n_matched']} | {fmt(row['mae_left'])} | {fmt(row['mae_right'])} | {fmt(row['right_improvement_pct'])} |")
    lines += ["", "## Selection and numerical limitations", "",
              f"Challenger selection: {json.dumps(selection['best_challenger'], sort_keys=True)}.",
              "Official OLS uses identical complete-Drivers training rows across B0/B1/Drivers. The common_training challenger track uses those same training rows; available allows each model its own eligible rows, including CatBoost's native missing predictors.",
              "All families receive identical numerical feature lists. No area identifiers were added.",
              "Ridge scales predictors inside each training fold. CatBoost early stopping uses an earlier month's own vintage and already-published labels.",
              "Candidate selection uses at most 12 earlier development validation months and at least 3 usable validation months; initial choices are fixed defaults.",
              "A seasonal preparation bug was corrected by rejecting unidentified or catastrophically ill-conditioned seasonal designs; registered terms and transformations were preserved. See PREPARATION_FIX.md.",
              "Sparse area 1 can still have extreme finite seasonal reconstructions even after that correction; no prediction or reconstruction was clipped. Area 13 often has no reconstruction base.", ""]
    for area, info in audit["sparse_areas"].items():
        lines.append(f"Area {area}: {json.dumps(info, sort_keys=True)}.")
    finite = predictions.loc[predictions.eligible & predictions.predicted_log.notna()]
    if len(finite):
        lines += ["", f"Finite log-prediction range across exported forecasts: {finite.predicted_log.min():.6g} to {finite.predicted_log.max():.6g}."]
    lines += ["", "Failures, training sizes, year/area errors and pairwise matched coverage are in nowcast_challengers.json; prediction-level flags are in the Parquet files.",
              "Ordinary logs remain undefined for zero harvests. Missing outcome bases cannot be repaired by Ridge or CatBoost.",
              "Actuals are revised observations, not archived first releases. Capacity weights use today's register and publication dates approximate historical schedules.",
              "Available-row differences can reflect coverage; interpret estimator comparisons using the common_training track and matched rows.", "",
              "## Registered F1", ""]
    official = predictions.loc[(predictions.track == "common_training") & (predictions.family == "ols")]
    f1 = contract_payload(official, final=final)["f1"]
    lines += [json.dumps(clean_json(f1), sort_keys=True) if final else "Unscored. No holdout forecasts or scores were produced; the real --final run is reserved for the 04:00 freeze."]
    return "\n".join(lines) + "\n"


def write_outputs(root, rows, selection, store, provenance, *, candidates=None, final=False, ablations=None):
    root = Path(root)
    official = rows.loc[(rows.track == "common_training") & (rows.family == "ols")].copy()
    summaries = {track: summarize(rows.loc[rows.track == track]) for track in TRACKS}
    site = root / "web/public/data"
    write_json_atomic(clean_json(contract_payload(official, final=final)), site / "nowcast.json")
    challengers = {"windows": {"dev": ["2021-01", "2024-12"], "holdout": ["2025-01", "2026-09"]},
                   "results": summaries, "selection": selection, "features_include_area": False,
                   "holdout_scored": bool(final)}
    write_json_atomic(clean_json(challengers), site / "nowcast_challengers.json")
    processed = root / "data/processed"
    write_parquet_atomic(official, processed / "nowcast_backtest.parquet")
    write_parquet_atomic(rows, processed / "nowcast_challenger_backtest.parquet")
    if candidates is not None and not candidates.empty:
        write_parquet_atomic(candidates, processed / "nowcast_tuning.parquet")
    if ablations is not None:
        ablation_rows, payload = ablations
        write_parquet_atomic(ablation_rows, processed / "nowcast_driver_ablations.parquet")
        write_json_atomic(clean_json(payload), site / "drivers.json")
    analysis = root / "analysis"
    analysis.mkdir(parents=True, exist_ok=True)
    (analysis / "RESULTS.md").write_text(report_text(rows, summaries, selection, store.audit(), final), encoding="utf-8")
    write_json_atomic(clean_json(provenance), analysis / "nowcast_provenance.json")


def main(argv=None, *, now=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=PROCESSED_DATA_DIR)
    parser.add_argument("--output-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--final", action="store_true")
    args = parser.parse_args(argv)
    now = now or datetime.now(ZoneInfo("Europe/London"))
    record = args.output_root / "analysis/nowcast_final_run.json"
    lock_path = args.output_root / "analysis/nowcast_selection.json"
    mutex = args.output_root / "analysis/.nowcast-final.lock"
    if args.final:
        check_final_allowed(args.output_root, now)
    elif record.exists():
        raise ValueError("Frozen final nowcast exists; development cannot replace it")
    inputs = input_hashes(args.input_dir)
    codes = code_hashes()
    provenance = {"generated_at": now.isoformat(), "final": args.final, "inputs": inputs, "code": codes,
                  "versions": {name: importlib.metadata.version(name) for name in ["pandas", "numpy", "pyarrow", "statsmodels", "scikit-learn", "catboost"]},
                  "seed": SEED, "grids": GRIDS, "features_include_area": False,
                  "partitions": {"training_development": ["2017-10", "2024-12"], "holdout": ["2025-01", "2026-09"]}}
    if not args.final:
        store = VintageStore(args.input_dir)
        rows, candidates, selection = run_development(store, progress=lambda s: print(s, flush=True))
        selection.update(inputs=inputs, code=codes, locked_at=now.isoformat(), versions=provenance["versions"])
        write_outputs(args.output_root, rows, selection, store, provenance, candidates=candidates)
        write_json_atomic(clean_json(selection), lock_path)
        print("Wrote development results and selection lock; holdout remains untouched.", flush=True)
        return
    if not lock_path.exists():
        raise ValueError("Run development first to create the challenger selection lock")
    selection = json.loads(lock_path.read_text())
    if selection["inputs"] != inputs or selection["code"] != codes or selection["versions"] != provenance["versions"]:
        raise ValueError("Inputs, implementation or package versions changed after selection; rerun development before freezing")
    mutex.parent.mkdir(parents=True, exist_ok=True)
    with mutex.open("x") as handle:
        handle.write(now.isoformat())
    try:
        store = VintageStore(args.input_dir, final=True)
        development = pd.read_parquet(args.output_root / "data/processed/nowcast_challenger_backtest.parquet",
                                      filters=[("window", "==", "dev")])
        holdout = run_holdout(store, selection, progress=lambda s: print(s, flush=True))
        rows = pd.concat([development, holdout], ignore_index=True)
        official = rows.loc[(rows.track == "common_training") & (rows.family == "ols")]
        ablations = run_ablations(store, official, progress=lambda s: print(s, flush=True))
        write_outputs(args.output_root, rows, selection, store, provenance, final=True, ablations=ablations)
        provenance["selection_sha256"] = digest(lock_path)
        write_json_atomic(clean_json(provenance), record)
        print("Recorded the frozen final nowcast, F1 and driver ablations.", flush=True)
    finally:
        mutex.unlink(missing_ok=True)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, FileNotFoundError, FileExistsError) as error:
        raise SystemExit(f"Production nowcast: {error}")
