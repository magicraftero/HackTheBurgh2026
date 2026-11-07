"""Calendar terms fixed before evaluation; no observed future inputs."""

from datetime import date, timedelta
from functools import lru_cache

import numpy as np
import pandas as pd
from dateutil.easter import easter


def week_start(week: str) -> pd.Timestamp:
    year, number = week.split("-W")
    result = pd.Timestamp(date.fromisocalendar(int(year), int(number), 1))
    if iso_week(result) != week:
        raise ValueError(f"Invalid ISO week: {week}")
    return result


def iso_week(value) -> str:
    year, week, _ = pd.Timestamp(value).isocalendar()
    return f"{year}-W{week:02d}"


@lru_cache(maxsize=64)
def holidays(year: int):
    sunday = easter(year)
    return sunday - timedelta(days=2), sunday + timedelta(days=1)


@lru_cache(maxsize=8192)
def weekly_holidays(start):
    end = start + timedelta(days=6)
    easter_week = float(any(start <= d <= end for d in holidays(start.year)))
    christmas = float(any(start <= date(y + 1, 1, 1) and end >= date(y, 12, 24)
                          for y in range(start.year - 1, start.year + 1)))
    return easter_week, christmas


def seasonality(index: pd.DatetimeIndex, freq="W", K=3) -> pd.DataFrame:
    anchor = index + pd.Timedelta(days=3) if freq == "W" else index + pd.Timedelta(days=14)
    result = pd.DataFrame({"const": np.ones(len(index))}, index=index)
    for k in range(1, K + 1):
        angle = 2 * np.pi * k * anchor.dayofyear / 365.25
        result[f"sin{k}"] = np.sin(angle)
        result[f"cos{k}"] = np.cos(angle)
    if freq == "W":
        flags = [weekly_holidays(d.date()) for d in index]
        result["easter"] = [f[0] for f in flags]
        result["christmas"] = [f[1] for f in flags]
    else:
        result["easter"] = [float(d.month == easter(d.year).month) for d in index]
    return result
