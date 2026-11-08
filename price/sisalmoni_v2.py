"""Frozen development/final SISALMONI experiment with chronological selection.

Run ``python -m price.sisalmoni_v2 run --raw-dir data/raw/sisalmoni``.
The final segment is retrospective: the earlier SISALMONI results are exposed.
"""

import argparse
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import platform
import sys

import numpy as np
import pandas as pd

from price.calendar import iso_week, week_start
from price.dataset import PriceDataset
from price.io import atomic_write
from price.sisalmoni import parse_public_years, retarget_dataset
from price.sisalmoni_v2_core import ALL_FEATURES, build_cases, predict_spec, training_rows

ROOT = Path(__file__).resolve().parents[1]
HORIZONS = tuple(range(2, 9))
PRIMARY_H = 4
MIN_TRAIN = 30
BASELINES = ("rw", "ar1", "old_ar", "old_c0", "old_c1")
GROUP_MODELS = ("ridge_fx", "ridge_exports", "ridge_biology")
SPECS = [
    {"id": "rw", "kind": "rw"},
    {"id": "ar1", "kind": "ar1"},
    *[{"id": f"ridge_{label}_a{alpha}", "kind": "ridge", "representation": representation,
       "alpha": alpha, "groups": []}
      for label, representation in [("log", "log_change"), ("level", "level")]
      for alpha in [10, 100]],
    *[{"id": f"ridge_{group}", "kind": "ridge", "representation": "log_change",
       "alpha": 100, "groups": [group]} for group in ["fx", "exports", "biology"]],
    {"id": "blend", "kind": "blend"},
]
MODEL_IDS = tuple(spec["id"] for spec in SPECS) + ("old_ar", "old_c0", "old_c1")
RULES = {
    "primary_horizon": PRIMARY_H, "primary_metric": "MAE EUR/kg",
    "minimum_training_rows": MIN_TRAIN,
    "feature_group_minimum_development_improvement_pct": 2.0,
    "objective_final_improvement_pct": 10.0,
    "adaptive_minimum_released_primary_forecasts": 8,
    "ties": "ascending stable model ID",
    "feature_group_reference": "ridge_log_a100",
    "evaluation": "retrospective; latest 24 of 117 target weeks; global horizon-aware selection embargo",
}


def write_json(path, value):
    def scalar(obj):
        if isinstance(obj, np.generic):
            return obj.item()
        if isinstance(obj, (pd.Timestamp, datetime)):
            return obj.isoformat()
        if isinstance(obj, Path):
            return str(obj)
        raise TypeError(f"Unsupported JSON value: {type(obj).__name__}")
    text = json.dumps(value, default=scalar, ensure_ascii=False, allow_nan=False, indent=2) + "\n"
    atomic_write(path, lambda p: p.write_text(text, encoding="utf-8"))


def file_hashes(paths):
    return {str(Path(p).resolve()): hashlib.sha256(Path(p).read_bytes()).hexdigest()
            for p in sorted(map(Path, paths), key=str)}


def validate_hashes(hashes):
    for filename, expected in hashes.items():
        path = Path(filename)
        if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f"Frozen input or code changed: {path}")


def evaluation_dates(index):
    if len(index) != 117:
        raise ValueError(f"The frozen protocol expects 117 SISALMONI observations, found {len(index)}")
    if not index.index.equals(pd.date_range(index.index.min(), index.index.max(), freq="W-MON", name=index.index.name)):
        raise ValueError("SISALMONI target history must contain consecutive ISO weeks")
    final_start, final_end = index.index[-24], index.index[-1]
    earliest_origin = final_start - pd.Timedelta(weeks=max(HORIZONS))
    selection_issue = earliest_origin + pd.Timedelta(days=10)
    selection_cutoff = min(index.index[index.index + pd.Timedelta(days=10) <= selection_issue].max(),
                           index.index[-25])
    return {"index_start": iso_week(index.index[0]), "index_end": iso_week(index.index[-1]),
            "dev_end": iso_week(index.index[-25]), "final_start": iso_week(final_start),
            "final_end": iso_week(final_end), "selection_cutoff": iso_week(selection_cutoff),
            "selection_issue_date": selection_issue.date().isoformat(),
            "development_target_count": 93, "final_target_count": 24}


