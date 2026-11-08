"""Independently audit saved DEVELOPMENT nowcast artifacts.

    python -m analysis.check_nowcast

No estimator or scoring helper is imported. All reported losses are
recomputed from prediction-level development exports. Holdout artifacts are
rejected before their prediction/label rows are materialised.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from analysis.config import DEVELOPMENT_WINDOW, PROCESSED_DATA_DIR, REPO_ROOT
from analysis.nowcast_data import VintageStore
from analysis.nowcast_inputs import OUTCOMES, forecast_date

KEYS = ["track", "family", "model", "outcome", "area", "month"]


def require(condition, message):
    if not bool(condition):
        raise ValueError(message)


def read_json(path):
    def invalid(value):
        raise ValueError(f"Non-standard JSON constant {value} in {path}")
    return json.loads(Path(path).read_text(), parse_constant=invalid)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def close(left, right, name):
    if right is None:
        require(left is None or pd.isna(left), f"{name}: expected unavailable, got {left}")
    else:
        require(left is not None and np.isclose(float(left), float(right), rtol=1e-9, atol=1e-11),
                f"{name}: {left} differs from {right}")


def development_parquet(path):
    # Filter before materialising labels. Comparing the retained length with
    # the file metadata detects ANY out-of-partition rows without reading them.
    total = pq.ParquetFile(path).metadata.num_rows
    frame = pd.read_parquet(path, filters=[("month", ">=", DEVELOPMENT_WINDOW.start),
                                          ("month", "<=", DEVELOPMENT_WINDOW.end)])
    require(len(frame) == total, f"Non-development prediction rows exported in {path.name}")
    require(frame.window.eq("dev").all(), f"Non-development window in {path.name}")
    unique = KEYS + (["candidate"] if "candidate" in frame else [])
    require(not frame.duplicated(unique).any(), f"Duplicate prediction keys in {path.name}")
    return frame


def valid(frame):
    return frame.eligible & np.isfinite(frame.predicted_log) & np.isfinite(frame.actual_log)


def score(frame):
    mask = valid(frame)
    return {"n_total": len(frame),
            "n_predicted": int((frame.eligible & np.isfinite(frame.predicted_log)).sum()),
            "n_scored": int(mask.sum()),
            "coverage": float(mask.mean()) if len(frame) else None,
            "mae": float((frame.loc[mask, "actual_log"] - frame.loc[mask, "predicted_log"]).abs().mean()) if mask.any() else None}


def matching_rows(frame, values):
    mask = pd.Series(True, index=frame.index)
    for name, value in values.items():
        mask &= frame[name].astype(str).eq(str(value))
    return frame.loc[mask]


def check_predictions(frame, name):
    require(frame.month.eq(frame.forecast_month).all(), f"{name}: target and forecast months differ")
    expected_dates = frame.month.map(forecast_date)
    require(pd.to_datetime(frame.made_on).eq(expected_dates).all(), f"{name}: incorrect forecast date")
    mask = valid(frame)
    require(frame.score_eligible.eq(mask).all(), f"{name}: incorrect scoring eligibility")
    expected_error = (frame.actual_log - frame.predicted_log).where(mask)
    require(np.allclose(frame.error, expected_error, equal_nan=True), f"{name}: incorrect signed errors")
    require(np.allclose(frame.abs_error, expected_error.abs(), equal_nan=True), f"{name}: incorrect absolute errors")
    reconstructed = frame.predicted_anomaly + frame.base
    computed = np.isfinite(frame.predicted_log)
    require(np.allclose(frame.loc[computed, "predicted_log"], reconstructed.loc[computed]), f"{name}: seasonal reconstruction differs")
    available = frame.eligible
    require(np.isfinite(frame.loc[available, ["predicted_anomaly", "predicted_log", "predicted_level", "base"]]).all().all(),
            f"{name}: eligible predictions contain non-finite values")
    require((frame.loc[available, "predicted_level"] > 0).all(), f"{name}: eligible prediction has nonpositive level")
    if "minimum_training_rows" in frame:
        require((frame.loc[available, "n_train"] >= frame.loc[available, "minimum_training_rows"]).all(), f"{name}: fit below its declared sample-size requirement")
    ols = available & frame.family.eq("ols")
    require(frame.loc[ols, "rank"].eq(frame.loc[ols, "n_parameters"]).all(), f"{name}: available OLS fit is unidentified")
    require((np.isfinite(frame.loc[ols, "condition"]) & (frame.loc[ols, "condition"] <= 1e12)).all(), f"{name}: available OLS fit is ill conditioned")
    require(np.allclose(frame.loc[available, "predicted_level"], np.exp(frame.loc[available, "predicted_log"])),
            f"{name}: reconstructed levels differ")
    require(frame.loc[~available, "reason"].fillna("").astype(str).str.len().gt(0).all(),
            f"{name}: unavailable forecast has no reason")
    positive = frame.actual_level > 0
    expected_log = np.log(frame.actual_level.where(positive))
    require(np.allclose(frame.actual_log, expected_log, equal_nan=True), f"{name}: actuals are not ordinary logs")


def check_group_scores(frame, records, extra=()):
    columns = ["window", "family", "model", "outcome", *extra]
    derived = frame.assign(year=frame.month.str[:4]) if "year" in extra else frame
    require(len(records) == derived.groupby(columns).ngroups, f"Wrong number of score groups: {columns}")
    for row in records:
        sample = matching_rows(derived, {key: row[key] for key in columns})
        expected = score(sample)
        for key, value in expected.items():
            close(value, row[key], f"{columns}/{row}/{key}")


def check_matched(frame, records):
    for record in records:
        subset = frame.loc[frame.outcome.eq(record["outcome"]) & frame.window.eq(record["window"]) & valid(frame)]
        lf, lm = record["left"].rsplit("_", 1)
        rf, rm = record["right"].rsplit("_", 1)
        left = subset.loc[subset.family.eq(lf) & subset.model.eq(lm)]
        right = subset.loc[subset.family.eq(rf) & subset.model.eq(rm)]
        joined = left.merge(right, on=["area", "month"], suffixes=("_left", "_right"), validate="one_to_one")
        require(len(joined) == record["n_matched"], "Incorrect matched-row count")
        require(np.allclose(joined.actual_log_left, joined.actual_log_right), "Matched actuals disagree")
        ml = float((joined.actual_log_left - joined.predicted_log_left).abs().mean()) if len(joined) else None
        mr = float((joined.actual_log_right - joined.predicted_log_right).abs().mean()) if len(joined) else None
        improvement = 100 * (1 - mr / ml) if ml is not None and ml > 0 and mr is not None else None
        close(ml, record["mae_left"], "Matched left MAE")
        close(mr, record["mae_right"], "Matched right MAE")
        close(improvement, record["right_improvement_pct"], "Matched improvement")
        require(sorted(joined.month.unique()) == record["months"], "Matched months differ")
        require(sorted(int(a) for a in joined.area.unique()) == record["areas"], "Matched areas differ")


def check_selection(selection, tuning):
    decisions = list(selection["online_decisions"])
    decisions.extend(item["selection"] for item in selection["configurations"].values())
    for row in decisions:
        month = row["selection_month"]
        validation = row["validation_months"]
        require(all(v < month and v <= DEVELOPMENT_WINDOW.end for v in validation), "Tuning used current/future or holdout validation months")
        require(validation == sorted(set(validation)), "Validation folds are not unique ordered months")
    for row in tuning[["month", "early_stopping"]].drop_duplicates().itertuples(index=False):
        info = json.loads(row.early_stopping)
        if not info or info.get("validation_month") is None:
            continue
        selection_month = info.get("selection_month", row.month)
        require(info["validation_month"] < selection_month <= row.month, "Early stopping used the scored month or future validation")
        require(info["validation_month"] <= DEVELOPMENT_WINDOW.end, "Early stopping used holdout observations")


def check_scalers(predictions, store):
    ridge = predictions.loc[predictions.family.eq("ridge")]
    checked = 0
    for (month, track, model, outcome), group in ridge.groupby(["month", "track", "model", "outcome"]):
        means = group.scaler_mean.drop_duplicates().tolist()
        scales = group.scaler_scale.drop_duplicates().tolist()
        require(len(means) == len(scales) == 1, "A pooled Ridge fit exported inconsistent scalers")
        exported_mean, exported_scale = json.loads(means[0]), json.loads(scales[0])
        if not exported_mean:
            require(not group.eligible.any(), "A successful Ridge fit has no scaler metadata")
            continue
        vintage = store.vintage(month)
        sets = store.feature_sets(month)
        features = sets[model]
        made_on = forecast_date(month)
        mask = (~vintage.is_target & (vintage.month < month)
                & np.isfinite(vintage[outcome + "_anom"])
                & (vintage.label_available_at <= made_on)
                & (vintage.feature_available_at <= made_on)
                & np.isfinite(vintage[features]).all(axis=1))
        if track == "common_training":
            mask &= np.isfinite(vintage[sets["drivers"]]).all(axis=1)
        values = vintage.loc[mask, features].to_numpy(dtype=float)
        require(len(values) == int(group.n_train.iloc[0]), "Ridge training count differs from published historical rows")
        expected_mean, expected_scale = values.mean(axis=0), values.std(axis=0, ddof=0)
        expected_scale[expected_scale == 0] = 1.
        require(np.allclose(expected_mean, exported_mean, rtol=1e-9, atol=1e-11), "Ridge scaler mean learned outside training fold")
        require(np.allclose(expected_scale, exported_scale, rtol=1e-9, atol=1e-11), "Ridge scaler scale learned outside training fold")
        checked += 1
    return checked


def check_shared_scores(official, payload):
    for outcome in OUTCOMES:
        sample = official.loc[official.outcome.eq(outcome) & valid(official)]
        pivot = sample.pivot(index=["area", "month"], columns="model", values="predicted_log").reindex(columns=["b0", "b1", "drivers"]).dropna()
        actual = sample.drop_duplicates(["area", "month"]).set_index(["area", "month"]).actual_log.reindex(pivot.index)
        for model in ("b0", "b1", "drivers"):
            mae = float((pivot[model] - actual).abs().mean()) if len(pivot) else None
            close(mae, payload["scores"]["dev"][outcome][model], "Shared registered matched MAE")
    require(len(payload["backtest"]) == official[["area", "month"]].drop_duplicates().shape[0], "Shared backtest coverage differs")
    groups = {(int(area), str(month)): group for (area, month), group in official.groupby(["area", "month"])}
    require(len({(r["area"], r["month"]) for r in payload["backtest"]}) == len(groups), "Duplicate shared backtest records")
    display = {"log_kg": "kg", "log_count": "count", "log_avg_kg": "avg_kg"}
    for row in payload["backtest"]:
        group = groups[(row["area"], row["month"])]
        for outcome, key in display.items():
            subset = group.loc[group.outcome.eq(outcome)]
            actual = subset.actual_level.iloc[0]
            close(actual, row["actual"][key], "Shared actual level")
            for model in ("b0", "b1", "drivers"):
                item = subset.loc[subset.model.eq(model)].iloc[0]
                predicted = item.predicted_level if item.eligible else None
                close(predicted, row["pred"][model][key], "Shared predicted level")


def audit(root=REPO_ROOT, input_dir=PROCESSED_DATA_DIR):
    root, input_dir = Path(root), Path(input_dir)
    analysis = root / "analysis"
    provenance = read_json(analysis / "nowcast_provenance.json")
    require(not provenance["final"], "This auditor accepts development artifacts only")
    require(not (analysis / "nowcast_final_run.json").exists(), "Final-run artifacts require a separate audit")
    selection = read_json(analysis / "nowcast_selection.json")
    require(selection["inputs"] == provenance["inputs"], "Selection/provenance input hashes differ")
    require(selection["code"] == provenance["code"], "Selection/provenance code hashes differ")
    require(selection["versions"] == provenance["versions"], "Selection/provenance versions differ")
    for name, expected in provenance["inputs"].items():
        require(sha256(input_dir / name) == expected, f"Prepared input changed: {name}")
    for name, expected in provenance["code"].items():
        require(sha256(Path(__file__).parent / name) == expected, f"Implementation changed: {name}")
    processed = root / "data/processed"
    official = development_parquet(processed / "nowcast_backtest.parquet")
    predictions = development_parquet(processed / "nowcast_challenger_backtest.parquet")
    tuning = development_parquet(processed / "nowcast_tuning.parquet")
    require(official.track.eq("common_training").all() and official.family.eq("ols").all(), "Official file contains a challenger or different training sample")
    expected = predictions.loc[predictions.track.eq("common_training") & predictions.family.eq("ols")]
    pd.testing.assert_frame_equal(official.sort_values(KEYS).reset_index(drop=True), expected.sort_values(KEYS).reset_index(drop=True))
    for name, frame in [("official", official), ("challengers", predictions), ("tuning", tuning)]:
        check_predictions(frame, name)
    payload = read_json(root / "web/public/data/nowcast.json")
    challengers = read_json(root / "web/public/data/nowcast_challengers.json")
    require(payload["scores"]["holdout"] is None and payload["f1"] is None and payload["latest"] is None,
            "Shared findings expose holdout results")
    require(not challengers["holdout_scored"], "Challenger findings expose holdout results")
    require(payload["models"] == ["b0", "b1", "drivers"], "Registered model list changed")
    require(all(row["month"] <= DEVELOPMENT_WINDOW.end and row["window"] == "dev" for row in payload["backtest"]), "Holdout rows in shared findings")
    require(challengers["selection"] == selection, "Findings and locked challenger selection disagree")
    for track, summary in challengers["results"].items():
        part = predictions.loc[predictions.track.eq(track)]
        check_group_scores(part, summary["available"])
        check_group_scores(part, summary["by_year"], ["year"])
        check_group_scores(part, summary["by_area"], ["area"])
        check_matched(part, summary["matched"])
    check_shared_scores(official, payload)
    check_selection(selection, tuning)
    store = VintageStore(input_dir)
    # Predictor files contain no target labels; this check is independent of
    # the prediction exports and avoids reading any holdout target rows.
    features = pd.read_parquet(input_dir / "nowcast_features.parquet", filters=[("month", "<=", DEVELOPMENT_WINDOW.end)])
    require(features[[name + "_label" for name in OUTCOMES]].isna().all().all(), "Target labels present in feature table")
    scalers = check_scalers(predictions, store)
    scaler_candidates = check_scalers(tuning, store)
    sparse = {}
    for area in (1, 13):
        subset = official.loc[official.area.eq(area)]
        sparse[str(area)] = {"rows": len(subset), "eligible": int(subset.eligible.sum()),
                             "reason_counts": {str(k): int(v) for k, v in subset.loc[~subset.eligible, "reason"].value_counts().items()}}
    result = {"prediction_rows": len(predictions), "tuning_rows": len(tuning),
              "ridge_scalers_checked": scalers, "candidate_scalers_checked": scaler_candidates,
              "sparse_areas": sparse}
    print("PASS: development-only exports, locks, chronological tuning, training scalers, reconstruction, coverage and independently recomputed MAEs.")
    print(json.dumps(result, sort_keys=True))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    parser.add_argument("--input-dir", type=Path, default=PROCESSED_DATA_DIR)
    args = parser.parse_args()
    audit(args.root, args.input_dir)


if __name__ == "__main__":
    main()
