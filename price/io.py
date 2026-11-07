"""Strict site JSON and atomic output replacement."""

import json
import math
import os
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd


def site_value(value):
    if isinstance(value, dict):
        return {str(k): site_value(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [site_value(v) for v in value]
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (int, np.integer)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        return float(f"{value:.4g}") if math.isfinite(value) else None
    if value is pd.NA or value is pd.NaT:
        return None
    return value


def atomic_write(path, writer):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, name = tempfile.mkstemp(dir=path.parent, suffix=path.suffix)
    os.close(handle)
    try:
        writer(Path(name))
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def write_json(path, value):
    text = json.dumps(site_value(value), ensure_ascii=False, allow_nan=False, indent=2) + "\n"
    atomic_write(path, lambda tmp: tmp.write_text(text, encoding="utf-8"))
