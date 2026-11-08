"""Combined production forecast: the better of v2 and the ML challenger for each outcome.

Choices made on the development window (2021-2024) only:
kg from v2 (``analysis.topdown``), average weight from the ML challenger, and fish count as
kg / average weight, so the three always agree. Run from the repository root with
``python -m analysis.combined`` after ``python -m analysis.topdown``.
"""

from __future__ import annotations

import argparse
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Final

import numpy as np
import pandas as pd

from analysis.config import DEVELOPMENT_WINDOW, HOLDOUT_WINDOW, PROCESSED_DATA_DIR, REPO_ROOT, SITE_DATA_DIR
from analysis.io import round_significant, write_json_atomic, write_parquet_atomic

ML_REF: Final = "origin/ml/challenger"
ML_PATH: Final = "data/processed/ml_supply_backtest.parquet"
OUTCOMES: Final = ("log_kg", "log_count", "log_avg_kg")
RULE: Final = (
    "kg from v2 (top-down + B1); average weight from the ML challenger; fish count = kg / weight. "
    "Chosen on the development window 2021-2024 before reading holdout results for the combination."
)
SOURCES: Final = {"log_kg": "v2", "log_avg_kg": "ml", "log_count": "v2 kg / ml weight"}


def load_ml_backtest(path: Path | None, ref: str = ML_REF) -> pd.DataFrame:
    """Nikita's backtest: a given file, else the repo copy, else straight from his branch."""

    local = REPO_ROOT / ML_PATH
    if path is None and local.exists():
        path = local
    if path is not None:
        return pd.read_parquet(path)
    blob = subprocess.run(
        ["git", "show", f"{ref}:{ML_PATH}"], cwd=REPO_ROOT, capture_output=True, check=True
    ).stdout
    with tempfile.TemporaryDirectory() as folder:
        target = Path(folder) / "ml_supply_backtest.parquet"
        target.write_bytes(blob)
        return pd.read_parquet(target)


def combine(ml: pd.DataFrame, topdown: pd.DataFrame) -> pd.DataFrame:
    """One row per area-month: actuals and every model's log forecast, plus the combination."""

    this_month = ml.loc[(ml["h"] == 0) & ml["window"].isin(["dev", "holdout"])]
    wide = this_month.pivot_table(
        index=["area", "month", "window"],
        columns="outcome",
        values=["actual", "b1", "drivers", "ml", "blend"],
    )
    wide.columns = [f"{model}_{outcome}" for model, outcome in wide.columns]
    wide = wide.reset_index().merge(
        topdown[["area", "month", "v2"]], on=["area", "month"], how="left", validate="one_to_one"
    )
    wide["combined_log_kg"] = wide["v2"]
    wide["combined_log_avg_kg"] = wide["ml_log_avg_kg"]
    wide["combined_log_count"] = wide["v2"] - wide["ml_log_avg_kg"]
    return wide


def scores(frame: pd.DataFrame) -> dict[str, Any]:
    """MAE by window and outcome on rows where every compared model has a forecast."""

    models = ("b1", "drivers", "ml", "blend", "combined")
    result: dict[str, Any] = {}
    for window in ("dev", "holdout"):
        part = frame.loc[frame["window"] == window]
        result[window] = {}
        for outcome in OUTCOMES:
            columns = [f"actual_{outcome}"] + [f"{model}_{outcome}" for model in models]
            rows = part.dropna(subset=columns + ["v2"])
            result[window][outcome] = {
                "n": int(len(rows)),
                **{
                    model: round_significant(
                        float((rows[f"actual_{outcome}"] - rows[f"{model}_{outcome}"]).abs().mean())
                    )
                    for model in models
                },
            } if len(rows) else None
    return result


def backtest_records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    records = []
    usable = frame.dropna(subset=["combined_log_kg", "combined_log_avg_kg"])
    for row in usable.sort_values(["month", "area"]).itertuples(index=False):
        records.append(
            {
                "area": int(row.area),
                "month": row.month,
                "window": row.window,
                "actual": {key: _level(getattr(row, f"actual_{outcome}")) for key, outcome in _KEYS},
                "pred": {key: _level(getattr(row, f"combined_{outcome}")) for key, outcome in _KEYS},
            }
        )
    return records


_KEYS: Final = (("kg", "log_kg"), ("count", "log_count"), ("avg_kg", "log_avg_kg"))


def _level(value: float) -> float | int | None:
    return round_significant(float(np.exp(value))) if np.isfinite(value) else None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--processed", type=Path, default=PROCESSED_DATA_DIR)
    parser.add_argument("--site", type=Path, default=SITE_DATA_DIR)
    parser.add_argument("--ml-backtest", type=Path, default=None)
    args = parser.parse_args()

    ml = load_ml_backtest(args.ml_backtest)
    topdown = pd.read_parquet(args.processed / "topdown_backtest.parquet")
    frame = combine(ml, topdown)
    write_parquet_atomic(frame, args.processed / "combined_backtest.parquet")
    summary = {
        "rule": RULE,
        "sources": SOURCES,
        "windows": {
            "dev": [DEVELOPMENT_WINDOW.start, DEVELOPMENT_WINDOW.end],
            "holdout": [HOLDOUT_WINDOW.start, HOLDOUT_WINDOW.end],
        },
        "scores": scores(frame),
        "note": "MAE in log points; holdout opened early by the team at 23:47 on 7 Nov 2026.",
        "backtest": backtest_records(frame),
    }
    write_json_atomic(summary, args.site / "combined.json")
    for window, outcomes in summary["scores"].items():
        for outcome, row in outcomes.items():
            print(window, outcome, row)


if __name__ == "__main__":
    main()
