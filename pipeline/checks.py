"""Check every Data table against the contract and the verified examples.

Verified examples (from the dashboard data plan, checked 7 Nov 2026):
- BarentsWatch area 3, 2026-W44: 86 likely stocked sites, 82 with a usable count, 10 above
  the published threshold (12.2%), unweighted mean 0.333 adult females, mean 12.14 °C.
- Directorate area 3, 2026-09: 24,443,037.75 kg across 5,093,481 fish (24,443 t, 4.80 kg).
- Statistics Norway 2026-W44: 28,444 t at 74.98 NOK/kg.

Also: exact contract columns and dtypes, no gaps, value ranges, and a data-quality summary.
Exits with status 1 if anything fails.

Run: python -m pipeline.checks
"""

from __future__ import annotations

import json
import sys

import pandas as pd

from pipeline.common import PROCESSED, SITE_DATA

FAILURES: list[str] = []

SCHEMAS = {
    "directorate_area_month": ["area", "month", "harvest_count", "harvest_kg", "avg_kg", "biomass_kg",
                               "fish_stock", "smolt_released", "dead", "feed_kg", "available_at"],
    "ssb_weekly": ["week", "week_start", "price_nok_kg", "volume_t", "available_at"],
    "fx_daily": ["date", "eurnok", "usdnok", "available_at"],
    "farms": ["locality_no", "name", "lat", "lon", "area", "capacity_t"],
    # lice_limit and above_limit are additions to the contract (dashboard plan).
    "farm_week": ["locality_no", "week", "week_start", "area", "reported", "adult_female", "mobile",
                  "stationary", "treated", "treat_types", "sea_temp_c", "fallow", "isa", "pd",
                  "lice_limit", "above_limit", "available_at"],
}
BOOL_COLUMNS = ["reported", "treated", "fallow", "isa", "pd", "above_limit"]


def check(ok: bool, what: str) -> None:
    print(("  ok    " if ok else "  FAIL  ") + what)
    if not ok:
        FAILURES.append(what)


def close(got: float, want: float, tol: float) -> bool:
    return abs(got - want) <= tol


def load(name: str) -> pd.DataFrame | None:
    path = PROCESSED / f"{name}.parquet"
    if not path.exists():
        check(False, f"{name}.parquet exists")
        return None
    return pd.read_parquet(path)


def schemas(tables: dict) -> None:
    print("contract schemas")
    for name, cols in SCHEMAS.items():
        df = tables.get(name)
        if df is None:
            continue
        check(list(df.columns) == cols, f"{name}: columns {list(df.columns) if list(df.columns) != cols else 'match'}")
        for col in ("date", "week_start", "available_at"):
            if col in df.columns:
                check(str(df[col].dtype) == "datetime64[ns]" and (df[col] == df[col].dt.normalize()).all(),
                      f"{name}.{col} is datetime64[ns] at midnight")
    fw = tables.get("farm_week")
    if fw is not None:
        check(all(str(fw[c].dtype) == "boolean" for c in BOOL_COLUMNS), "farm_week bool columns are nullable boolean")


def directorate(d: pd.DataFrame) -> None:
    print("directorate_area_month")
    r = d[(d["area"] == 3) & (d["month"] == "2026-09")].iloc[0]
    check(close(r.harvest_kg, 24_443_037.75, 0.01) and r.harvest_count == 5_093_481,
          f"area 3 2026-09: {r.harvest_kg / 1000:,.0f} t, {r.harvest_count:,} fish, {r.avg_kg:.2f} kg (24,443 t, 4.80 kg)")
    n = d[d["month"] == "2026-09"][["harvest_kg", "harvest_count"]].sum()
    check(close(n.harvest_count / 1e6, 41.9, 0.1) and close(n.harvest_kg / 1e3, 194_000, 1_000),
          f"national 2026-09: {n.harvest_count / 1e6:.1f} m fish, {n.harvest_kg / 1e3:,.0f} t (41.9 m, ~194,000 t)")
    per_month = d.groupby("month")["area"].nunique()
    check((per_month == 14).all() and d["month"].min() == "2017-10", "areas 0-13 in every month from 2017-10")
    check(d["avg_kg"].isna().eq(d["harvest_count"].eq(0)).all(), "avg_kg is null exactly when there's no harvest")
    num = ["harvest_count", "harvest_kg", "biomass_kg", "fish_stock", "smolt_released", "dead", "feed_kg"]
    check((d[num] >= 0).all().all(), "no negative values")


def ssb(s: pd.DataFrame) -> None:
    print("ssb_weekly")
    r = s[s["week"] == "2026-W44"].iloc[0]
    check(r.volume_t == 28_444 and close(r.price_nok_kg, 74.98, 0.005),
          f"2026-W44: {r.volume_t:,.0f} t at {r.price_nok_kg:.2f} NOK/kg (28,444 t, 74.98)")
    gaps = (s["week_start"].diff().dt.days.dropna() != 7).sum()
    check(s["week"].iloc[0] == "2000-W01" and gaps == 0, f"weekly from 2000-W01 with no gaps ({gaps} gaps)")
    check(s[["price_nok_kg", "volume_t"]].notna().all().all(), "no missing price or volume")


def fx(f: pd.DataFrame) -> None:
    print("fx_daily")
    check(f[["eurnok", "usdnok"]].notna().all().all(), "no missing rates")
    check(f[["eurnok", "usdnok"]].stack().between(5, 14).all(), "every rate between 5 and 14")
    check((f["date"].dt.day_of_week < 5).all(), "business days only")


