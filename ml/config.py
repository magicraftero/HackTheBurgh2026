"""Fixed settings for the harvest model, as pre-registered in prereg/ML_PLAN.md.

The model is the blend: the mean of the linear Drivers model and gradient-boosted
trees, both refitted at every issue date. The evaluation windows and the freeze
come from Production's module, so the model can never drift from them.
"""

from __future__ import annotations

from typing import Final

from analysis.config import DEVELOPMENT_WINDOW, HOLDOUT_WINDOW, PROCESSED_DATA_DIR, SITE_DATA_DIR
from analysis.nowcast import FREEZE_AT, OUTCOMES

__all__ = ["DEVELOPMENT_WINDOW", "HOLDOUT_WINDOW", "PROCESSED_DATA_DIR", "SITE_DATA_DIR", "FREEZE_AT", "OUTCOMES"]

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
# The linear half of the model; the other half is the gradient-boosted trees ("ml").
SUPPLY_LINEAR: Final = ("drivers",)
MODEL: Final = "blend"
# What the site shows: the model, and the seasonal normal (level + season, no drivers) as the reference line.
SUPPLY_MODELS: Final = ("seasonal", MODEL)

BAND_LEVELS: Final = (0.1, 0.9)
SUPPLY_BAND_MONTHS: Final = 36
SUPPLY_BAND_MIN_MONTHS: Final = 12

MODEL_LABELS: Final = {
    "seasonal": "Seasonal normal",
    "blend": "Harvest model (linear + trees)",
}