def metrics(rows, planned_counts=None):
    """Score every emitted forecast, retaining failures instead of dropping them."""
    result = []
    if rows.empty:
        return result
    for (h, model), group in rows.groupby(["h", "model"], sort=True):
        expected = int((planned_counts or {}).get(int(h), len(group)))
        pred = group.pred_eur_kg.to_numpy(float)
        actual = group.actual_eur_kg.to_numpy(float)
        finite = np.isfinite(pred) & np.isfinite(actual)
        positive = finite & (pred > 0) & (actual > 0)
        failed = group.failed.fillna(True).to_numpy(bool) | ~positive
        n_failed = int(failed.sum()) + max(0, expected - len(group))
        full = len(group) == expected and n_failed == 0 and expected > 0
        errors = pred - actual
        raw_mae = float(np.abs(errors).mean()) if finite.all() else None
        baseline_price = group.origin_price.to_numpy(float)
        actual_direction = np.sign(actual - baseline_price)
        predicted_direction = np.sign(pred - baseline_price)
        calls = positive & (predicted_direction != 0)
        result.append({"h": int(h), "model": model, "n": len(group), "planned": expected,
                       "n_failed": n_failed, "coverage": float((expected - n_failed) / expected) if expected else 0.0,
                       "mae_eur_kg": raw_mae if full else None,
                       "raw_finite_mae_eur_kg": raw_mae,
                       "rmse_eur_kg": float(np.sqrt(np.mean(errors ** 2))) if full else None,
                       "log_change_mae": float(np.mean(np.abs(np.log(pred / actual)))) if full else None,
                       "directional_accuracy": float(np.mean(predicted_direction[calls] == actual_direction[calls])) if calls.any() else None,
                       "direction_calls": int(calls.sum()),
                       "first_target": group.target_week.min(), "last_target": group.target_week.max(),
                       "min_train": int(group.n_train.min()), "max_train": int(group.n_train.max())})
    return result


def select_models(development_rows):
    """Select only from supplied already-published primary validation errors."""
    primary = development_rows.loc[(development_rows.h == PRIMARY_H)
                                   & ~development_rows.model.isin(["adaptive_policy", "frozen_policy"])]
    expected = primary.groupby("model").size().max() if not primary.empty else 0
    score = {r["model"]: r for r in metrics(primary, {PRIMARY_H: int(expected)})}
    eligible = {name for name, r in score.items() if r["mae_eur_kg"] is not None and r["coverage"] == 1}
    group_reference = score.get("ridge_log_a100", {}).get("mae_eur_kg")
    group_eligible = {}
    for name in GROUP_MODELS:
        value = score.get(name, {}).get("mae_eur_kg")
        accepted = bool(name in eligible and group_reference is not None and group_reference > 0
                        and value <= .98 * group_reference)
        group_eligible[name] = accepted
        if not accepted:
            eligible.discard(name)
    def best(names):
        candidates = [name for name in names if name in eligible]
        return min(candidates, key=lambda name: (score[name]["mae_eur_kg"], name)) if candidates else None
    baseline = best(BASELINES)
    challenger = best(name for name in MODEL_IDS if name not in BASELINES)
    if baseline is None:
        raise ValueError("No fully covered eligible baseline in development")
    policy = best([baseline] + ([challenger] if challenger else []))
    return {"selected_challenger": challenger, "strongest_baseline": baseline,
            "selected_policy": policy, "feature_group_eligible": group_eligible,
            "primary_development_scores": score}