def farm_week(fw: pd.DataFrame, farms: pd.DataFrame) -> None:
    print("farm_week")
    check(fw["area"].between(1, 13).all(), "every row has an area 1-13")
    check(not fw.duplicated(["locality_no", "week"]).any(), "one row per site-week")
    check(fw["locality_no"].isin(farms["locality_no"]).all(), "every site is in farms.parquet")
    farm_area = farms.set_index("locality_no")["area"]
    mismatched = (fw["area"] != fw["locality_no"].map(farm_area)).sum()
    check(mismatched == 0, f"every farm_week area equals the site's farms.parquet area ({mismatched} differ)")
    early = fw["week"] < "2014-W01"
    check(fw.loc[early, ["isa", "pd"]].isna().all().all() and fw.loc[~early, ["isa", "pd"]].notna().all().all(),
          "isa/pd null before 2014-W01 and known from then on")
    unreported = fw["reported"] != True  # noqa: E712
    check(fw.loc[unreported, ["adult_female", "mobile", "stationary"]].isna().all().all(),
          "unreported weeks keep lice missing, never zero")
    t = fw["sea_temp_c"].dropna()
    check(t.between(-2, 25).all(), "cleaned sea temperature within -2..25 °C")

    # The dashboard plan's area 3 example.
    a = fw[(fw["area"] == 3) & (fw["week"] == "2026-W44")]
    stocked = a[a["fallow"] == False]  # noqa: E712
    counted = a[(a["reported"] == True) & a["adult_female"].notna()]  # noqa: E712
    above = counted[counted["above_limit"] == True]  # noqa: E712
    share = 100 * len(above) / len(counted)
    check(len(stocked) == 86 and len(counted) == 82 and len(above) == 10 and close(share, 12.2, 0.05),
          f"area 3 2026-W44: {len(counted)} of {len(stocked)} counted, {len(above)} above ({share:.1f}%) (82 of 86, 10, 12.2%)")
    mean_af = counted["adult_female"].mean()
    check(close(mean_af, 0.333, 0.0005), f"area 3 2026-W44 mean adult females {mean_af:.3f} (0.333)")
    # The plan's 12.14 °C is the raw reported mean; the cleaned value can differ only if an outlier was removed.
    mean_t = counted["sea_temp_c"].mean()
    check(close(mean_t, 12.14, 0.005), f"area 3 2026-W44 mean sea temperature {mean_t:.2f} °C (12.14)")


def site_json(farms: pd.DataFrame) -> None:
    print("site JSON")
    path = SITE_DATA / "farms.json"
    if not path.exists():
        check(False, "farms.json exists")
        return
    ids = {f["id"] for f in json.loads(path.read_text())}
    check(ids == set(farms["locality_no"]), "farms.json matches farms.parquet")
    years = json.loads((SITE_DATA / "farm_weeks" / "index.json").read_text())["years"]
    for y in years:
        p = SITE_DATA / "farm_weeks" / f"{y}.json"
        j = json.loads(p.read_text())
        shapes_ok = all(len(j[k]) == len(j["weeks"]) and all(len(row) == len(j["ids"]) for row in j[k])
                        for k in ("mobile", "treated", "temp") + (("disease",) if "disease" in j else ()))
        check(set(j["ids"]) <= ids and shapes_ok and p.stat().st_size < 3e6,
              f"{y}.json: {len(j['weeks'])} weeks × {len(j['ids'])} sites, {p.stat().st_size / 1e6:.2f} MB")


def quality(fw: pd.DataFrame, d: pd.DataFrame) -> None:
    print("\ndata-quality summary (informational)")
    y = fw["week"].str[:4]
    rep = fw["reported"] == True  # noqa: E712
    out = pd.DataFrame({
        "reporting_%": 100 * rep.groupby(y).mean(),
        "temp_%": 100 * fw["sea_temp_c"].notna()[rep].groupby(y[rep]).mean(),
        "above_limit_%": 100 * (fw["above_limit"] == True)[rep].groupby(y[rep]).mean(),  # noqa: E712
        "treated_sites_per_week": (fw["treated"] == True).groupby(fw["week"]).sum().groupby(lambda w: w[:4]).mean(),  # noqa: E712
    }).round(1)
    print(out.to_string())
    # Same season a year apart, so the comparison isn't just winter against autumn.
    before = fw[(fw["week"] >= "2023-W46") & (fw["week"] < "2024-W10")]
    after = fw[(fw["week"] >= "2024-W46") & (fw["week"] < "2025-W10")]
    tb = (before["treated"] == True).groupby(before["week"]).sum().mean()  # noqa: E712
    ta = (after["treated"] == True).groupby(after["week"]).sum().mean()  # noqa: E712
    print(f"treated sites per week, W46-W09 before vs after the 2024-W46 format change: {tb:.0f} vs {ta:.0f}")
    never_temp = fw[rep].groupby("locality_no")["sea_temp_c"].apply(lambda s: s.isna().all()).sum()
    print(f"reporting sites that never have a temperature: {never_temp}")
    zero = d[(d["area"] > 0) & d["avg_kg"].isna()]
    print(f"Directorate area-months (1-13) with zero harvest: {len(zero)}")


def main() -> None:
    tables = {name: load(name) for name in SCHEMAS}
    schemas(tables)
    if tables["directorate_area_month"] is not None:
        directorate(tables["directorate_area_month"])
    if tables["ssb_weekly"] is not None:
        ssb(tables["ssb_weekly"])
    if tables["fx_daily"] is not None:
        fx(tables["fx_daily"])
    if tables["farm_week"] is not None and tables["farms"] is not None:
        farm_week(tables["farm_week"], tables["farms"])
        site_json(tables["farms"])
        quality(tables["farm_week"], tables["directorate_area_month"])
    print(f"\n{len(FAILURES)} failed" + (":\n  " + "\n  ".join(FAILURES) if FAILURES else ", all checks passed"))
    sys.exit(1 if FAILURES else 0)


if __name__ == "__main__":
    main()
