"""Audit saved production inputs independently of the build command."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from analysis.config import PROCESSED_DATA_DIR
from analysis.nowcast_inputs import NowcastInputs, model_features, OUTCOMES
from analysis.panel import week_start_from_label
from analysis.validation import require, validate_sources


def audit(directory, input_dir):
    report = json.loads((directory / "production_preparation.json").read_text())
    as_of = pd.Timestamp(report["as_of"])
    sources = {name: pd.read_parquet(input_dir / (name + ".parquet"))
               for name in ["directorate_area_month", "farm_week", "farms", "ssb_weekly"]}
    validate_sources(sources["directorate_area_month"], sources["farm_week"], sources["farms"], sources["ssb_weekly"])
    for name, evidence in report["inputs"].items():
        require(hashlib.sha256((input_dir / name).read_bytes()).hexdigest() == evidence["sha256"], f"Changed input: {name}")
    tables = {}
    for name, summary in report["outputs"].items():
        require(hashlib.sha256((directory / (name + ".parquet")).read_bytes()).hexdigest() == summary["sha256"], f"Output hash changed: {name}")
        frame = pd.read_parquet(directory / (name + ".parquet"))
        require(len(frame) == summary["rows"], f"Row count changed: {name}")
        require(not frame.duplicated(summary["keys"]).any(), f"Duplicate output keys: {name}")
        require(not np.isinf(frame.select_dtypes(include="number").to_numpy(dtype=float, na_value=np.nan)).any(), f"Infinity: {name}")
        for col in frame:
            if pd.api.types.is_datetime64_any_dtype(frame[col]):
                require(str(frame[col].dtype) == "datetime64[ns]", f"Date resolution: {name}.{col}")
        tables[name] = frame
    for name in ["weekly_area_index", "weekly_national_index"]:
        weekly = tables[name]
        starts = week_start_from_label(weekly.week)
        require(weekly.available_at.notna().all(), f"Undated weeks: {name}")
        require(((weekly.available_at >= starts + pd.Timedelta(days=13)) & (weekly.available_at <= as_of)).all(),
                f"Publication bounds: {name}")
        bands = ["dd_below8", "dd_8to14", "dd_above14"]
        require(np.allclose(weekly[bands].sum(axis=1, min_count=3), weekly.dd_anom, equal_nan=True), f"Temperature bands: {name}")
        for col in ["treat_rate", "disease_share"]:
            require(weekly[col].dropna().between(0, 1).all(), f"Invalid rate: {name}.{col}")
        if "area" in weekly:
            require(set(weekly.area) == set(range(1, 14)), "Area indices exclude area 0")
        missing = weekly.n_reporting == 0
        require(weekly.loc[missing, ["mobile_idx", "temp_c", "treat_rate", "disease_share"]].isna().all().all(), "Empty weeks must stay missing")

    # Direct calculation from individual farm rows checks that national
    # weighting is across farms, rather than an unweighted mean of areas.
    latest = tables["weekly_national_index"].week.max()
    fw = sources["farm_week"]
    fw = fw.loc[(fw.week == latest) & fw.reported.fillna(False)].copy()
    farms = sources["farms"]
    fw["weight"] = fw.locality_no.map(farms.set_index("locality_no").capacity_t)
    fw["weight"] = fw.weight.fillna(fw.area.map(farms.groupby("area").capacity_t.median()))
    valid = fw.mobile.notna()
    expected = np.average(fw.loc[valid, "mobile"], weights=fw.loc[valid, "weight"])
    actual = tables["weekly_national_index"].set_index("week").loc[latest, "mobile_idx"]
    require(np.isclose(expected, actual), "National capacity weighting")

    national = tables["drivers_national_month"].set_index("month")
    d = sources["directorate_area_month"]
    sums = d.groupby("month")[["feed_kg", "biomass_kg", "dead", "fish_stock"]].sum()
    sums = sums.reindex(national.index)
    require(np.allclose(national.feed_rate, sums.feed_kg / sums.biomass_kg), "National feed ratio includes area 0")
    require(np.allclose(national.mortality, 1000 * sums.dead / sums.fish_stock), "National mortality ratio includes area 0")

    features = tables["nowcast_features"]
    targets = tables["nowcast_targets"]
    require(features.groupby("month").area.nunique().eq(13).all(), "Forecast grid needs 13 areas")
    require(features.filter(like="_label").isna().all().all(), "Target labels leaked into forecast features")
    require((features.feature_available_at <= features.made_on).all(), "Future data in forecast inputs")
    require(targets.loc[targets.zero_harvest, list(OUTCOMES)].isna().all().all(), "Zero-harvest log labels")
    require(targets.loc[targets.zero_harvest, "avg_kg"].isna().all(), "Zero-harvest average weight")
    if "nowcast_vintages" in tables:
        vintages = tables["nowcast_vintages"]
        require((vintages.month <= vintages.forecast_month).all(), "Future rows in vintage")
        labeled = vintages.filter(like="_label").notna().any(axis=1)
        require((vintages.loc[labeled, "label_available_at"] <= vintages.loc[labeled, "made_on"]).all(), "Unpublished training labels")
        current = vintages.loc[vintages.is_target].reset_index(drop=True)
        pd.testing.assert_frame_equal(current, features)

    # Rebuild one real-data snapshot; changing target/future outcomes and
    # unused stored anomaly columns cannot change a single feature or label.
    cutoff = min("2024-09", features.month.max())
    published_d = d.loc[d.available_at <= as_of]
    ssb = sources["ssb_weekly"].loc[lambda x: x.available_at <= as_of]
    weekly = tables["weekly_area_index"]
    original = NowcastInputs(published_d, weekly, ssb).build_vintage(cutoff)
    altered = published_d.copy()
    cols = ["harvest_kg", "harvest_count", "avg_kg", "biomass_kg", "fish_stock", "smolt_released", "feed_kg", "dead"]
    altered.loc[altered.month >= cutoff, cols] *= 7
    weekly = weekly.copy()
    weekly[["mobile_anom", "treat_anom", "dd_anom", "dd_below8", "dd_8to14", "dd_above14"]] = 999999.
    rebuilt = NowcastInputs(altered, weekly, ssb).build_vintage(cutoff)
    pd.testing.assert_frame_equal(original, rebuilt)
    saved = features.loc[features.month == cutoff].reset_index(drop=True)
    pd.testing.assert_frame_equal(original.loc[original.is_target].reset_index(drop=True), saved)
    print(f"PASS: {len(tables)} output tables; source hashes, publication dates, weights, rates, zero handling and real-data snapshot leakage checks.")
    print(f"{len(features):,} forecast rows; {int(features.drivers_ready.sum()):,} with complete Drivers predictors.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--processed", type=Path, default=PROCESSED_DATA_DIR)
    parser.add_argument("--input-dir", type=Path, default=PROCESSED_DATA_DIR)
    args = parser.parse_args()
    audit(args.processed, args.input_dir)


if __name__ == "__main__":
    main()
