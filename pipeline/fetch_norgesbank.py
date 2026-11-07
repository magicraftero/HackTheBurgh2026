"""Norges Bank daily EUR/NOK and USD/NOK -> data/processed/fx_daily.parquet

Business days only, as Norges Bank publishes them; weekends and holidays stay absent.

Run: python -m pipeline.fetch_norgesbank [--offline]
"""

from __future__ import annotations

import sys

import pandas as pd

from pipeline.common import available_at_fx, write_parquet
from pipeline.release_log import download, latest_raw, log_download

START = "2011-12-01"
SERIES = {"eurnok": "B.EUR.NOK.SP", "usdnok": "B.USD.NOK.SP"}


def url(series: str) -> str:
    return f"https://data.norges-bank.no/api/data/EXR/{series}?format=csv&startPeriod={START}&locale=en"


def load_one(path, name: str) -> pd.DataFrame:
    raw = pd.read_csv(path, sep=";", decimal=".", usecols=["TIME_PERIOD", "OBS_VALUE"])
    return pd.DataFrame({"date": pd.to_datetime(raw["TIME_PERIOD"]),
                         name: pd.to_numeric(raw["OBS_VALUE"], errors="coerce")})


def main() -> None:
    offline = "--offline" in sys.argv
    parts, paths = [], {}
    for name, series in SERIES.items():
        path = latest_raw(f"norgesbank_{name}", "*.csv") if offline else download(url(series), f"norgesbank_{name}", ".csv")
        paths[name] = path
        parts.append(load_one(path, name).set_index("date"))

    df = parts[0].join(parts[1], how="outer").reset_index().sort_values("date")
    df["available_at"] = [available_at_fx(d) for d in df["date"]]
    df = df[["date", "eurnok", "usdnok", "available_at"]]

    ok = True
    for name, part in zip(SERIES, parts):
        # errors="coerce" turns unparseable values into NaN, so count them before anything drops them.
        unparsed = int(part[name].isna().sum())
        if part.empty or unparsed:
            print(f"WARNING: {name} has {len(part)} rows, {unparsed} empty or unparseable values")
            ok = False
        if part[name].notna().any():
            s = df[["date", name]].dropna()
            print(f"{name}: {s['date'].min().date()} .. {s['date'].max().date()} ({len(s)} days), "
                  f"range {s[name].min():.4f}-{s[name].max():.4f}")
            if not s[name].between(5, 14).all():
                print(f"WARNING: {name} has values outside 5-14")
                ok = False
    unmatched = int(df[list(SERIES)].isna().any(axis=1).sum())
    if unmatched:
        print(f"WARNING: {unmatched} days have one rate but not the other")
        ok = False
    print(df.tail(3).to_string(index=False))

    write_parquet(df, "fx_daily.parquet")
    if not offline:
        last = df["date"].max()
        for name, path in paths.items():
            log_download(f"norgesbank_{name}", START, str(last.date()), available_at_fx(last), path, len(df))
    if not ok:
        print("CHECKS FAILED: tell your human.")


if __name__ == "__main__":
    main()
