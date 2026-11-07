"""farms.parquet + farm_week.parquet -> the map data for the site (web/public/data/)

- farms.json: [{id, name, lat, lon, area, capacity_t}]
- farm_weeks/index.json: {"years": [...]}
- farm_weeks/{year}.json, 2019-2026: {year, weeks, ids, mobile, treated, temp[, disease]}
  where mobile[i][j] is week weeks[i] at site ids[j] and null means no report.

Only weeks whose reporting deadline (the Tuesday after) has passed are exported, so the map
never shows a half-reported week. ids are the sites that reported at least once that year.
treated is null in weeks without a lice report. disease (1 = ISA or PD, 0 = neither) is written only when the flags exist.
Lice and temperature are rounded to 2 decimals, capacity to 4 significant figures, and
coordinates to 4 decimals (about 10 m). IDs, areas and years are never rounded.

Run: python -m pipeline.export_site_data
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from pipeline.common import PROCESSED, SITE_DATA, write_json

YEARS = range(2019, 2027)


def sig4(x):
    return None if x is None or math.isnan(x) else float(f"{x:.4g}")


def grid(sub: pd.DataFrame, col: str, weeks, ids, decimals=None) -> list:
    m = sub.pivot(index="week", columns="locality_no", values=col).reindex(index=weeks, columns=ids)
    vals = m.to_numpy(dtype=float, na_value=np.nan)
    if decimals is not None:
        vals = np.round(vals, decimals)
    return [[None if np.isnan(v) else (int(v) if decimals is None else float(v)) for v in row] for row in vals]


def main() -> None:
    farms = pd.read_parquet(PROCESSED / "farms.parquet")
    fw = pd.read_parquet(PROCESSED / "farm_week.parquet")

    write_json([{"id": int(r.locality_no), "name": r.name, "lat": round(r.lat, 4), "lon": round(r.lon, 4),
                 "area": int(r.area), "capacity_t": sig4(r.capacity_t)} for r in farms.itertuples()],
               SITE_DATA / "farms.json")

    has_disease = fw["isa"].notna().any()
    rep = fw["reported"].fillna(False).astype(bool)
    fw["treated_num"] = fw["treated"].astype("Float64").where(rep)
    fw["disease_num"] = (fw["isa"].fillna(False) | fw["pd"].fillna(False)).astype("Float64").where(fw["isa"].notna())

    known = set(farms["locality_no"])
    # Farms report by the Tuesday after the week; show a week once that deadline has passed.
    # (The tables keep the contract's stricter available_at for modelling.)
    published = fw["week_start"] + pd.Timedelta(days=8) <= pd.Timestamp.today().normalize()
    years = []
    for year in YEARS:
        sub = fw[fw["week"].str.startswith(f"{year}-") & published]
        if sub.empty:
            continue
        weeks = sorted(sub["week"].unique())
        ids = sorted(sub.loc[rep[sub.index], "locality_no"].unique().tolist())
        missing = set(ids) - known
        if missing:
            raise SystemExit(f"{year}: {len(missing)} ids not in farms.json, e.g. {sorted(missing)[:5]}")
        out = {"year": year, "weeks": weeks, "ids": [int(i) for i in ids],
               "mobile": grid(sub, "mobile", weeks, ids, 2),
               "treated": grid(sub, "treated_num", weeks, ids),
               "temp": grid(sub, "sea_temp_c", weeks, ids, 2)}
        if has_disease:
            out["disease"] = grid(sub, "disease_num", weeks, ids)
        path = write_json(out, SITE_DATA / "farm_weeks" / f"{year}.json")
        if path.stat().st_size > 3e6:
            print(f"WARNING: {path.name} is over 3 MB")
        years.append(year)
    write_json({"years": years}, SITE_DATA / "farm_weeks" / "index.json")


if __name__ == "__main__":
    main()
