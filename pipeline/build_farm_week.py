"""BarentsWatch lice, treatments and disease -> data/processed/farm_week.parquet

One row per salmonid site × ISO week, as the lice export lists them (every site BarentsWatch
considers active that week, reporting or not).

- reported: the site counted lice that week ("Har telt lakselus"). Unreported weeks keep
  their lice values missing, never zero.
- fallow: BarentsWatch's estimate that the site is likely without fish ("Trolig uten fisk").
- treated: any delousing treatment (medicinal or not) reported that week; a farm-week counts
  once. Before 2024-W46 most non-medicinal treatments have no type, so treat_types falls back
  to the measure ("ikke-medikamentell"). Treating sites per week is stable across the change.
- sea_temp_c: null below -2 °C, above 25 °C, or more than 6 °C from the site's trailing
  8-week median (trailing, so no later data is used).
- isa, pd: the site has a suspected or confirmed ISA (ILA) / PD case that week. Null before the
  first disease record. Records are sparse before 2014 (a few cases a week in 2012).
- lice_limit, above_limit: the week's published adult-female threshold and BarentsWatch's flag
  for being above it (an addition to the contract, from the dashboard plan).
- available_at: the Sunday ending week w + 1.

Run: python -m pipeline.build_farm_week
"""

from __future__ import annotations

import pandas as pd

from pipeline import bw_raw
from pipeline.common import PROCESSED, available_at_bw, iso_week_str, week_start, write_parquet

YES_NO = {"Ja": True, "Nei": False}
COLUMNS = ["locality_no", "week", "week_start", "area", "reported", "adult_female", "mobile",
           "stationary", "treated", "treat_types", "sea_temp_c", "fallow", "isa", "pd",
           "lice_limit", "above_limit", "available_at"]


def yes_no(s: pd.Series) -> pd.Series:
    return s.map(YES_NO).astype("boolean")


def lice_rows() -> pd.DataFrame:
    raw = bw_raw.load("lice")
    df = pd.DataFrame({
        "locality_no": raw["Lokalitetsnummer"].astype("int64"),
        "year": raw["År"].astype(int),
        "wk": raw["Uke"].astype(int),
        "area": pd.to_numeric(raw["ProduksjonsområdeId"], errors="coerce").astype("Int64"),
        "reported": yes_no(raw["Har telt lakselus"]),
        "adult_female": pd.to_numeric(raw["Voksne hunnlus"], errors="coerce"),
        "mobile": pd.to_numeric(raw["Lus i bevegelige stadier"], errors="coerce"),
        "stationary": pd.to_numeric(raw["Fastsittende lus"], errors="coerce"),
        "temp_raw": pd.to_numeric(raw["Sjøtemperatur"], errors="coerce"),
        "fallow": yes_no(raw["Trolig uten fisk"]),
        "lice_limit": pd.to_numeric(raw["Lusegrense uke"], errors="coerce"),
        "above_limit": yes_no(raw["Over lusegrense uke"]),
    })
    df["week"] = [iso_week_str(y, w) for y, w in zip(df["year"], df["wk"])]
    dupes = df.duplicated(["locality_no", "week"]).sum()
    if dupes:
        print(f"note: dropping {dupes} duplicate site-weeks (kept the first)")
        df = df.drop_duplicates(["locality_no", "week"])
    # Lice counts only mean something when the site counted that week.
    lice = ["adult_female", "mobile", "stationary"]
    df.loc[df["reported"] != True, lice] = float("nan")  # noqa: E712 (nullable boolean)
    return df


def treatment_weeks() -> pd.DataFrame:
    t = bw_raw.load("treatments")
    t = t[t["Tiltak"].isin(["medikamentell", "ikke-medikamentell"])].copy()
    t["week"] = [iso_week_str(y, w) for y, w in zip(t["År"], t["Uke"])]
    t["kind"] = t["Type behandling"].fillna(t["Tiltak"])
    return (t.groupby(["Lokalitetsnummer", "week"])["kind"]
             .agg(lambda k: ",".join(sorted(set(k))))
             .rename("treat_types").reset_index()
             .rename(columns={"Lokalitetsnummer": "locality_no"}))


