"""Separate exploratory price-model backtest on public SISALMONI observations.

No Nasdaq history is spliced in. This does not alter the registered SSB F2 run.
Fetch the three public yearly JSON responses first, then run::

    python -m price.sisalmoni --raw-dir data/raw/sisalmoni
"""

import argparse
from datetime import date, datetime
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import platform
import sys
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from price.calendar import iso_week, week_start
from price.dataset import C0_FEATURES, PriceDataset
from price.evaluate import evaluate
from price.io import atomic_write
from price.models import design, fit_predict, target

ROOT = Path(__file__).resolve().parents[1]
FIRST_INDEX_WEEK = "2024-W32"
START, END = "2025-W01", "2026-W44"
SOURCE = "https://salmonprice.com/fishpool/servlets/newt/public/json/fpiAverages?year={year}"
METHOD = "https://www.sitagri.com/sitagri-salmon-index/"
MODELS = ("rw", "ar", "c0", "c1")


def parse_public_years(payloads):
    """Decode settlement-month tables without confusing week 1's ISO year.

The provider's December 2025 table includes 2026-W01. Identical duplicate
observations are harmless, but conflicting values are never silently picked.
"""
    observations = {}
    for payload in payloads:
        year = int(payload["year"])
        for month in payload["months"]:
            month_number = int(month["month"])
            if not 1 <= month_number <= 12:
                raise ValueError("Invalid settlement month")
            for row in month["weeks"]:
                week = int(row["week"])
                iso_year = year + (month_number == 12 and week == 1) - (month_number == 1 and week >= 52)
                monday = pd.Timestamp(date.fromisocalendar(iso_year, week, 1))
                label = iso_week(monday)
                if label < FIRST_INDEX_WEEK:
                    raise ValueError(f"{label}: pre-SISALMONI observation; no historical-index splice allowed")
                value = row["fpiEUR"]
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not np.isfinite(value) or value <= 0:
                    raise ValueError(f"{label}: SISALMONI price must be finite and positive")
                if monday in observations and observations[monday] != float(value):
                    raise ValueError(f"{label}: conflicting duplicate index prices")
                observations[monday] = float(value)
    if not observations:
        raise ValueError("No SISALMONI observations found")
    result = pd.Series(observations, name="price_eur_kg").sort_index()
    result.index = pd.DatetimeIndex(result.index, name="period")
    return result


def retarget_dataset(original, index):
    """Keep SSB export volumes; conservatively use index prices from Thursday.

All older volume observations remain available to the anomaly estimator.
Missing index prices remain NaN, including every pre-index observation.
"""
    ssb = original.ssb.copy()
    ssb["price_nok_kg"] = index.reindex(ssb.index)  # Legacy internal carrier; values are EUR/kg.
    ssb["ssb_available_at"] = ssb.available_at
    index_release = pd.Series(ssb.index + pd.Timedelta(days=10), index=ssb.index)
    ssb["available_at"] = ssb.available_at.where(ssb.available_at >= index_release, index_release)
    return PriceDataset(ssb, original.fx, original.weight, original.monthly,
                        original.weekly, original.notes.copy())


def run_sisalmoni(dataset, lags, *, start=START, end=END, horizons=range(2, 9), progress=None):
    """Original OLS/features and sample rule, with inherited, untuned AR lags."""
    if dataset.weekly is None:
        raise ValueError("SISALMONI comparison requires authoritative weekly biology inputs")
    horizons = tuple(horizons)
    start_date, end_date = week_start(start), week_start(end)
    origins = dataset.ssb.loc[(dataset.ssb.index >= start_date - pd.Timedelta(weeks=max(horizons)))
                              & (dataset.ssb.index <= end_date - pd.Timedelta(weeks=min(horizons)))]
    records, skips = [], {}
    for position, (t, raw) in enumerate(origins.iterrows()):
        frame = dataset.snapshot(raw.available_at)
        if t not in frame.index:
            continue
        for h in horizons:
            T = t + pd.Timedelta(weeks=h)
            if not start_date <= T <= end_date:
                continue
            counts = skips.setdefault(str(h), dict(missing_features=0, insufficient_training=0,
                                                   missing_actual=0, scored=0))
            largest = design(frame, h, lags[h], "c1", dataset.drivers)
            complete = largest.notna().all(axis=1) & frame.p.notna()
            if not complete.loc[t]:
                counts["missing_features"] += 1
                continue
            y = target(frame, h)
            train_targets = frame.index + pd.Timedelta(weeks=h)
            releases = dataset.ssb.available_at.reindex(train_targets).to_numpy()
            valid = complete & y.notna() & (train_targets <= t) & (releases <= raw.available_at.to_datetime64())
            n = int(valid.sum())
            if n <= largest.shape[1]:
                counts["insufficient_training"] += 1
                continue
            if T not in dataset.ssb.index or pd.isna(dataset.ssb.loc[T, "price_nok_kg"]):
                counts["missing_actual"] += 1
                continue
            training_design = largest.loc[valid].to_numpy()
            rank = int(np.linalg.matrix_rank(training_design))
            condition = float(np.linalg.cond(training_design))
            actual_price = float(dataset.ssb.loc[T, "price_nok_kg"])
            actual = float(np.log(actual_price) - frame.loc[t, "p"])
            predictions = {"rw": 0.0}
            ar_columns = [c for c in largest if c not in dataset.feature_columns]
            for model in MODELS[1:]:
                columns = ar_columns if model == "ar" else ar_columns + C0_FEATURES if model == "c0" else list(largest)
                x = largest[columns]
                predictions[model] = fit_predict(x.loc[valid], y.loc[valid], x.loc[[t]])
            if not np.isfinite(list(predictions.values())).all():
                raise ValueError(f"Non-finite log forecast at {iso_week(t)}, h={h}")
            counts["scored"] += 1
            for model, prediction in predictions.items():
                with np.errstate(over="ignore"):
                    predicted_price = float(np.exp(frame.loc[t, "p"] + prediction))
                records.append(dict(origin_week=iso_week(t), target_week=iso_week(T), h=h,
                                    model=model, window="evaluation", y=actual, y_hat=prediction,
                                    error=actual - prediction, actual_eur_kg=actual_price,
                                    pred_eur_kg=predicted_price, n_train=n,
                                    design_columns=largest.shape[1], design_rank=rank,
                                    design_condition=condition,
                                    issue_date=raw.available_at.date().isoformat()))
        if progress and (position % 20 == 0 or position == len(origins) - 1):
            progress(f"Processed {position + 1}/{len(origins)} origins ({iso_week(t)})")
    if not records:
        raise ValueError("No matched index forecasts could be scored: " + json.dumps(skips))
    return pd.DataFrame.from_records(records), {"skips": skips, "lags": lags,
                                                "c1_drivers": dataset.drivers}


