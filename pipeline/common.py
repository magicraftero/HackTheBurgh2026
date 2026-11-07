"""Shared helpers for every fetcher: paths, ISO weeks, publication dates and writers.

Publication rules (docs/plans/00-shared.md, "Publication dates"):
  BarentsWatch week w   -> the Sunday ending week w + 1
  Statistics Norway w   -> the Wednesday of week w + 1
  Directorate month m   -> the 20th of month m + 1
  Exchange rates day d  -> d + 1
"""

from __future__ import annotations

import json
import math
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
SITE_DATA = ROOT / "web" / "public" / "data"

DATE_COLUMNS = ("date", "week_start", "available_at", "available_at_dir", "available_at_bw")


# ---- ISO weeks and months -------------------------------------------------

def iso_week_str(year: int, week: int) -> str:
    return f"{int(year)}-W{int(week):02d}"


def parse_week(week: str) -> tuple[int, int]:
    y, w = week.split("-W")
    return int(y), int(w)


def week_start(week: str) -> date:
    """Monday of an ISO week written YYYY-Www."""
    return date.fromisocalendar(*parse_week(week), 1)


def week_to_month(week: str) -> str:
    """A week belongs to the month that contains its Thursday."""
    thu = date.fromisocalendar(*parse_week(week), 4)
    return f"{thu.year}-{thu.month:02d}"


def month_str(year: int, month: int) -> str:
    return f"{int(year)}-{int(month):02d}"


def next_month(year: int, month: int) -> tuple[int, int]:
    return (year + 1, 1) if month == 12 else (year, month + 1)


# ---- Publication dates ----------------------------------------------------

def available_at_bw(week: str) -> date:
    return week_start(week) + timedelta(days=13)


def available_at_ssb(week: str) -> date:
    return week_start(week) + timedelta(days=9)


def available_at_dir(month: str) -> date:
    y, m = next_month(*map(int, month.split("-")))
    return date(y, m, 20)


def available_at_fx(d: date) -> date:
    return d + timedelta(days=1)


# ---- Writers --------------------------------------------------------------

def write_parquet(df: pd.DataFrame, name: str) -> Path:
    """Write data/processed/<name>, with date columns as datetime64[ns] at midnight."""
    df = df.copy()
    for col in DATE_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col]).dt.normalize().astype("datetime64[ns]")
    PROCESSED.mkdir(parents=True, exist_ok=True)
    path = PROCESSED / name
    df.to_parquet(path, index=False)
    print(f"wrote {path.relative_to(ROOT)}: {len(df):,} rows")
    return path


def _clean(obj):
    if isinstance(obj, dict):
        return {k: _clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_clean(v) for v in obj]
    if isinstance(obj, np.generic):
        obj = obj.item()
    if isinstance(obj, float) and not math.isfinite(obj):
        return None
    if obj is pd.NA or obj is pd.NaT:
        return None
    return obj


def write_json(obj, path: Path) -> Path:
    """UTF-8 JSON with NaN written as null (allow_nan=False catches any left over)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(_clean(obj), f, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    print(f"wrote {path.relative_to(ROOT)}: {path.stat().st_size / 1e6:.2f} MB")
    return path
