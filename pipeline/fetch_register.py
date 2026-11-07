"""Directorate aquaculture register + BarentsWatch sites -> data/processed/farms.parquet

The register has one row per licence × site × species. We keep marine (SJØ, HAV) sites
licensed for salmon or trout and deduplicate to one row per site (locality number).
Capacity is the site's licensed capacity when given in tonnes, otherwise null.

Sites that appear in BarentsWatch but not in today's register (mostly closed sites) are
added from BarentsWatch: coordinates and area from its latest report that has them, capacity
null. A site with coordinates but no area takes the area of its nearest site. Sites with
neither (old sites from before production areas existed) are dropped and counted.

Run: python -m pipeline.fetch_register [--offline]   (needs the BarentsWatch lice files)
"""

from __future__ import annotations

import sys

import numpy as np
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
    g = lice.groupby("Lokalitetsnummer")
    last = g[["Lokalitetsnavn", "Lat", "Lon", "area"]].last().reset_index()
    last["n_reports"] = g["Har telt lakselus"].apply(lambda s: (s == "Ja").sum()).to_numpy()
    return pd.DataFrame({
        "locality_no": last["Lokalitetsnummer"].astype(int),
        "name": last["Lokalitetsnavn"],
        "lat": last["Lat"].astype(float),
        "lon": last["Lon"].astype(float),
        "area": last["area"].astype("Int64"),
        "n_reports": last["n_reports"],  # only for the "dropping" message
    })


def nearest_area(farms: pd.DataFrame) -> pd.Series:
    """Give a site without an area 1-13 the area of the nearest site that has one (Data plan, task 5)."""
    area = farms["area"].copy()
    known = farms[area.between(1, 13).fillna(False) & farms[["lat", "lon"]].notna().all(axis=1)]
    todo = farms[~area.between(1, 13).fillna(False) & farms[["lat", "lon"]].notna().all(axis=1)]
    if todo.empty:
        return area
    # Equirectangular distance is plenty for picking the nearest site along one coast.
    kx = np.cos(np.radians(known["lat"].to_numpy()))
    for i, row in todo.iterrows():
        d2 = (known["lat"].to_numpy() - row.lat) ** 2 + ((known["lon"].to_numpy() - row.lon) * kx) ** 2
        area.loc[i] = known["area"].iloc[int(np.argmin(d2))]
    print(f"gave {len(todo)} sites the area of their nearest site")
    return area


def build(register: pd.DataFrame, bw: pd.DataFrame) -> pd.DataFrame:
    # Fill a register site's missing area from BarentsWatch, then add BarentsWatch-only sites.
    reg = register.merge(bw[["locality_no", "area"]].rename(columns={"area": "bw_area"}), on="locality_no", how="left")
    reg["area"] = reg["area"].fillna(reg["bw_area"])
    reg = reg.drop(columns="bw_area")
    extra = bw[~bw["locality_no"].isin(reg["locality_no"])].assign(capacity_t=float("nan"))
    print(f"register sites: {len(reg)}, added from BarentsWatch only: {len(extra)}")
    farms = pd.concat([reg, extra], ignore_index=True)
    farms["area"] = nearest_area(farms)

    bad = farms[~farms["area"].between(1, 13).fillna(False)]
    if len(bad):
        lost = int(bad["n_reports"].fillna(0).sum())
        print(f"dropping {len(bad)} sites with no area and no coordinates ({lost} lice reports in total)")
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