def add_adaptive_policy(rows):
    """Replay selection using only earlier validation outcomes released by each issue."""
    records = []
    for (h, origin), current in rows.groupby(["h", "origin_week"], sort=True):
        issue = pd.Timestamp(current.issue_date.iloc[0])
        prior = rows.loc[(rows.h == PRIMARY_H) & (pd.to_datetime(rows.target_available_at) <= issue)
                         & (pd.to_datetime(rows.issue_date) < issue)]
        count = prior.loc[prior.model == "rw", "origin_week"].nunique()
        chosen = select_models(prior)["selected_policy"] if count >= 8 else "rw"
        selected = current.loc[current.model == chosen]
        if len(selected) != 1:
            raise ValueError(f"Adaptive selection has no matched forecast: {chosen}, {origin}, h={h}")
        record = selected.iloc[0].to_dict()
        record.update(model="adaptive_policy", selected_model=chosen, selection_released_count=int(count))
        records.append(record)
    return pd.concat([rows, pd.DataFrame(records)], ignore_index=True)


def _legacy_lookup(path):
    rows = pd.read_parquet(path)
    if rows.duplicated(["origin_week", "h", "model"]).any():
        raise ValueError("Legacy predictions contain duplicate model/origin/horizon rows")
    return rows.set_index(["origin_week", "h", "model"])


def evaluate_cases(cases, legacy, dates, *, split, selected_policy=None):
    start = week_start(dates["index_start"] if split == "development" else dates["final_start"])
    end = week_start(dates["selection_cutoff"] if split == "development" else dates["final_end"])
    targets = pd.date_range(start, end, freq="W-MON")
    records, counts = [], {}
    for h in HORIZONS:
        frame = cases[h]
        count = {"requested": len(targets), "eligible": 0, "missing_origin_or_features": 0,
                 "insufficient_training": 0, "missing_actual": 0, "missing_legacy": 0}
        for T in targets:
            t = T - pd.Timedelta(weeks=h)
            if t not in frame.index:
                count["missing_origin_or_features"] += 1
                continue
            current = frame.loc[t]
            if not np.isfinite(current[list(ALL_FEATURES)].to_numpy(float)).all():
                count["missing_origin_or_features"] += 1
                continue
            if not np.isfinite(current.actual_price) or current.actual_price <= 0:
                count["missing_actual"] += 1
                continue
            train = training_rows(frame, t)
            if len(train) < MIN_TRAIN:
                count["insufficient_training"] += 1
                continue
            origin_week = iso_week(t)
            keys = [(origin_week, h, model) for model in ["ar", "c0", "c1"]]
            if any(key not in legacy.index for key in keys):
                count["missing_legacy"] += 1
                continue
            if split == "development" and pd.Timestamp(current.target_available_at) > pd.Timestamp(dates["selection_issue_date"]):
                raise ValueError("Development target label would be unavailable at the final selection freeze")
            count["eligible"] += 1
            common = {"h": h, "origin_week": origin_week, "target_week": iso_week(T),
                      "issue_date": pd.Timestamp(current.issue_date).date().isoformat(),
                      "target_available_at": pd.Timestamp(current.target_available_at).date().isoformat(),
                      "origin_price": float(current.origin_price), "actual_eur_kg": float(current.actual_price),
                      "split": split, "n_train": len(train)}
            for spec in SPECS:
                try:
                    prediction, diagnostics = predict_spec(spec, train, current)
                    prediction = float(prediction)
                    failed = not np.isfinite(prediction) or prediction <= 0
                    reason = "non-positive or non-finite price forecast" if failed else ""
                except (ValueError, FloatingPointError, np.linalg.LinAlgError, OverflowError) as exc:
                    prediction, failed, reason = np.nan, True, f"{type(exc).__name__}: {exc}"
                records.append({**common, "model": spec["id"], "pred_eur_kg": prediction,
                                "failed": failed, "reason": reason})
            for key in keys:
                old = legacy.loc[key]
                if (not np.isclose(float(old.actual_eur_kg), float(current.actual_price), rtol=0, atol=1e-12)
                        or pd.Timestamp(old.issue_date) != pd.Timestamp(current.issue_date)):
                    raise ValueError(f"Legacy benchmark alignment mismatch: {key}")
                prediction = float(old.pred_eur_kg)
                records.append({**common, "model": "old_" + key[-1], "pred_eur_kg": prediction,
                                "n_train": int(old.n_train), "failed": not np.isfinite(prediction) or prediction <= 0,
                                "reason": "" if np.isfinite(prediction) and prediction > 0 else "invalid legacy forecast"})
        counts[h] = count
    rows = pd.DataFrame(records)
    if rows.empty:
        raise ValueError(f"No matched {split} forecasts: {counts}")
    if selected_policy is not None:
        selected = rows.loc[rows.model == selected_policy].copy()
        selected["model"] = "frozen_policy"
        selected["selected_model"] = selected_policy
        rows = pd.concat([rows, selected], ignore_index=True)
    return rows, counts


