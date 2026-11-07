"""Fixed ML challenger settings, as pre-registered in prereg/ML_PLAN.md.

Windows and the freeze come from Production's and Price's own modules, so the
challenger can never drift from the pre-registered evaluation windows.
"""

from __future__ import annotations

from typing import Final

from analysis.config import DEVELOPMENT_WINDOW, HOLDOUT_WINDOW, PROCESSED_DATA_DIR, SITE_DATA_DIR
from analysis.nowcast import FREEZE_AT, OUTCOMES
from price.backtest import FREEZE as PRICE_FREEZE
from price.backtest import WINDOWS as PRICE_WINDOWS

__all__ = [
    "DEVELOPMENT_WINDOW", "HOLDOUT_WINDOW", "PROCESSED_DATA_DIR", "SITE_DATA_DIR",
    "FREEZE_AT", "OUTCOMES", "PRICE_FREEZE", "PRICE_WINDOWS",
]

GBM_PARAMS: Final = {
    "loss": "absolute_error",
    "max_depth": 3,
    "learning_rate": 0.05,
    "max_iter": 300,
    "min_samples_leaf": 20,
    "l2_regularization": 1.0,
    "early_stopping": False,
    "random_state": 0,
}

SUPPLY_HORIZONS: Final = (0, 1, 2, 3)
SUPPLY_WARMUP_START: Final = "2019-07"
SUPPLY_MODELS: Final = ("seasonal", "b0", "b1", "drivers", "ml", "blend")
SUPPLY_LINEAR: Final = ("b0", "b1", "drivers")

PRICE_HORIZONS: Final = tuple(range(1, 9))
PRICE_SHOWN_HORIZONS: Final = (1, 2, 4, 8)
PRICE_WARMUP_START: Final = "2019-W40"
PRICE_MODELS: Final = ("rw", "ar", "c0", "c1", "ml", "blend")

BAND_LEVELS: Final = (0.1, 0.9)
SUPPLY_BAND_MONTHS: Final = 36
SUPPLY_BAND_MIN_MONTHS: Final = 12
PRICE_BAND_WEEKS: Final = 156
PRICE_BAND_MIN_WEEKS: Final = 52

WINNER_MARGIN: Final = 0.02
LEAKAGE_RATIO: Final = 0.8

MODEL_LABELS: Final = {
    "seasonal": "Seasonal normal",
    "b0": "Stock (biomass, fish numbers)",
    "b1": "Stock + export volume",
    "drivers": "Linear, all drivers",
    "ml": "Gradient-boosted trees",
    "blend": "Blend (linear + trees)",
    "rw": "No change",
    "ar": "Price history + season",
    "c0": "Market",
    "c1": "Market + biology",
}
