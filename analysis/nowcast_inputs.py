"""Dated model inputs; no regression fits or holdout scoring.

Descriptive full-sample anomalies are deliberately ignored here. Each vintage
refits seasonal adjustment from published levels and builds calendar lags.
"""

import numpy as np
import pandas as pd

from analysis.anomalies import decompose
from analysis.config import AREAS
from analysis.drivers import add_directorate_levels
from analysis.panel import monthly_export_levels, week_month, week_start_from_label
from analysis.weekly_indices import _add_group_features

DIRECTORATE_FEATURES = [
    ("biomass_kg", "biomass_anom", "log"),
    ("fish_stock", "fish_stock_anom", "log"),
    ("smolt_pipe", "smolt_pipe_anom", "none"),
    ("feed_rate", "feed_rate_anom", "log"),
    ("mortality", "mortality_anom", "log1p"),
]
WEEKLY_FEATURES = ["mobile_anom", "treat_anom", "disease_share", "dd_below8", "dd_8to14", "dd_above14"]
OUTCOMES = {"log_kg": "harvest_kg", "log_count": "harvest_count", "log_avg_kg": "avg_kg"}
B0_FEATURES = ["biomass_anom_l1", "fish_stock_anom_l1"]
B1_FEATURES = [*B0_FEATURES, "export_vol_anom"]
DRIVERS_FEATURES = [*B1_FEATURES, "smolt_pipe_anom_l1", "feed_rate_anom_l1", "mortality_anom_l1",
                    *[name + suffix for name in WEEKLY_FEATURES for suffix in ("", "_l1")]]


def forecast_date(target):
    return (pd.Period(target, freq="M") + 1).to_timestamp() + pd.Timedelta(days=9)


def model_features(include_disease=True):
    return {"b0": B0_FEATURES.copy(), "b1": B1_FEATURES.copy(),
            "drivers": [c for c in DRIVERS_FEATURES if include_disease or not c.startswith("disease_share")]}


def components(values, freq, transform, fit_end):
    try:
        return decompose(values.astype(float), freq, transform, fit_end)
    except ValueError as error:
        if "Not enough usable observations" not in str(error):
            raise
        return pd.DataFrame(np.nan, index=values.index, columns=["y", "level", "season", "anomaly"])


