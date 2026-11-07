"""Walk-forward price forecasts. Default: development only; --final is locked."""

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from price.anomalies import get_anomaly
from price.calendar import iso_week, week_start
from price.dataset import C0_FEATURES, PriceDataset
from price.evaluate import backtest_prices, evaluate
from price.io import atomic_write, write_json
from price.models import choose_lag, design, fit_predict, target

ROOT = Path(__file__).resolve().parents[1]
WINDOWS = {"dev": ["2021-W01", "2024-W52"], "holdout": ["2025-W01", "2026-W44"]}
FREEZE = datetime(2026, 11, 8, 4, tzinfo=ZoneInfo("Europe/London"))
SOURCES = [
    {"label": "Statistics Norway 03024: fresh/chilled farmed salmon",
     "url": "https://www.ssb.no/en/statbank/table/03024/", "units": "NOK/kg; export tonnes"},
    {"label": "Directorate of Fisheries: biomass statistics by production area",
     "url": "https://register.fiskeridir.no/biomassestatistikk/BIOSTAT-LAKS-OMR/biostat-total-omr.csv",
     "units": "round-weight kg; national totals include area 0"},
    {"label": "Norges Bank exchange rates", "url": "https://data.norges-bank.no/", "units": "NOK per EUR / USD"},
    {"label": "BarentsWatch Fish Health", "url": "https://www.barentswatch.no/fiskehelse/",
     "units": "mobile lice per fish; treatment/disease shares; temperature degree-days"},
]
ROW_COLUMNS = ["origin_week", "h", "model", "window", "y", "y_hat", "error"]


def check_final_allowed(output_root, now=None):
    now = now or datetime.now(ZoneInfo("Europe/London"))
    if now < FREEZE:
        raise ValueError("Holdout locked until 04:00 Europe/London on 8 November 2026; use the default development run.")
    root = Path(output_root)
    if (root / "price/final_run.json").exists():
        raise ValueError("Final run already recorded; preserve the frozen results.")


