"""Directorate aquaculture register + BarentsWatch sites -> data/processed/farms.parquet

The register has one row per licence × site × species. We keep marine (SJØ, HAV) sites
licensed for salmon or trout and deduplicate to one row per site (locality number).
Capacity is the site's licensed capacity when given in tonnes, otherwise null.

Sites that appear in BarentsWatch but not in today's register (mostly closed sites) are
added from BarentsWatch: coordinates and area from its latest report, capacity null.
Rows without an area 1-13 are dropped and counted.

Run: python -m pipeline.fetch_register [--offline]   (needs the BarentsWatch lice files)
"""

from __future__ import annotations

import sys

import pandas as pd

from pipeline import bw_raw
from pipeline.common import write_parquet
from pipeline.release_log import download, latest_raw, log_download

URL = "https://api.fiskeridir.no/pub-aqua/api/v1/dump/new-legacy-csv-file"
SALMONIDS = {"Laks", "Regnbueørret", "Ørret"}


def load_register(path) -> pd.DataFrame:
    # Line 1 is a title ("AKVAKULTURTILLATELSER PR. <date>"), the header is line 2.
    r = pd.read_csv(path, sep=";", skiprows=1, dtype=str, encoding="utf-8")
    r = r[r["LOK_PLASS"].isin(["SJØ", "HAV"]) & r["ART"].isin(SALMONIDS)].copy()
    r["locality_no"] = r["LOK_NR"].astype(int)
    r["capacity_t"] = pd.to_numeric(r["LOK_KAP"], errors="coerce").where(r["LOK_ENHET"] == "TN")
    sites = r.groupby("locality_no").agg(
        name=("LOK_NAVN", "first"),
        lat=("N_GEOWGS84", "first"),
        lon=("Ø_GEOWGS84", "first"),
        area=("PROD_OMR", "first"),
        capacity_t=("capacity_t", "max"),
    ).reset_index()
    sites[["lat", "lon"]] = sites[["lat", "lon"]].apply(pd.to_numeric, errors="coerce")
    sites["area"] = pd.to_numeric(sites["area"], errors="coerce").astype("Int64")
    return sites


def bw_sites() -> pd.DataFrame:
    lice = bw_raw.load("lice")
    lice = lice.assign(area=pd.to_numeric(lice["ProduksjonsområdeId"], errors="coerce")).sort_values(["År", "Uke"])
    # last() skips blanks, so each field comes from the latest report that has it.
    last = lice.groupby("Lokalitetsnummer")[["Lokalitetsnavn", "Lat", "Lon", "area"]].last().reset_index()
    return pd.DataFrame({
        "locality_no": last["Lokalitetsnummer"].astype(int),
        "name": last["Lokalitetsnavn"],
        "lat": last["Lat"].astype(float),
        "lon": last["Lon"].astype(float),
        "area": last["area"].astype("Int64"),
    })


def build(register: pd.DataFrame, bw: pd.DataFrame) -> pd.DataFrame:
    # Fill a register site's missing area from BarentsWatch, then add BarentsWatch-only sites.
    reg = register.merge(bw[["locality_no", "area"]].rename(columns={"area": "bw_area"}), on="locality_no", how="left")
    reg["area"] = reg["area"].fillna(reg["bw_area"])
    reg = reg.drop(columns="bw_area")
    extra = bw[~bw["locality_no"].isin(reg["locality_no"])].assign(capacity_t=float("nan"))
    print(f"register sites: {len(reg)}, added from BarentsWatch only: {len(extra)}")
    farms = pd.concat([reg, extra], ignore_index=True)

    bad = farms[~farms["area"].between(1, 13).fillna(False)]
    if len(bad):
        print(f"dropping {len(bad)} sites with no area 1-13 (e.g. {bad['name'].head(3).tolist()})")
    farms = farms[farms["area"].between(1, 13).fillna(False)].copy()
    farms["area"] = farms["area"].astype("int64")
    farms["locality_no"] = farms["locality_no"].astype("int64")
    farms["capacity_t"] = farms["capacity_t"].astype("float64")
    return farms[["locality_no", "name", "lat", "lon", "area", "capacity_t"]].sort_values("locality_no").reset_index(drop=True)


def main() -> None:
    offline = "--offline" in sys.argv
    path = latest_raw("register", "*.csv") if offline else download(URL, "register", ".csv")
    farms = build(load_register(path), bw_sites())
    print(f"farms: {len(farms)}, with capacity: {farms['capacity_t'].notna().sum()}, "
          f"per area: {farms['area'].value_counts().sort_index().to_dict()}")
    write_parquet(farms, "farms.parquet")
    if not offline:
        log_download("register", "", "", pd.Timestamp.today().normalize(), path, len(farms))


if __name__ == "__main__":
    main()