def summarize(rows):
    statistics = evaluate(rows, final=False)
    scores = []
    for item in statistics["scorecard"]:
        group = rows.loc[(rows.h == item["h"]) & (rows.model == item["model"])]
        overflow = int((~np.isfinite(group.pred_eur_kg)).sum())
        scores.append({**item, "n": len(group),
                       "mae_eur_kg": None if overflow else float((group.actual_eur_kg - group.pred_eur_kg).abs().mean()),
                       "nonfinite_price_forecasts": overflow,
                       "first_target": group.target_week.min(), "last_target": group.target_week.max(),
                       "min_train": int(group.n_train.min()), "max_train": int(group.n_train.max()),
                       "rank_deficient_origins": int((group.design_rank < group.design_columns).sum()),
                       "min_design_rank": int(group.design_rank.min()),
                       "design_columns": int(group.design_columns.max()),
                       "max_design_condition": float(group.design_condition.max()) if np.isfinite(group.design_condition).all() else None,
                       "max_abs_log_forecast": float(group.y_hat.abs().max())})
    comparison = []
    for cw in statistics["cw"]:
        c0 = next(r for r in scores if r["h"] == cw["h"] and r["model"] == "c0")
        c1 = next(r for r in scores if r["h"] == cw["h"] and r["model"] == "c1")
        comparison.append({**cw, "improvement_pct": 100 * (1 - c1["mae"] / c0["mae"])})
    return {"scorecard": scores, "comparisons": comparison}