def run_backtest(dataset, *, final=False, horizons=range(2, 9), windows=None, progress=None):
    """Calculation engine; CLI enforces the real-data final-run time/once guard.

    Tests may pass short synthetic windows. Public CLI windows are fixed.
    """
    windows = windows or WINDOWS
    horizons = tuple(horizons)
    start = week_start(windows["dev"][0])
    end = week_start(windows["holdout" if final else "dev"][1])
    prefit = dataset.snapshot(pd.Timestamp("2018-12-31"))
    lags, selection = {}, {}
    for h in horizons:
        lags[h], selection[h] = choose_lag(prefit, h)
    models = ["rw", "ar", "c0"] + (["c1"] if dataset.weekly is not None else [])
    diagnostics = {"lag_selection": selection, "skips": {}, "first_complete_origin": None,
                   "last_starting_feature": None, "h4_first_dev_training_rows": None,
                   "anomaly_engine": get_anomaly()[1], "models": models}
    rows = []
    origins = dataset.ssb
    # Only construct snapshots that could yield a scored target in this run.
    origins = origins.loc[(origins.index >= start - pd.Timedelta(weeks=max(horizons)))
                          & (origins.index <= end - pd.Timedelta(weeks=min(horizons)))]
    for position, (t, raw) in enumerate(origins.iterrows()):
        frame = dataset.snapshot(raw.available_at)
        if t not in frame.index:
            continue
        for h in horizons:
            T = t + pd.Timedelta(weeks=h)
            if not start <= T <= end:
                continue
            window = "dev" if T <= week_start(windows["dev"][1]) else "holdout"
            key = f"{window}/h{h}"
            skips = diagnostics["skips"].setdefault(key, {"missing_features": 0, "insufficient_training": 0,
                                                        "missing_actual": 0, "scored": 0})
            largest = design(frame, h, lags[h], models[-1], dataset.drivers)
            complete = largest.notna().all(axis=1) & frame.p.notna()
            if h == 4 and diagnostics["first_complete_origin"] is None and complete.any():
                first = complete.index[complete][0]
                starts = {col: largest[col].first_valid_index() for col in largest if col != "const"}
                starts = {col: date for col, date in starts.items() if date is not None}
                diagnostics["first_complete_origin"] = iso_week(first)
                diagnostics["last_starting_feature"] = max(starts, key=starts.get)
            if not complete.loc[t]:
                skips["missing_features"] += 1
                continue
            y = target(frame, h)
            targets = frame.index + pd.Timedelta(weeks=h)
            releases = dataset.ssb.available_at.reindex(targets).to_numpy()
            valid = complete & y.notna() & (targets <= t) & (releases <= raw.available_at.to_datetime64())
            n = int(valid.sum())
            if h == 4 and T == start:
                diagnostics["h4_first_dev_training_rows"] = n
            if n <= largest.shape[1]:
                skips["insufficient_training"] += 1
                continue
            if T not in dataset.ssb.index or pd.isna(dataset.ssb.loc[T, "price_nok_kg"]):
                skips["missing_actual"] += 1
                continue
            actual = float(np.log(dataset.ssb.loc[T, "price_nok_kg"]) - frame.loc[t, "p"])
            predictions = {"rw": 0.0}
            ar_columns = [c for c in largest if c not in dataset.feature_columns]
            for model in models[1:]:
                columns = ar_columns if model == "ar" else ar_columns + C0_FEATURES if model == "c0" else list(largest)
                x = largest[columns]
                predictions[model] = fit_predict(x.loc[valid], y.loc[valid], x.loc[[t]])
            if not all(np.isfinite(list(predictions.values()))):
                raise ValueError(f"Non-finite OLS prediction at {iso_week(t)}, h={h}")
            skips["scored"] += 1
            for model, prediction in predictions.items():
                rows.append({"origin_week": iso_week(t), "h": h, "model": model, "window": window,
                             "y": actual, "y_hat": prediction, "error": actual - prediction})
        if progress and (position % 25 == 0 or position == len(origins) - 1):
            progress(f"Processed {position + 1}/{len(origins)} forecast origins ({iso_week(t)})")
    results = pd.DataFrame(rows, columns=ROW_COLUMNS)
    if results.empty:
        raise ValueError("No forecasts could be scored; check input coverage and missing-feature counts: "
                         + json.dumps(diagnostics["skips"]))
    metrics = evaluate(results, final=final)
    notes = dataset.notes.copy()
    notes += ["Errors and MAE are in log price-change points; prices are NOK/kg.",
              "All models use matched origins and expanding training rows; lags fixed by 2012–2018 BIC.",
              f"Anomaly engine: {diagnostics['anomaly_engine']}.",
              "The 80% interval uses development errors and is not a calibrated coverage guarantee."]
    if not final:
        notes.append("Holdout unscored and locked until the analysis freeze (8 Nov 2026, 04:00 Europe/London).")
    history = dataset.ssb.loc[dataset.ssb.index >= pd.Timestamp("2017-01-02")]
    payload = {"history": history[["week", "price_nok_kg"]].to_dict("records"),
               "c1_drivers": dataset.drivers, "windows": windows, "notes": notes,
               **metrics, "backtest_h4": backtest_prices(results, dataset.ssb, metrics["f2"]) if final else None,
               "current": None}
    return results, payload, diagnostics