def load_experiment(raw_dir, input_dir, legacy_path):
    raw_files = sorted(Path(raw_dir).glob("*.json"))
    if not raw_files:
        raise FileNotFoundError(f"No SISALMONI observations in {raw_dir}")
    index = parse_public_years(json.loads(p.read_text()) for p in raw_files)
    dataset = retarget_dataset(PriceDataset.load(input_dir), index)
    dates = evaluation_dates(index)
    legacy = _legacy_lookup(legacy_path)
    return index, build_cases(dataset, HORIZONS), legacy, dates, raw_files


def hash_manifest(raw_files, input_dir, legacy_path, output_dir):
    inputs = list(raw_files) + [Path(legacy_path), ROOT / "price/experiments/sisalmoni/provenance.json",
                               ROOT / "price/final_run.json", ROOT / "requirements.txt"]
    inputs += [Path(input_dir) / f"{name}.parquet" for name in
               ["ssb_weekly", "fx_daily", "directorate_area_month", "weekly_national_index", "drivers_national_month"]]
    code = [ROOT / "price" / name for name in
            ["sisalmoni_v2.py", "sisalmoni_v2_core.py", "sisalmoni.py", "dataset.py", "calendar.py", "anomalies.py"]]
    code.append(ROOT / "analysis/anomalies.py")
    plan = Path(output_dir) / "PLAN.md"
    if plan.exists():
        inputs.append(plan)
    return {"inputs": file_hashes(inputs), "code": file_hashes(code)}


def freeze_selection(output_dir, selection):
    output_dir = Path(output_dir)
    path = output_dir / "selection.json"
    if path.exists():
        raise ValueError("Selection is already frozen")
    write_json(path, selection)
    digest = hashlib.sha256(path.read_bytes()).hexdigest() + "\n"
    atomic_write(output_dir / "selection.sha256", lambda p: p.write_text(digest, encoding="ascii"))


def ensure_final_allowed(output_dir, selection):
    output_dir = Path(output_dir)
    if (output_dir / "final_metrics.json").exists():
        raise ValueError("Final evaluation already completed; preserve its frozen results")
    if not (output_dir / "selection.json").exists():
        raise ValueError("Final evaluation requires a written selection freeze")
    freeze_path = output_dir / "selection.json"
    digest_path = output_dir / "selection.sha256"
    if not digest_path.exists() or digest_path.read_text().strip() != hashlib.sha256(freeze_path.read_bytes()).hexdigest():
        raise ValueError("Frozen selection changed or its digest is missing")
    if json.loads(freeze_path.read_text()) != selection:
        raise ValueError("Selection payload differs from the written freeze")
    validate_hashes(selection["hashes"]["inputs"])
    validate_hashes(selection["hashes"]["code"])
    if selection.get("candidate_specs") != SPECS or selection.get("rules") != RULES:
        raise ValueError("Frozen candidate definitions or selection rules changed")


