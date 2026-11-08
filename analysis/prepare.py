"""Build and audit all production-nowcast input data, without scoring models.

    python -m analysis.prepare --as-of 2026-11-08
"""

import argparse
from datetime import datetime
import hashlib
import importlib.metadata
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from analysis.config import PROCESSED_DATA_DIR, SITE_DATA_DIR
from analysis.io import write_json_atomic, write_parquet_atomic
from analysis.nowcast_inputs import NowcastInputs, build_targets, forecast_date, model_features, OUTCOMES
from analysis.panel import area_month_records, build_production_tables
from analysis.validation import require, validate_sources
from analysis.weekly_indices import build_weekly_indices

INPUT_NAMES = ["directorate_area_month", "farm_week", "farms", "ssb_weekly"]
REUSED_FROM = "origin/production at a61f406a87416cd7c19d58a6559498a9418196f1"


def frame_summary(frame, keys):
    require(not frame.duplicated(keys).any(), f"duplicate output keys: {keys}")
    numeric = frame.select_dtypes(include=["number"])
    require(not np.isinf(numeric.to_numpy(dtype=float, na_value=np.nan)).any(), "infinite output values")
    return {"rows": len(frame), "keys": keys,
            "missing": {c: int(n) for c, n in frame.isna().sum().items() if n}}


