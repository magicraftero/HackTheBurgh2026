"""Fixed Production configuration.

Evaluation windows and decision thresholds are pre-registered. Keeping them in
one module reduces the risk of accidental drift between analysis scripts.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DATA_DIR = REPO_ROOT / "data" / "processed"
SITE_DATA_DIR = REPO_ROOT / "web" / "public" / "data"

AREAS = tuple(range(1, 14))
NATIONAL_AREAS = tuple(range(14))


@dataclass(frozen=True)
class EvaluationWindow:
    """Inclusive target-month window used by the walk-forward backtest."""

    start: str
    end: str


DEVELOPMENT_WINDOW = EvaluationWindow("2021-01", "2024-12")
HOLDOUT_WINDOW = EvaluationWindow("2025-01", "2026-09")

F1_MINIMUM_IMPROVEMENT_PCT = 5.0
F1_MAXIMUM_P_VALUE = 0.05
NOWCAST_DAY_OF_FOLLOWING_MONTH = 10
DIRECTORATE_RELEASE_DAY_OF_FOLLOWING_MONTH = 20
