"""Partition-protected access to dated production forecast inputs.

Development reads use Parquet filters before materialising a DataFrame. No
holdout vintage, label or forecast row is needed to tune development models.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from analysis.config import AREAS, DEVELOPMENT_WINDOW, HOLDOUT_WINDOW
from analysis.nowcast_inputs import OUTCOMES, forecast_date, model_features


class VintageStore:
    """One immutable historical snapshot per forecast month.

    ``final=True`` permits reading the held-out months; the calling CLI must
    enforce the real final-run time and once-only guards before creating it.
    Returned frames are copies so fold-specific preprocessing cannot mutate
    another model's training inputs.
    """

    def __init__(self, input_dir: str | Path, final: bool = False):
        self.input_dir = Path(input_dir)
        self.final = bool(final)
        self.end = HOLDOUT_WINDOW.end if self.final else DEVELOPMENT_WINDOW.end
        vintages = pd.read_parquet(
            self.input_dir / "nowcast_vintages.parquet",
            filters=[("forecast_month", "<=", self.end)],
        )
        targets = pd.read_parquet(
            self.input_dir / "nowcast_targets.parquet",
            filters=[("month", "<=", self.end)],
        )
        self._initialise(vintages, targets)

    @classmethod
    def from_frames(cls, vintages: pd.DataFrame, targets: pd.DataFrame, *, final=False):
        """In-memory constructor for synthetic tests, with the same guards."""
        result = cls.__new__(cls)
        result.input_dir = None
        result.final = bool(final)
        result.end = HOLDOUT_WINDOW.end if result.final else DEVELOPMENT_WINDOW.end
        result._initialise(
            vintages.loc[vintages.forecast_month <= result.end].copy(),
            targets.loc[targets.month <= result.end].copy(),
        )
        return result

    def _initialise(self, vintages, targets):
        required = {
            "area", "month", "forecast_month", "made_on", "is_target",
            "feature_available_at", "label_available_at",
            *model_features(True)["drivers"],
            *[name + suffix for name in OUTCOMES for suffix in ("_anom", "_base", "_label")],
        }
        missing = required - set(vintages)
        if missing:
            raise ValueError(f"Nowcast vintages missing columns: {sorted(missing)}")
        target_required = {"area", "month", "available_at", *OUTCOMES, *OUTCOMES.values()}
        missing = target_required - set(targets)
        if missing:
            raise ValueError(f"Nowcast targets missing columns: {sorted(missing)}")
        if vintages.empty:
            raise ValueError("No forecast vintages in the permitted partition")
        if vintages.duplicated(["forecast_month", "area", "month"]).any():
            raise ValueError("Duplicate vintage area-month rows")
        if targets.duplicated(["area", "month"]).any():
            raise ValueError("Duplicate target area-month rows")
        for frame, columns in ((vintages, ["month", "forecast_month"]), (targets, ["month"])):
            for name in columns:
                if frame[name].isna().any() or not frame[name].astype(str).str.fullmatch(r"\d{4}-\d{2}").all():
                    raise ValueError(f"Invalid {name} labels")
                parsed = pd.to_datetime(frame[name] + "-01", errors="raise")
                if not parsed.dt.strftime("%Y-%m").eq(frame[name]).all():
                    raise ValueError(f"Invalid {name} labels")
            if not frame.area.isin(AREAS).all():
                raise ValueError("Nowcast rows must use areas 1-13")
        if (vintages.month > vintages.forecast_month).any():
            raise ValueError("A vintage contains future observation months")
        if (vintages.forecast_month > self.end).any() or (targets.month > self.end).any():
            raise ValueError("Holdout data escaped the partition filter")
        if not vintages.is_target.eq(vintages.month.eq(vintages.forecast_month)).all():
            raise ValueError("is_target disagrees with forecast month")
        for name in ("made_on", "feature_available_at", "label_available_at"):
            vintages[name] = pd.to_datetime(vintages[name], errors="raise").astype("datetime64[ns]")
        targets["available_at"] = pd.to_datetime(targets.available_at, errors="raise").astype("datetime64[ns]")
        expected_date = vintages.forecast_month.map(forecast_date)
        if vintages.made_on.isna().any() or not vintages.made_on.eq(expected_date).all():
            raise ValueError("Vintage dates must be the 10th of the following month")
        if (vintages.feature_available_at > vintages.made_on).any():
            raise ValueError("Vintage contains predictors published after its forecast")
        if (vintages.label_available_at > vintages.made_on).any():
            raise ValueError("Vintage contains labels published after its forecast")
        target_rows = vintages.loc[vintages.is_target]
        expected = set(AREAS)
        if any(set(group.area) != expected for _, group in target_rows.groupby("forecast_month")):
            raise ValueError("Each forecast month must contain all 13 target areas")
        target_labels = [name + suffix for name in OUTCOMES for suffix in ("_anom", "_label")]
        if target_rows[target_labels].notna().any().any() or target_rows.label_available_at.notna().any():
            raise ValueError("Target labels leaked into the forecasting vintage")
        for frame in (vintages, targets):
            numeric = frame.select_dtypes(include="number").to_numpy(dtype=float, na_value=np.nan)
            if np.isinf(numeric).any():
                raise ValueError("Non-finite input values must be missing, not infinity")
        for name, level in OUTCOMES.items():
            expected_log = np.log(targets[level].where(targets[level] > 0))
            if not np.allclose(targets[name], expected_log, equal_nan=True):
                raise ValueError(f"{name} targets must be ordinary logs of positive {level}")
            labeled = vintages[name + "_label"].notna()
            if vintages.loc[labeled, "label_available_at"].isna().any():
                raise ValueError("A historical label has no publication date")
        self._vintages = vintages.sort_values(["forecast_month", "area", "month"]).reset_index(drop=True)
        self._targets = targets.sort_values(["area", "month"]).reset_index(drop=True)
        self.months = tuple(sorted(self._vintages.forecast_month.unique()))
        self._groups = {
            month: frame.reset_index(drop=True)
            for month, frame in self._vintages.groupby("forecast_month", sort=True)
        }

    def vintage(self, month: str | pd.Period) -> pd.DataFrame:
        month = str(pd.Period(month, freq="M"))
        if month > self.end:
            raise ValueError("Holdout vintages are protected in development mode")
        if month not in self._groups:
            raise ValueError(f"No prepared vintage for {month}")
        return self._groups[month].copy(deep=True)

    def targets(self) -> pd.DataFrame:
        return self._targets.copy(deep=True)

    def feature_sets(self, month: str | pd.Period) -> dict[str, list[str]]:
        vintage = self.vintage(month)
        return model_features(include_disease=bool(vintage.disease_share.notna().any()))

    def audit(self) -> dict:
        """Coverage and sparse-area diagnostics, with no model fit or score."""
        target_rows = self._vintages.loc[self._vintages.is_target]
        area_diagnostics = {}
        for area in (1, 13):
            target = self._targets.loc[self._targets.area == area]
            forecasts = target_rows.loc[target_rows.area == area]
            area_diagnostics[str(area)] = {
                "actual_area_months": len(target),
                "zero_harvest_months": int(target.harvest_count.eq(0).sum()),
                "undefined_log_targets": int(target.log_kg.isna().sum()),
                "target_base_missing": {name: int(forecasts[name + "_base"].isna().sum()) for name in OUTCOMES},
                "target_base_range": {
                    name: {"min": _finite(forecasts[name + "_base"].min()), "max": _finite(forecasts[name + "_base"].max())}
                    for name in OUTCOMES
                },
            }
        return {
            "mode": "final" if self.final else "development",
            "first_forecast_month": self.months[0], "last_forecast_month": self.months[-1],
            "forecast_months": len(self.months), "target_area_rows": len(target_rows),
            "snapshot_rows": len(self._vintages),
            "unique_historical_area_months": int(self._vintages[["area", "month"]].drop_duplicates().shape[0]),
            "label_area_months": len(self._targets),
            "sparse_areas": area_diagnostics,
            "notes": ["Snapshot rows repeat historical area-months and are not independent samples.",
                      "Only the permitted chronological partition was read from Parquet."],
        }


def _finite(value):
    return float(value) if pd.notna(value) and np.isfinite(value) else None