def build_all(input_dir, output_dir, site_dir, as_of, through_month="2026-09", write_vintages=True):
    as_of = pd.Timestamp(as_of).normalize()
    sources = {name: pd.read_parquet(input_dir / (name + ".parquet")) for name in INPUT_NAMES}
    validate_sources(sources["directorate_area_month"], sources["farm_week"], sources["farms"], sources["ssb_weekly"])
    # Incomplete / not-yet-public periods cannot enter any production output.
    public = {name: frame.loc[pd.to_datetime(frame.available_at) <= as_of].copy()
              if "available_at" in frame else frame.copy() for name, frame in sources.items()}
    d, fw, farms, ssb = [public[name] for name in INPUT_NAMES]
    require(not d.empty and not fw.empty and not ssb.empty, "No published source data for this as-of date")
    print(f"Validated sources; using farm weeks through {fw.week.max()} as of {as_of.date()}.", flush=True)
    weekly_area, weekly_national = build_weekly_indices(fw, farms)
    tables = build_production_tables(d, ssb, weekly_area, weekly_national)
    targets = build_targets(d)
    inputs = NowcastInputs(d, weekly_area, ssb)
    last_target = min(pd.Period(through_month, freq="M"), as_of.to_period("M") - 1)
    months = [m for m in pd.period_range("2021-01", last_target, freq="M") if forecast_date(m) <= as_of]
    require(bool(months), "No production forecast months are available")
    vintages, features = [], []
    for i, month in enumerate(months):
        vintage = inputs.build_vintage(month)
        current = vintage.loc[vintage.is_target].copy()
        require(current[[name + "_label" for name in OUTCOMES]].isna().all().all(), "target labels leaked into inputs")
        require((current.feature_available_at <= current.made_on).all(), "future source release in target features")
        features.append(current)
        if write_vintages:
            vintages.append(vintage)
        if i % 12 == 0 or i == len(months) - 1:
            print(f"Prepared {i + 1}/{len(months)} monthly vintages ({month}).", flush=True)
    features = pd.concat(features, ignore_index=True)
    outputs = {
        "weekly_area_index": (weekly_area, ["area", "week"]),
        "weekly_national_index": (weekly_national, ["week"]),
        "drivers_area_month": (tables.drivers_area_month, ["area", "month"]),
        "drivers_national_month": (tables.drivers_national_month, ["month"]),
        "area_month_panel": (tables.area_month_panel, ["area", "month"]),
        "nowcast_features": (features, ["area", "month"]),
        "nowcast_targets": (targets, ["area", "month"]),
    }
    if write_vintages:
        outputs["nowcast_vintages"] = (pd.concat(vintages, ignore_index=True), ["forecast_month", "area", "month"])
    summaries = {name: frame_summary(frame, keys) for name, (frame, keys) in outputs.items()}
    for name, (frame, _) in outputs.items():
        path = output_dir / (name + ".parquet")
        write_parquet_atomic(frame, path)
        require(path.stat().st_size < 50_000_000, f"Output exceeds 50 MB: {path}")
        summaries[name]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    write_json_atomic(area_month_records(tables.area_month_panel), site_dir / "area_month.json")

    scored_month = features.month.between("2021-01", "2024-12")
    coverage = {}
    for model, columns in model_features(inputs.include_disease).items():
        coverage[model] = {"predictors": columns, "complete_target_rows": int(features[model + "_ready"].sum()),
                           "total_target_rows": len(features),
                           "dev_complete_target_rows": int(features.loc[scored_month, model + "_ready"].sum()),
                           "missing_predictors": {c: int(features[c].isna().sum()) for c in columns if features[c].isna().any()},
                           "by_outcome": {name: {"forecastable_rows": int((features[model + "_ready"] & features[name + "_base"].notna()).sum())}
                                          for name in OUTCOMES}}
    treatment = weekly_national.set_index("week").treat_rate
    before = treatment.loc[(treatment.index >= "2023-W46") & (treatment.index <= "2024-W09")].mean()
    after = treatment.loc[(treatment.index >= "2024-W46") & (treatment.index <= "2025-W09")].mean()
    finite = lambda value: float(value) if pd.notna(value) else None
    report = {
        "as_of": str(as_of.date()), "sources_reused_from": REUSED_FROM,
        "generated_at": datetime.now(ZoneInfo("Europe/London")).isoformat(),
        "inputs": {name + ".parquet": {"sha256": hashlib.sha256((input_dir / (name + ".parquet")).read_bytes()).hexdigest(),
                                          "source_rows": len(sources[name]), "published_rows": len(public[name])}
                   for name in INPUT_NAMES},
        "outputs": summaries, "coverage": coverage,
        "versions": {name: importlib.metadata.version(name) for name in ["pandas", "numpy", "pyarrow"]},
        "capacity_values_imputed_with_area_median": int(farms.capacity_t.isna().sum()),
        "zero_harvest_area_months": int(targets.zero_harvest.sum()),
        "excluded_unpublished_farm_weeks": int(len(sources["farm_week"]) - len(fw)),
        "treatment_format_diagnostic": {"prior_season_mean_share": finite(before), "following_season_mean_share": finite(after),
                                        "difference_percentage_points": finite(100 * (after - before))},
        "notes": [*tables.notes,
            "Stored panel/driver anomalies use full-sample fits and are for descriptive analysis only.",
            "nowcast_vintages refits anomalies from published levels for each forecast month; target labels remain null.",
            "nowcast_features is the target subset of those vintages, not a substitute for each vintage's training rows.",
            "Targets are latest revised figures. Historical source vintages and farm capacity histories are unavailable.",
            "Zero-harvest outcomes have missing log labels; do not replace those with zero or log1p for the F1 nowcast.",
            "Temperature bands need 3 previous years of same-ISO-week temperatures and 6 consecutive valid weeks.",
            "Missing weeks (especially ISO week 53) can leave temperature bands and nowcast predictors unavailable.",
            "Treatment format changed in 2024-W46; the seasonal comparison is diagnostic, not proof of comparability.",
            "Area 13's descriptive weight anomaly is unavailable when its sparse positive harvests cannot support the registered seasonal fit.",
            "This preparation command does not train or score nowcast models."],
    }
    write_json_atomic(report, output_dir / "production_preparation.json")
    lines = ["# Production data preparation", "", f"Built as of {as_of.date()}; no model scores computed.", "",
             "| Table | Rows |", "| --- | ---: |"]
    lines += [f"| {name} | {summary['rows']:,} |" for name, summary in summaries.items()]
    lines += ["", "| Model inputs | Complete forecast rows | Total |", "| --- | ---: | ---: |"]
    lines += [f"| {name} | {c['complete_target_rows']} | {c['total_target_rows']} |" for name, c in coverage.items()]
    lines += ["", "| Model | Log kg forecastable | Log count forecastable | Log weight forecastable |", "| --- | ---: | ---: | ---: |"]
    lines += [f"| {name} | {c['by_outcome']['log_kg']['forecastable_rows']} | {c['by_outcome']['log_count']['forecastable_rows']} | {c['by_outcome']['log_avg_kg']['forecastable_rows']} |" for name, c in coverage.items()]
    lines += ["", f"{int(farms.capacity_t.isna().sum())} missing capacities use area medians for weighting; source tables stay intact.",
              f"{int(targets.zero_harvest.sum())} zero-harvest area-months retain null average weights and log labels.",
              f"{report['excluded_unpublished_farm_weeks']} farm-week rows excluded because they are not published as of the build date.", "",
              (f"Treatment reporting diagnostic, W46–W09 a year apart: {100 * before:.2f}% → {100 * after:.2f}% of reporting farms treated."
               if pd.notna(before) and pd.notna(after) else "Treatment format diagnostic: comparison periods not yet available."), ""]
    lines += ["- " + note for note in report["notes"]]
    (output_dir / "PRODUCTION_DATA_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {len(outputs)} production tables, area_month.json and preparation reports.", flush=True)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=PROCESSED_DATA_DIR)
    parser.add_argument("--output-dir", type=Path, default=PROCESSED_DATA_DIR)
    parser.add_argument("--site-dir", type=Path, default=SITE_DATA_DIR)
    parser.add_argument("--as-of", default=datetime.now(ZoneInfo("Europe/London")).date().isoformat())
    parser.add_argument("--through-month", default="2026-09")
    parser.add_argument("--no-vintages", action="store_true", help="Only save target rows, not all training snapshots")
    args = parser.parse_args()
    build_all(args.input_dir, args.output_dir, args.site_dir, args.as_of, args.through_month, not args.no_vintages)


if __name__ == "__main__":
    main()
