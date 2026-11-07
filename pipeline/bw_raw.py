"""Read the BarentsWatch bulk exports saved by pipeline.fetch_barentswatch.

For each report and year the newest file on disk wins (a finished year has one file; the
current year has timestamped snapshots).
"""

from __future__ import annotations

import re

import pandas as pd

from pipeline.common import RAW

OUT = RAW / "barentswatch"


def files(report: str) -> list:
    newest = {}
    for f in sorted((OUT / report).glob(f"{report}_*.csv")):
        m = re.match(rf"{report}_(\d{{4}})", f.name)
        if m:
            newest[int(m.group(1))] = f  # sorted, so later snapshots overwrite earlier ones
    return [newest[y] for y in sorted(newest)]


def load(report: str) -> pd.DataFrame:
    paths = files(report)
    if not paths:
        raise SystemExit(f"no BarentsWatch {report} files in {OUT / report}; run python -m pipeline.fetch_barentswatch")
    df = pd.concat([pd.read_csv(p, encoding="utf-8-sig", dtype={"Lokalitetsnummer": "int64"}, low_memory=False)
                    for p in paths],
                   ignore_index=True)
    print(f"read {report}: {len(paths)} files, {len(df):,} rows, years {files_years(paths)}")
    return df


def files_years(paths) -> str:
    years = [int(re.search(r"_(\d{4})", p.name).group(1)) for p in paths]
    return f"{min(years)}-{max(years)}"
