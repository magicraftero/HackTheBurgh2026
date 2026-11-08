"""File output helpers shared by Production scripts.

Writes are atomic (temporary file, then replace) because the front end and
the chart scripts read these files while they are being regenerated.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


def write_parquet_atomic(frame: pd.DataFrame, destination: Path) -> None:
    frame = frame.copy()
    frame.attrs = {}
    for column in frame:
        if pd.api.types.is_datetime64_any_dtype(frame[column]):
            frame[column] = pd.to_datetime(frame[column]).astype("datetime64[ns]")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".tmp.parquet")
    frame.to_parquet(temporary, index=False)
    temporary.replace(destination)


def write_json_atomic(payload: Any, destination: Path) -> None:
    """Write site JSON as UTF-8, failing loudly if any NaN slipped through."""

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".tmp.json")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, allow_nan=False)
    temporary.replace(destination)


def round_significant(value: Any, digits: int = 4) -> int | float | None:
    """Round a measured value to significant figures; missing becomes None."""

    number = _as_float(value)
    if number is None:
        return None
    if number == 0:
        return 0
    magnitude = math.floor(math.log10(abs(number)))
    rounded = round(number, digits - 1 - magnitude)
    return int(rounded) if float(rounded).is_integer() else float(rounded)


def round_decimals(value: Any, decimals: int = 2) -> float | None:
    """Round lice and temperature values to fixed decimals."""

    number = _as_float(value)
    return None if number is None else round(number, decimals)


def as_int(value: Any) -> int | None:
    number = _as_float(value)
    return None if number is None else int(number)


def _as_float(value: Any) -> float | None:
    if value is None or value is pd.NA or value is pd.NaT:
        return None
    number = float(value)
    if not np.isfinite(number):
        return None
    return number
