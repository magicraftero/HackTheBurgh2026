"""Directorate of Fisheries biomass statistics -> data/processed/directorate_area_month.parquet

One row per production area (0 = the "(null)" row of suppressed data, 1-13) and month,
salmon only, summed over stocking year (UTSETTSÅR).

Run: python -m pipeline.fetch_directorate [--offline]   (--offline reuses the newest raw file)
"""

from __future__ import annotations

import sys

import pandas as pd

from pipeline.common import available_at_dir, month_str, write_parquet
from pipeline.release_log import download, latest_raw, log_download

URL = "https://register.fiskeridir.no/biomassestatistikk/BIOSTAT-LAKS-OMR/biostat-total-omr.csv"

COLUMNS = {
    "UTTAK_STK": "harvest_count",
    "UTTAK_KG": "harvest_kg",  # round-weight equivalent: gutted × 1.125 plus round weight
    "BIOMASSE_KG": "biomass_kg",
    "BEHFISK_STK": "fish_stock",
    "UTSETT_SMOLT_STK": "smolt_released",
    "DØDFISK_STK": "dead",
    "FORFORBRUK_KG": "feed_kg",
}
INT_COLUMNS = ["harvest_count", "fish_stock", "smolt_released", "dead"]
FLOAT_COLUMNS = ["harvest_kg", "biomass_kg", "feed_kg"]


def load(path) -> pd.DataFrame:
    raw = pd.read_csv(path, sep=";", encoding="utf-8-sig")
    missing = {"ÅR", "MÅNED_KODE", "PO_KODE", "ARTSID", "UTSETTSÅR", *COLUMNS} - set(raw.columns)
    if missing:
        raise SystemExit(f"Directorate file is missing columns: {sorted(missing)}")

    raw = raw[raw["ARTSID"] == "LAKS"].copy()
    raw["area"] = raw["PO_KODE"].replace("(null)", "0").astype(int)
    df = (raw.groupby(["area", "ÅR", "MÅNED_KODE"], as_index=False)[list(COLUMNS)].sum()
             .rename(columns=COLUMNS))
    df["month"] = [month_str(y, m) for y, m in zip(df["ÅR"], df["MÅNED_KODE"])]
    df["avg_kg"] = df["harvest_kg"] / df["harvest_count"].where(df["harvest_count"] > 0)
    df["available_at"] = [available_at_dir(m) for m in df["month"]]

    df[INT_COLUMNS] = df[INT_COLUMNS].astype("int64")
    df[FLOAT_COLUMNS + ["avg_kg"]] = df[FLOAT_COLUMNS + ["avg_kg"]].astype("float64")
    cols = ["area", "month", "harvest_count", "harvest_kg", "avg_kg", "biomass_kg",
            "fish_stock", "smolt_released", "dead", "feed_kg", "available_at"]
    return df[cols].sort_values(["month", "area"]).reset_index(drop=True)


def check(df: pd.DataFrame) -> bool:
    ok = True
    months = sorted(df["month"].unique())
    print(f"months {months[0]} .. {months[-1]} ({len(months)}), areas {sorted(df['area'].unique())}")

    per_month = df.groupby("month")["area"].nunique()
    if (per_month != 14).any():
        print("WARNING: months without all areas 0-13:", per_month[per_month != 14].to_dict())
        ok = False

    num = INT_COLUMNS + FLOAT_COLUMNS
    neg = df[(df[num] < 0).any(axis=1)]
    if len(neg):
        print(f"WARNING: {len(neg)} rows with negative values:\n{neg}")
        ok = False
    no_feed = df[(df["biomass_kg"] > 0) & (df["feed_kg"] == 0)]
    if len(no_feed):
        print(f"note: {len(no_feed)} area-months with biomass but zero feed:")
        print(no_feed[["area", "month", "biomass_kg"]].to_string(index=False))

    # Unit jumps: national feed per kg of biomass and deaths per 1,000 fish, median by year.
    nat = df.groupby("month")[["feed_kg", "biomass_kg", "dead", "fish_stock"]].sum()
    nat["feed_rate"] = nat["feed_kg"] / nat["biomass_kg"]
    nat["mortality"] = 1000 * nat["dead"] / nat["fish_stock"]
    yearly = nat.groupby(nat.index.str[:4])[["feed_rate", "mortality"]].median()
    print("national yearly medians:\n" + yearly.round(4).to_string())
    ratio = yearly / yearly.shift(1)
    jumps = ratio[((ratio > 2) | (ratio < 0.5)).any(axis=1)]
    if len(jumps):
        print(f"WARNING: unit jump (>2x year on year) in:\n{jumps}")
        ok = False

    zero = df[(df["area"] > 0) & df["avg_kg"].isna()]
    print(f"area-months (1-13) with zero harvest: {len(zero)}")

    latest = df[df["month"] == months[-1]]
    n = latest[["harvest_count", "harvest_kg"]].sum()
    print(f"national {months[-1]}: {n.harvest_count / 1e6:.1f} m fish, "
          f"{n.harvest_kg / 1e3:,.0f} t, "
          f"{n.harvest_kg / n.harvest_count:.2f} kg/fish")
    return ok


def main() -> None:
    path = latest_raw("directorate", "*.csv") if "--offline" in sys.argv else download(URL, "directorate", ".csv")
    df = load(path)
    ok = check(df)
    write_parquet(df, "directorate_area_month.parquet")
    months = sorted(df["month"].unique())
    log_download("directorate", months[0], months[-1], available_at_dir(months[-1]), path, len(df))
    if not ok:
        print("CHECKS FAILED: table pushed as-is; tell your human before rescaling anything.")


if __name__ == "__main__":
    main()