class NowcastInputs:
    def __init__(self, directorate, weekly_area, ssb_weekly):
        self.directorate = directorate.copy()
        self.directorate["date"] = pd.to_datetime(self.directorate.month + "-01")
        self.directorate["available_at"] = pd.to_datetime(self.directorate.available_at)
        self.first_month = self.directorate.date.min()
        self.weekly = weekly_area.copy()
        self.weekly["week_start"] = week_start_from_label(self.weekly.week)
        self.weekly["available_at"] = pd.to_datetime(self.weekly.available_at)
        self.ssb = ssb_weekly.copy()
        self.ssb["available_at"] = pd.to_datetime(self.ssb.available_at)
        self.include_disease = self.weekly.disease_share.notna().any()

    def build_vintage(self, target, made_on=None):
        """Return training rows and target rows from one publication snapshot.

        Labels in the target month are always null; join evaluation targets
        separately, after prediction. Stored *_anom columns are never read.
        """
        target = pd.Period(target, freq="M")
        made_on = forecast_date(target) if made_on is None else min(pd.Timestamp(made_on), forecast_date(target))
        last_known = (target - 1).to_timestamp()
        # Weekly membership follows Thursday. A Monday in the preceding
        # calendar month can belong to the target month and must not enter fit.
        weekly_fit_end = target.to_timestamp() - pd.Timedelta(days=4)
        grid = pd.date_range(self.first_month, target.to_timestamp(), freq="MS")
        row_dates = pd.Series([forecast_date(d) for d in grid], index=grid)
        include_disease = self.weekly.loc[self.weekly.available_at <= made_on, "disease_share"].notna().any()
        public_ssb = self.ssb.loc[self.ssb.available_at <= made_on]
        export = monthly_export_levels(public_ssb).reindex(grid)
        export_release = public_ssb.assign(month=week_month(public_ssb.week_start)).groupby("month").available_at.max()
        export_releases = pd.Series(grid.strftime("%Y-%m").map(export_release), index=grid)
        export = export.where(export_releases <= row_dates)
        export_anom = components(export, "M", "log", last_known).anomaly

        frames = []
        for area in AREAS:
            source = self.directorate.loc[self.directorate.area == area].set_index("date").reindex(grid)
            published = (source.index <= last_known) & (source.available_at <= made_on)
            known = source.copy()
            numeric = ["biomass_kg", "fish_stock", "smolt_released", "feed_kg", "dead", *OUTCOMES.values()]
            known.loc[~published, list(set(numeric))] = np.nan
            levels = add_directorate_levels(known)
            frame = pd.DataFrame(index=grid)
            previous_release = source.available_at.shift(1)
            for level, name, transform in DIRECTORATE_FEATURES:
                adjusted = components(levels[level], "M", transform, last_known).anomaly.shift(1)
                frame[name + "_l1"] = adjusted.where(previous_release <= row_dates)
            frame["export_vol_anom"] = export_anom
            weekly, bw_releases = self._monthly_weekly(area, made_on, weekly_fit_end, grid, row_dates)
            for column in WEEKLY_FEATURES:
                frame[column] = weekly[column]
                frame[column + "_l1"] = weekly[column].shift(1)
            for name, level in OUTCOMES.items():
                parts = components(known[level], "M", "log", last_known)
                frame[name + "_anom"] = parts.anomaly
                frame[name + "_base"] = parts.level + parts.season
                frame[name + "_label"] = parts.y
            # Track actual source releases rather than one coarse monthly stamp.
            releases = pd.concat([previous_release, export_releases, bw_releases, bw_releases.shift(1)], axis=1)
            frame["feature_available_at"] = releases.max(axis=1)
            frame["label_available_at"] = source.available_at.where(published)
            frame["area"] = area
            frame["month"] = grid.strftime("%Y-%m")
            frame["forecast_month"] = str(target)
            frame["made_on"] = pd.Series(made_on, index=grid, dtype="datetime64[ns]")
            frame["is_target"] = grid == target.to_timestamp()
            for model, columns in model_features(include_disease).items():
                frame[model + "_ready"] = frame[columns].notna().all(axis=1) & (frame.feature_available_at <= made_on)
            frames.append(frame.reset_index(drop=True))
        return pd.concat(frames, ignore_index=True)

    def _monthly_weekly(self, area, made_on, fit_end, grid, row_dates):
        weekly = self.weekly.loc[(self.weekly.area == area) & (self.weekly.available_at <= made_on)].copy()
        dates = pd.date_range(self.weekly.week_start.min(), max(fit_end, grid[-1] + pd.offsets.MonthEnd(0)), freq="W-MON")
        weekly = weekly.set_index("week_start").reindex(dates).rename_axis("week_start").reset_index()
        # Rebuild normals/bands from public temperatures as well as refitting
        # anomalies: an old row with a delayed release must not leak into them.
        weekly = _add_group_features(weekly)
        for level, name, scale in [("mobile_idx", "mobile_anom", 1), ("treat_rate", "treat_anom", 100)]:
            values = pd.Series(scale * weekly[level].to_numpy(), index=dates)
            weekly[name] = components(values, "W", "log1p", fit_end).anomaly.to_numpy()
        weekly["month"] = week_month(weekly.week_start)
        own_forecast = pd.to_datetime(weekly.month + "-01") + pd.offsets.MonthBegin(1) + pd.Timedelta(days=9)
        allowed = weekly.available_at.notna() & (weekly.available_at <= own_forecast)
        weekly.loc[~allowed, WEEKLY_FEATURES] = np.nan
        monthly = weekly.groupby("month")[WEEKLY_FEATURES].mean()
        monthly.index = pd.to_datetime(monthly.index + "-01")
        release = weekly.loc[allowed].groupby("month").available_at.max()
        release.index = pd.to_datetime(release.index + "-01")
        return monthly.reindex(grid), release.reindex(grid)


def build_targets(directorate):
    """Evaluation labels kept apart from feature snapshots, with zero flags."""
    result = directorate.loc[directorate.area.isin(AREAS),
                             ["area", "month", "harvest_kg", "harvest_count", "avg_kg", "available_at"]].copy()
    for name, level in OUTCOMES.items():
        result[name] = np.log(result[level].where(result[level] > 0))
    result["zero_harvest"] = result.harvest_count == 0
    result["log_targets_valid"] = result[list(OUTCOMES)].notna().all(axis=1)
    return result.sort_values(["area", "month"]).reset_index(drop=True)