def report(metrics, diagnostics, index):
    lines = ["# SISALMONI exploratory price-model test", "",
             "The original model features and OLS estimator are refitted to SISALMONI EUR/kg prices only.",
             "No Nasdaq prices are used or spliced in. The registered SSB F2 result is unchanged.",
             "The public endpoint uses the legacy key fpiEUR for the SISALMONI 3–6kg EUR benchmark. Its fpiNOK history is not used because 2024 NOK observations include blended FPI values.", "",
             f"Public target history: {iso_week(index.index.min())} to {iso_week(index.index.max())}, {len(index)} weeks.",
             f"Requested evaluation targets: {START} to {END}; early targets without enough training are skipped for every model.",
             "AR lag counts are inherited from the frozen SSB run's pre-2019 selection, not selected on this index.",
             "Training expands at each Thursday origin, retaining only labels and drivers public by that date.",
             "The public index is released Wednesday afternoon; Thursday midnight is used conservatively, combined with SSB publication availability. Holiday release timing is approximate.", "",
             "| h | Model | n | MAE log | MAE EUR/kg | MAE / no-change | First target | Last target |",
             "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for r in metrics["scorecard"]:
        nok = "unbounded" if r["mae_eur_kg"] is None else f"{r['mae_eur_kg']:.3f}"
        lines.append(f"| {r['h']} | {r['model']} | {r['n']} | {r['mae']:.6g} | {nok} | {r['mae_ratio']:.4g} | {r['first_target']} | {r['last_target']} |")
    lines += ["", "| h | c1 improvement over c0 | Clark–West p | Secondary Holm p |",
              "| --- | --- | --- | --- |"]
    for r in metrics["comparisons"]:
        p = "unavailable" if r["p"] is None else f"{r['p']:.6g}"
        holm = "primary" if r["p_holm"] is None else f"{r['p_holm']:.6g}"
        lines.append(f"| {r['h']} | {r['improvement_pct']:.3f}% | {p} | {holm} |")
    lines += ["", "## Limits", "",
              "- This is an exploratory target-change experiment, not a new pre-registered F2 decision or independent confirmation.",
              "- The target series starts in 2024; its short training history can make the high-dimensional OLS model unstable. No hyperparameters, feature lists, forecasts or start dates were tuned after seeing results.",
              "- Actuals and exogenous inputs are today's revised observations; historical availability is reconstructed.",
              "- All models are scored on identical origin rows at each horizon, using the original rule n_train > number of c1 columns.",
              "- Every pre-index price and missing index week is NaN. Older SSB export volumes remain available as predictors, but SSB prices are never used as target substitutes.",
              "- Any natural-price overflow is counted and its EUR/kg MAE is explicitly unavailable rather than dropping the forecast.",
              "- Rank deficiency, conditioning and forecast extrema are recorded in metrics.json; forecasts are never clipped or removed for instability.",
              "", "## Sources and reproduction", "",
              f"- [Public weekly index history](https://salmonprice.com/fishpool/public/priceHistory)",
              f"- [Index definition and publication time]({METHOD})", "",
              "`python -m price.sisalmoni --raw-dir data/raw/sisalmoni`", "",
              "The raw response, input and lag-selection hashes and runtime versions are in provenance.json.",
              "", "## Skipped targets", "", "```json", json.dumps(diagnostics["skips"], indent=2), "```", ""]
    return "\n".join(lines)


def _write_json(path, payload):
    # Experimental metrics retain full precision rather than site rounding.
    def scalar(value):
        if isinstance(value, np.generic):
            return value.item()
        raise TypeError(f"Unsupported JSON value: {type(value).__name__}")

    text = json.dumps(payload, ensure_ascii=False, allow_nan=False, indent=2,
                      default=scalar) + "\n"
    atomic_write(path, lambda p: p.write_text(text, encoding="utf-8"))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--input-dir", type=Path, default=ROOT / "data/processed")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "price/experiments/sisalmoni")
    args = parser.parse_args(argv)
    raw_files = sorted(args.raw_dir.glob("*.json"))
    if not raw_files:
        raise FileNotFoundError(f"No public SISALMONI JSON responses in {args.raw_dir}")
    index = parse_public_years(json.loads(p.read_text()) for p in raw_files)
    if index.index.min() != week_start(FIRST_INDEX_WEEK):
        raise ValueError(f"Expected full SISALMONI history starting {FIRST_INDEX_WEEK}")
    lag_file = ROOT / "price/final_run.json"
    lag_record = json.loads(lag_file.read_text())
    selection = lag_record["diagnostics"]["lag_selection"]
    lags = {h: int(selection[str(h)]["p"]) for h in range(2, 9)}
    original = PriceDataset.load(args.input_dir)
    dataset = retarget_dataset(original, index)
    rows, diagnostics = run_sisalmoni(dataset, lags, progress=lambda s: print(s, flush=True))
    metrics = summarize(rows)
    metrics.update({"target": "SISALMONI 3–6kg EUR/kg", "currency": "EUR", "status": "exploratory",
                    "index_from": iso_week(index.index.min()), "index_to": iso_week(index.index.max()),
                    "evaluation_targets": [START, END], "diagnostics": diagnostics})
    inputs = raw_files + [lag_file] + [args.input_dir / f"{name}.parquet" for name in
             ["ssb_weekly", "fx_daily", "directorate_area_month", "weekly_national_index", "drivers_national_month"]
             if (args.input_dir / f"{name}.parquet").exists()]
    provenance = {"generated_at": datetime.now(ZoneInfo("Europe/London")).isoformat(),
                  "sources": [SOURCE.format(year=y) for y in sorted({json.loads(p.read_text())["year"] for p in raw_files})],
                  "inputs": {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},
                  "lag_selection_source": str(lag_file), "lags": lags,
                  "runtime": {"python": platform.python_version(), "executable": sys.executable,
                              "packages": {n: version(n) for n in ["pandas", "numpy", "scipy", "statsmodels", "pyarrow"]}},
                  "code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    args.output_dir.mkdir(parents=True, exist_ok=True)
    atomic_write(args.output_dir / "predictions.parquet", lambda p: rows.to_parquet(p, index=False))
    _write_json(args.output_dir / "metrics.json", metrics)
    _write_json(args.output_dir / "provenance.json", provenance)
    atomic_write(args.output_dir / "RESULTS.md", lambda p: p.write_text(report(metrics, diagnostics, index), encoding="utf-8"))
    print(f"Wrote {len(rows):,} predictions to {args.output_dir}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, FileNotFoundError) as exc:
        print(f"SISALMONI experiment: {exc}", file=sys.stderr)
        raise SystemExit(1)
