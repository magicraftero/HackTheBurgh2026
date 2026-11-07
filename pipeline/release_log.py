"""The release clock: every download is saved under a timestamped name and logged.

Raw files are never overwritten, so a later revision of the same period sits beside
the earlier one. data/processed/release_log.parquet records, for each download, the
periods it covers, the rule-based publication date of its newest period, when we
downloaded it and a hash of the bytes.

Historic rows are revised data scored against assumed release dates, so any
backtest built from them is a reconstruction, not a record of real-time data.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

from pipeline.common import PROCESSED, RAW, ROOT

LOG = PROCESSED / "release_log.parquet"


def stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def download(url: str, source: str, suffix: str, **kwargs) -> Path:
    """GET url and save it as data/raw/<source>/<source>_<UTC stamp><suffix>."""
    resp = requests.get(url, timeout=120, **kwargs)
    resp.raise_for_status()
    out = RAW / source / f"{source}_{stamp()}{suffix}"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(resp.content)
    print(f"downloaded {url}\n  -> {out.relative_to(ROOT)} ({len(resp.content) / 1e6:.2f} MB)")
    return out


def latest_raw(source: str, pattern: str = "*") -> Path | None:
    files = sorted((RAW / source).glob(pattern))
    return files[-1] if files else None


def log_download(source: str, period_from: str, period_to: str, available_at, path: Path, rows: int) -> None:
    row = pd.DataFrame([{
        "source": source,
        "period_from": period_from,
        "period_to": period_to,
        "available_at": pd.Timestamp(available_at),
        "downloaded_at": pd.Timestamp.now(tz="UTC").tz_localize(None),
        "file": str(path.relative_to(ROOT)),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "rows": int(rows),
    }])
    log = pd.concat([pd.read_parquet(LOG), row], ignore_index=True) if LOG.exists() else row
    # Same dtype as the contract tables: available_at at midnight, downloaded_at keeps its time.
    log["available_at"] = pd.to_datetime(log["available_at"]).dt.normalize().astype("datetime64[ns]")
    log["downloaded_at"] = pd.to_datetime(log["downloaded_at"]).astype("datetime64[ns]")
    log.to_parquet(LOG, index=False)
