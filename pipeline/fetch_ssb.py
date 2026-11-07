"""Statistics Norway table 03024 -> data/processed/ssb_weekly.parquet

Weekly export of fresh or chilled farmed salmon (VareGrupper2 = 01): tonnes (Vekt)
and NOK/kg (Kilopris), every week since 2000-W01. One request covers it all.

Run: python -m pipeline.fetch_ssb [--offline]
"""

from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd

from pipeline.common import available_at_ssb, iso_week_str, week_start, write_parquet
from pipeline.release_log import download, latest_raw, log_download

URL = ("https://data.ssb.no/api/pxwebapi/v2/tables/03024/data?lang=en"
       "&valueCodes[VareGrupper2]=01&valueCodes[ContentsCode]=Vekt,Kilopris"
       "&valueCodes[Tid]=*&outputFormat=json-stat2")


def load(path) -> pd.DataFrame:
    j = json.loads(path.read_text(encoding="utf-8"))
    dims = j["id"]
    if dims != ["VareGrupper2", "ContentsCode", "Tid"]:
        raise SystemExit(f"unexpected dimension order {dims}")
    contents = j["dimension"]["ContentsCode"]["category"]["index"]
    tids = sorted(j["dimension"]["Tid"]["category"]["index"].items(), key=lambda kv: kv[1])
    values = np.array([np.nan if v is None else v for v in j["value"]], dtype=float)
    values = values.reshape(j["size"])[0]  # -> (contents, time)

    weeks = [iso_week_str(*map(int, code.split("U"))) for code, _ in tids]
    df = pd.DataFrame({
        "week": weeks,
        "price_nok_kg": values[contents["Kilopris"]],
        "volume_t": values[contents["Vekt"]],
    })
    df["week_start"] = [week_start(w) for w in df["week"]]
    df["available_at"] = [available_at_ssb(w) for w in df["week"]]
    return df[["week", "week_start", "price_nok_kg", "volume_t", "available_at"]]


def check(df: pd.DataFrame) -> bool:
    ok = True
    print(f"weeks {df['week'].iloc[0]} .. {df['week'].iloc[-1]} ({len(df)})")
    gaps = (pd.to_datetime(df["week_start"]).diff().dt.days.dropna() != 7).sum()
    if gaps:
        print(f"WARNING: {gaps} gaps in the weekly sequence")
        ok = False
    w53 = sorted(w[:4] for w in df["week"] if w.endswith("W53"))
    print(f"years with week 53: {w53}")
    missing = df[["price_nok_kg", "volume_t"]].isna().sum()
    if missing.any():
        print(f"WARNING: missing values {missing.to_dict()}")
        ok = False
    print(df.tail(3).to_string(index=False))
    return ok


def main() -> None:
    offline = "--offline" in sys.argv
    path = latest_raw("ssb", "*.json") if offline else download(URL, "ssb", ".json")
    df = load(path)
    ok = check(df)
    write_parquet(df, "ssb_weekly.parquet")
    if not offline:
        log_download("ssb", df["week"].iloc[0], df["week"].iloc[-1], available_at_ssb(df["week"].iloc[-1]), path, len(df))
    if not ok:
        print("CHECKS FAILED: tell your human.")


if __name__ == "__main__":
    main()