def results_text(payload, diagnostics):
    lines = ["# Price results", "", "Real-data walk-forward backtest; no demonstration observations.", "",
             "## Training and availability", "",
             f"First complete origin: {diagnostics['first_complete_origin']}.",
             f"Last-starting feature: {diagnostics['last_starting_feature']}.",
             f"Training rows for the first h=4 development target: {diagnostics['h4_first_dev_training_rows']}.",
             f"Anomaly engine: {diagnostics['anomaly_engine']}.",
             "c1 added drivers: " + (", ".join(payload["c1_drivers"]) or "unavailable") + ".", ""]
    if diagnostics["first_complete_origin"] and diagnostics["first_complete_origin"] > "2020-W01":
        lines += ["WARNING: training starts after 2020-W01; less than one year before development.", ""]
    lines += ["| h | Fixed AR lag p | Pre-2019 BIC rows |", "| --- | --- | --- |"]
    for h, details in diagnostics["lag_selection"].items():
        lines.append(f"| {h} | {details['p']} | {details['n']} |")
    lines += ["", "## Measured performance", "", "MAE is in log points; ratios compare with the random walk.", "",
              "| Window | h | Model | MAE | MAE / RW | Direction hit rate |", "| --- | --- | --- | --- | --- | --- |"]
    fmt = lambda x: "not estimable" if x is None else f"{x:.5g}"
    for row in payload["scorecard"]:
        lines.append(f"| {row['window']} | {row['h']} | {row['model']} | {fmt(row['mae'])} | {fmt(row['mae_ratio'])} | {fmt(row['hit_rate'])} |")
    lines += ["", "| Window | h | CW statistic | One-sided p | Holm p (secondary horizons) |", "| --- | --- | --- | --- | --- |"]
    for row in payload["cw"]:
        lines.append(f"| {row['window']} | {row['h']} | {fmt(row['stat'])} | {fmt(row['p'])} | {fmt(row['p_holm'])} |")
    f2 = payload["f2"]
    lines += ["", "## F2", ""]
    if f2 is None:
        lines += ["Not recorded: holdout unscored. Development results are not the F2 decision."]
    else:
        lines += [f"Holdout result: {f2['pass']}. MAE c0={fmt(f2['mae_c0'])}, c1={fmt(f2['mae_c1'])}; CW p={fmt(f2['cw_p'])}."]
    lines += ["", "## Matched-sample coverage", "", "| Window / horizon | Scored | Missing features | Too little training | Missing actual |",
              "| --- | --- | --- | --- | --- |"]
    for key, counts in diagnostics["skips"].items():
        lines.append(f"| {key} | {counts['scored']} | {counts['missing_features']} | {counts['insufficient_training']} | {counts['missing_actual']} |")
    lines += ["", "## Limitations", ""] + ["- " + note for note in payload["notes"]]
    if any(row["model"] == "c1" and row["h"] == 4 and row["mae_ratio"] is not None and row["mae_ratio"] < .8
           for row in payload["scorecard"]):
        lines += ["", "WARNING: h=4 MAE ratio below 0.8; audit publication timing and leakage before interpreting."]
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=ROOT / "data/processed")
    parser.add_argument("--output-root", type=Path, default=ROOT)
    parser.add_argument("--input-note", action="append", default=[], help="Provenance or caveat to include in the findings")
    parser.add_argument("--final", action="store_true", help="Score the locked holdout once, after the freeze")
    args = parser.parse_args(argv)
    final_record = args.output_root / "price/final_run.json"
    if args.final:
        check_final_allowed(args.output_root)
    elif final_record.exists():
        raise ValueError("Frozen final results already exist; development run would overwrite them.")
    dataset = PriceDataset.load(args.input_dir)
    dataset.notes.extend(args.input_note)
    if args.final and dataset.weekly is None:
        raise ValueError("Cannot freeze F2 without weekly national c1 inputs")
    lock = args.output_root / "price/.final-run.lock"
    if args.final:
        lock.parent.mkdir(parents=True, exist_ok=True)
        with lock.open("x") as handle:
            handle.write(datetime.now(ZoneInfo("Europe/London")).isoformat())
    try:
        rows, payload, diagnostics = run_backtest(dataset, final=args.final, progress=lambda s: print(s, flush=True))
        if args.final and (payload["f2"] is None or payload["f2"]["pass"] is None):
            raise ValueError("F2 is not estimable; final results were not frozen")
        # Provenance is a separate Price-owned sidecar, preserving price.json's schema.
        provenance = {"generated_at": datetime.now(ZoneInfo("Europe/London")).isoformat(),
                      "final": args.final, "sources": SOURCES, "inputs": {}, "diagnostics": diagnostics}
        for path in sorted(args.input_dir.glob("*.parquet")):
            if path.stem in {"ssb_weekly", "fx_daily", "directorate_area_month", "weekly_national_index", "drivers_national_month"}:
                provenance["inputs"][path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
        atomic_write(args.output_root / "data/processed/price_backtest.parquet", lambda p: rows.to_parquet(p, index=False))
        write_json(args.output_root / "web/public/data/price.json", payload)
        write_json(args.output_root / "price/provenance.json", provenance)
        text = results_text(payload, diagnostics)
        atomic_write(args.output_root / "price/RESULTS.md", lambda p: p.write_text(text, encoding="utf-8"))
        if args.final:
            write_json(final_record, provenance)
        print(f"Wrote {len(rows):,} matched predictions; first complete origin {diagnostics['first_complete_origin']}; "
              f"last-starting feature {diagnostics['last_starting_feature']}; first h4 training n="
              f"{diagnostics['h4_first_dev_training_rows']}. F2: {payload['f2']}")
    finally:
        if args.final:
            lock.unlink(missing_ok=True)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, FileNotFoundError, FileExistsError) as exc:
        print(f"Price backtest: {exc}", file=sys.stderr)
        sys.exit(1)