def disease_weeks() -> tuple[pd.DataFrame, str]:
    d = bw_raw.load("disease")
    d = d[d["Status"].isin(["Mistanke", "Påvist"])].copy()  # suspected and confirmed both count
    d["week"] = [iso_week_str(y, w) for y, w in zip(d["År"], d["Uke"])]
    flags = (d.assign(isa=d["Sykdom"].eq("ILA"), pd=d["Sykdom"].eq("PD"))
              .groupby(["Lokalitetsnummer", "week"])[["isa", "pd"]].any().reset_index()
              .rename(columns={"Lokalitetsnummer": "locality_no"}))
    # Weeks before the first disease record are unknown, not disease-free.
    return flags, d["week"].min()


def clean_temperature(df: pd.DataFrame) -> pd.Series:
    t = df["temp_raw"].where(df["temp_raw"].between(-2, 25))
    s = df.assign(t=t).sort_values(["locality_no", "week_start"])
    med = s.groupby("locality_no").rolling("56D", on="week_start", min_periods=3)["t"].median()
    # The result comes back in the same order as s (groups sorted by locality, then by week).
    med = pd.Series(med.to_numpy(), index=s.index).reindex(df.index)
    return t.where(med.isna() | ((t - med).abs() <= 6))


def build() -> pd.DataFrame:
    df = lice_rows()
    df["week_start"] = pd.to_datetime([week_start(w) for w in df["week"]])

    # Area: from the lice report, else from farms.parquet; rows still without 1-13 are dropped.
    farms_path = PROCESSED / "farms.parquet"
    if farms_path.exists():
        farm_area = pd.read_parquet(farms_path).set_index("locality_no")["area"]
        df["area"] = df["area"].fillna(df["locality_no"].map(farm_area).astype("Int64"))
    bad = ~df["area"].between(1, 13).fillna(False)
    if bad.any():
        print(f"dropping {bad.sum()} site-weeks with no area 1-13")
    df = df[~bad].copy()
    df["area"] = df["area"].astype("int64")

    df = df.merge(treatment_weeks(), on=["locality_no", "week"], how="left")
    df["treated"] = df["treat_types"].notna().astype("boolean")

    flags, first_disease_week = disease_weeks()
    df = df.merge(flags, on=["locality_no", "week"], how="left")
    covered = df["week"] >= first_disease_week
    print(f"disease data from {first_disease_week}")
    for col in ("isa", "pd"):
        df[col] = df[col].astype("boolean").fillna(False).where(covered, pd.NA).astype("boolean")

    df["sea_temp_c"] = clean_temperature(df)
    df["available_at"] = [available_at_bw(w) for w in df["week"]]
    return df[COLUMNS].sort_values(["week", "locality_no"]).reset_index(drop=True)


def summary(df: pd.DataFrame) -> None:
    y = df["week"].str[:4]
    g = df.groupby(y)
    rep = df["reported"] == True  # noqa: E712
    out = pd.DataFrame({
        "rows": g.size(),
        "sites": g["locality_no"].nunique(),
        "reporting_%": (100 * rep.groupby(y).mean()).round(1),
        "temp_%_of_reporting": (100 * df["sea_temp_c"].notna()[rep].groupby(y[rep]).mean()).round(1),
        "treated_%_of_reporting": (100 * (df["treated"] == True)[rep].groupby(y[rep]).mean()).round(1),  # noqa: E712
        "above_limit_%_of_reporting": (100 * (df["above_limit"] == True)[rep].groupby(y[rep]).mean()).round(1),  # noqa: E712
        "isa_or_pd_%": (100 * ((df["isa"] == True) | (df["pd"] == True)).groupby(y).mean()).round(2),  # noqa: E712
    })
    print(out.to_string())
    print(f"weeks {df['week'].min()} .. {df['week'].max()}, areas {sorted(df['area'].unique())}")
    print(f"lice limit values: {df['lice_limit'].value_counts().sort_index().to_dict()}")


def main() -> None:
    df = build()
    summary(df)
    write_parquet(df, "farm_week.parquet")


if __name__ == "__main__":
    main()