def ensure_requested_inputs(selection, raw_dir, input_dir, legacy_path, output_dir):
    """Bind final CLI arguments to the exact data files frozen in development."""
    raw_files = sorted(Path(raw_dir).glob("*.json"))
    requested = hash_manifest(raw_files, input_dir, legacy_path, output_dir)["inputs"]
    if requested != selection["hashes"]["inputs"]:
        raise ValueError("Requested final input paths or contents differ from the frozen development inputs")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["develop", "final", "run"])
    parser.add_argument("--raw-dir", type=Path, default=ROOT / "data/raw/sisalmoni")
    parser.add_argument("--input-dir", type=Path, default=ROOT / "data/processed")
    parser.add_argument("--legacy-predictions", type=Path, default=ROOT / "price/experiments/sisalmoni/predictions.parquet")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "price/experiments/sisalmoni_v2")
    args = parser.parse_args(argv)
    output = args.output_dir
    selection_path = output / "selection.json"
    if args.phase in {"develop", "run"} and selection_path.exists():
        if args.phase == "develop":
            raise ValueError("Development selection already frozen; do not tune against the final segment")
        selection = json.loads(selection_path.read_text())
        ensure_final_allowed(output, selection)
    elif args.phase in {"develop", "run"}:
        index, cases, legacy, dates, raw_files = load_experiment(args.raw_dir, args.input_dir, args.legacy_predictions)
        rows, counts = evaluate_cases(cases, legacy, dates, split="development")
        rows = add_adaptive_policy(rows)
        primary_rows = rows.loc[rows.h == PRIMARY_H]
        selected = select_models(primary_rows)
        selection = {**selected, "dates": dates, "candidate_specs": SPECS, "baseline_ids": list(BASELINES),
                     "rules": RULES, "hashes": hash_manifest(raw_files, args.input_dir, args.legacy_predictions, output),
                     "frozen_at": datetime.now(timezone.utc).isoformat(),
                     "interpretation": "retrospective evaluation; existing SISALMONI outcomes have been inspected"}
        atomic_write(output / "development_predictions.parquet", lambda p: rows.to_parquet(p, index=False))
        write_json(output / "development_metrics.json", {"scores": metrics(rows, {h: c["eligible"] for h, c in counts.items()}),
                                                        "coverage": counts, "dates": dates})
        freeze_selection(output, selection)
        print("Development selection frozen:", {k: selected[k] for k in
                                                ["selected_challenger", "strongest_baseline", "selected_policy"]}, flush=True)
        if args.phase == "develop":
            return 0
    else:
        if not selection_path.exists():
            raise ValueError("Run development and freeze selection before the final phase")
        selection = json.loads(selection_path.read_text())
    ensure_final_allowed(output, selection)
    ensure_requested_inputs(selection, args.raw_dir, args.input_dir, args.legacy_predictions, output)
    # Loading a new invocation's cases never changes the frozen choices.
    if "cases" not in locals():
        index, cases, legacy, dates, raw_files = load_experiment(args.raw_dir, args.input_dir, args.legacy_predictions)
    if dates != selection["dates"]:
        raise ValueError("Target dates changed after selection was frozen")
    rows, counts = evaluate_cases(cases, legacy, dates, split="final", selected_policy=selection["selected_policy"])
    if any(c["eligible"] != 24 for c in counts.values()):
        raise ValueError(f"Final coverage incomplete; preserve dates and investigate: {counts}")
    final_scores = metrics(rows, {h: 24 for h in HORIZONS})
    atomic_write(output / "final_predictions.parquet", lambda p: rows.to_parquet(p, index=False))
    write_json(output / "provenance.json", {"generated_at": datetime.now(timezone.utc).isoformat(),
                                          "hashes": selection["hashes"], "selection_sha256": hashlib.sha256(selection_path.read_bytes()).hexdigest(),
                                          "runtime": {"python": platform.python_version(), "executable": sys.executable,
                                                      "packages": {n: version(n) for n in ["pandas", "numpy", "scipy", "statsmodels", "pyarrow"]}}})
    write_json(output / "final_metrics.json", {"scores": final_scores, "coverage": counts, "dates": dates,
                                             "selected_challenger": selection["selected_challenger"],
                                             "strongest_baseline": selection["strongest_baseline"],
                                             "selected_policy": selection["selected_policy"]})
    print("Final retrospective evaluation saved; no model selection changed.", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, FileNotFoundError) as exc:
        print(f"SISALMONI v2: {exc}", file=sys.stderr)
        raise SystemExit(1)
