"""Build origin snapshots from published levels, never stored anomaly columns."""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from price.anomalies import get_anomaly
from price.calendar import week_start

C0_FEATURES = ["v_anom", "v_anom_lag1", "weight_anom", "eurnok_chg", "eurnok_chg_lag1"]
C1_DRIVERS = ["mobile_anom", "treat_anom", "disease_share", "dd_below8", "dd_8to14",
              "dd_above14", "biomass_anom", "feed_rate_anom", "mortality_anom", "usdnok_chg"]


def driver_features(drivers):
    result = []
    for name in drivers:
        result.append(name)
        if name in {"mobile_anom", "treat_anom", "usdnok_chg"}:
            result.append(name + "_lag1")
    return result


def _require(frame, columns, name):
    missing = set(columns) - set(frame.columns)
    if missing:
        raise ValueError(f"{name}: missing columns {', '.join(sorted(missing))}")


def _dates(frame, column):
    dates = pd.to_datetime(frame[column], errors="raise").astype("datetime64[ns]")
    if dates.isna().any() or (dates != dates.dt.normalize()).any():
        raise ValueError(f"{column} must contain non-null midnight dates")
    return dates


def _weekly(frame, name, columns):
    _require(frame, ["week", "available_at", *columns], name)
    frame = frame.copy()
    frame.index = pd.DatetimeIndex(frame.week.map(week_start), name="period")
    if frame.index.duplicated().any():
        raise ValueError(f"{name}: duplicate weeks")
    frame["available_at"] = _dates(frame, "available_at")
    if (frame.available_at < frame.index + pd.Timedelta(days=7)).any():
        raise ValueError(f"{name}: a week cannot be published before it ends")
    if "week_start" in frame and not (pd.to_datetime(frame.week_start) == frame.index).all():
        raise ValueError(f"{name}: week_start disagrees with ISO week")
    return frame.sort_index()


def _monthly(frame, name, columns):
    _require(frame, ["month", *columns], name)
    frame = frame.copy()
    frame.index = pd.DatetimeIndex(pd.to_datetime(frame.month + "-01"), name="period")
    if frame.index.duplicated().any():
        raise ValueError(f"{name}: duplicate months")
    if "available_at_dir" in frame:
        frame["available_at"] = _dates(frame, "available_at_dir")
    elif "available_at" in frame:
        frame["available_at"] = _dates(frame, "available_at")
    else:
        frame["available_at"] = frame.index + pd.offsets.MonthBegin(1) + pd.Timedelta(days=19)
    if (frame.available_at <= frame.index + pd.offsets.MonthEnd(0)).any():
        raise ValueError(f"{name}: publication must follow the observation month")
    return frame.sort_index()


def national_months(directorate):
    """Include suppressed area 0. Ratios of sums; missing inputs stay missing."""
    columns = ["harvest_kg", "harvest_count", "biomass_kg", "feed_kg", "dead", "fish_stock"]
    _require(directorate, ["area", "month", "available_at", *columns], "Directorate")
    if directorate.duplicated(["area", "month"]).any():
        raise ValueError("Directorate: duplicate area-month rows")
    if not directorate.area.between(0, 13).all():
        raise ValueError("Directorate: areas must be 0–13")
    source = directorate.copy()
    source["available_at"] = _dates(source, "available_at")
    groups = source.groupby("month", sort=True)
    sums = groups[columns].sum(min_count=1)
    sums = sums.mask(groups[columns].count().ne(groups.size(), axis=0))
    # A missing area row is missing national data, not a smaller national total.
    sums.loc[groups.area.nunique() != 14, columns] = np.nan
    sums["available_at"] = groups.available_at.max()
    sums["avg_kg"] = sums.harvest_kg / sums.harvest_count.where(sums.harvest_count > 0)
    sums["feed_rate"] = sums.feed_kg / sums.biomass_kg.where(sums.biomass_kg > 0)
    sums["mortality"] = 1000 * sums.dead / sums.fish_stock.where(sums.fish_stock > 0)
    return sums.reset_index()


@dataclass
class PriceDataset:
    ssb: pd.DataFrame
    fx: pd.DataFrame
    weight: pd.DataFrame
    monthly: pd.DataFrame
    weekly: pd.DataFrame | None
    notes: list[str]

    @classmethod
    def from_frames(cls, ssb, fx, directorate, weekly=None, monthly=None):
        ssb = _weekly(ssb, "SSB", ["price_nok_kg", "volume_t"])
        for name in ["price_nok_kg", "volume_t"]:
            if (ssb[name].dropna() <= 0).any():
                raise ValueError(f"SSB: {name} must be positive or null")
        _require(fx, ["date", "available_at", "eurnok", "usdnok"], "FX")
        fx = fx.copy()
        fx["date"] = _dates(fx, "date")
        fx["available_at"] = _dates(fx, "available_at")
        if fx.date.duplicated().any() or (fx.available_at <= fx.date).any():
            raise ValueError("FX: duplicate dates or publication before the next day")
        if (fx[["eurnok", "usdnok"]] <= 0).any().any():
            raise ValueError("FX rates must be positive or null")
        national = national_months(directorate)
        weight = _monthly(national, "National weight", ["avg_kg"])
        notes = ["Actuals are latest revised data, not archived first releases.",
                 "Publication lags reconstruct historical availability; holiday release dates are approximate."]
        incomplete = int(directorate.groupby("month").area.nunique().ne(14).sum())
        if incomplete:
            notes.append(f"National totals missing in {incomplete} months: not all areas 0–13 were delivered.")
        if monthly is None:
            monthly = national
            notes.append("Monthly driver levels built from Directorate national sums (areas 0–13).")
        monthly = _monthly(monthly, "Monthly drivers", ["biomass_kg", "feed_rate", "mortality"])
        if weekly is not None:
            weekly = _weekly(weekly, "National weekly index", ["mobile_idx", "treat_rate",
                "disease_share", "dd_below8", "dd_8to14", "dd_above14"])
            if weekly.disease_share.isna().all():
                notes.append("disease_share dropped from c1: no disease flags in BarentsWatch.")
        else:
            notes.append("c1 unavailable: weekly_national_index.parquet has not landed; preliminary rw/ar/c0 only.")
        return cls(ssb, fx.sort_values("date"), weight, monthly, weekly, notes)

    @classmethod
    def load(cls, directory):
        directory = Path(directory)
        required = ["ssb_weekly", "fx_daily", "directorate_area_month"]
        missing = [str(directory / (name + ".parquet")) for name in required
                   if not (directory / (name + ".parquet")).exists()]
        if missing:
            raise FileNotFoundError("Inputs have not landed yet: " + ", ".join(missing))
        frames = [pd.read_parquet(directory / (name + ".parquet")) for name in required]
        optional = [pd.read_parquet(directory / (name + ".parquet"))
                    if (directory / (name + ".parquet")).exists() else None
                    for name in ["weekly_national_index", "drivers_national_month"]]
        return cls.from_frames(*frames, *optional)

    @property
    def drivers(self):
        if self.weekly is None:
            return []
        return [name for name in C1_DRIVERS
                if name != "disease_share" or self.weekly.disease_share.notna().any()]

    @property
    def feature_columns(self):
        return C0_FEATURES + driver_features(self.drivers)

    def snapshot(self, origin):
        """At D refit anomalies, then as-of align to each training row's own D(s)."""
        origin = pd.Timestamp(origin)
        ssb = self.ssb.loc[self.ssb.available_at <= origin]
        if ssb.empty:
            return pd.DataFrame()
        grid = pd.date_range(self.ssb.index.min(), ssb.index.max(), freq="W-MON")
        frame = ssb.reindex(grid).copy()
        frame["p"] = np.log(frame.price_nok_kg)
        origins = frame.available_at
        for lag in range(8):
            public = (frame.available_at.shift(lag) <= origins) & (frame.available_at.shift(lag + 1) <= origins)
            frame[f"dp_lag{lag}"] = frame.p.diff().shift(lag).where(public)
        frame["v_anom"] = _adjust(ssb, "volume_t", "W", "log", origin).reindex(grid)
        frame["v_anom_lag1"] = frame.v_anom.shift(1).where(frame.available_at.shift(1) <= origins)
        # A row is usable only at its own published origin; a missing latest
        # report stays missing, rather than falling back to an older valid value.
        weights = self.weight.loc[self.weight.available_at <= origin].copy()
        weights["weight_anom"] = _adjust(weights, "avg_kg", "M", "log", origin)
        frame["weight_anom"] = _asof(weights, origins, ["weight_anom"])["weight_anom"]
        fx = self.fx.loc[self.fx.available_at <= origin].copy()
        fx["period"] = fx.date - pd.to_timedelta(fx.date.dt.dayofweek, unit="D")
        fxweek = fx.groupby("period").agg(eurnok=("eurnok", "mean"), usdnok=("usdnok", "mean"),
                                         available_at=("available_at", "max"))
        if not fxweek.empty:
            fxgrid = pd.date_range(fxweek.index.min(), fxweek.index.max(), freq="W-MON")
            fxweek = fxweek.reindex(fxgrid)
        for name in ["eurnok", "usdnok"]:
            changes = np.log(fxweek[name]).diff().reindex(grid)
            valid = fxweek.available_at.reindex(grid) <= origins
            prev_valid = fxweek.available_at.shift(1).reindex(grid) <= origins
            frame[name + "_chg"] = changes.where(valid & prev_valid)
            frame[name + "_chg_lag1"] = frame[name + "_chg"].shift(1)
        if self.weekly is not None:
            weekly = self.weekly.loc[self.weekly.available_at <= origin].copy()
            weekly["mobile_anom"] = _adjust(weekly, "mobile_idx", "W", "log1p", origin)
            weekly["treat_anom"] = _adjust(weekly.assign(treat_pct=100 * weekly.treat_rate),
                                            "treat_pct", "W", "log1p", origin)
            weekly_cols = ["mobile_anom", "treat_anom", "disease_share",
                           "dd_below8", "dd_8to14", "dd_above14"]
            # Exact L-1, even when an intermediate week has no report.
            for name in ["mobile_anom", "treat_anom"]:
                weekly[name + "_lag1"] = weekly[name].reindex(
                    weekly.index - pd.Timedelta(weeks=1)).to_numpy()
                weekly_cols.append(name + "_lag1")
            weekly["lag1_release"] = weekly.available_at.reindex(weekly.index - pd.Timedelta(weeks=1)).to_numpy()
            frame[weekly_cols] = _asof(weekly, origins, weekly_cols)
            lag_release = _asof(weekly, origins, ["lag1_release"])["lag1_release"]
            lag_public = pd.to_datetime(lag_release) <= origins
            for name in ["mobile_anom_lag1", "treat_anom_lag1"]:
                frame[name] = frame[name].where(lag_public)
            monthly = self.monthly.loc[self.monthly.available_at <= origin].copy()
            for name, level, transform in [("biomass_anom", "biomass_kg", "log"),
                                            ("feed_rate_anom", "feed_rate", "log"),
                                            ("mortality_anom", "mortality", "log1p")]:
                monthly[name] = _adjust(monthly, level, "M", transform, origin)
            names = ["biomass_anom", "feed_rate_anom", "mortality_anom"]
            frame[names] = _asof(monthly, origins, names)
        return frame.replace([np.inf, -np.inf], np.nan)


def _adjust(frame, column, freq, transform, origin):
    if frame.empty:
        return pd.Series(dtype=float, index=frame.index)
    grid = pd.date_range(frame.index.min(), frame.index.max(), freq="W-MON" if freq == "W" else "MS")
    values = frame[column].reindex(grid)
    anomaly, _ = get_anomaly()
    try:
        return anomaly(values, freq, transform=transform, fit_end=origin).reindex(frame.index)
    except ValueError as exc:
        if "Not enough usable observations" not in str(exc):
            raise
        return pd.Series(np.nan, index=frame.index)


def _asof(source, origins, columns):
    """Latest observation period released by each origin, including null values."""
    out = pd.DataFrame({name: pd.Series(pd.NaT, index=origins.index, dtype="datetime64[ns]")
                       if pd.api.types.is_datetime64_any_dtype(source[name])
                       else pd.Series(np.nan, index=origins.index) for name in columns})
    if source.empty:
        return out
    # Cumulative max observation period handles out-of-order publication dates.
    ordered = source.sort_values("available_at").copy()
    ordered["latest_period"] = ordered.index.to_series().cummax()
    ordered = ordered.drop_duplicates("available_at", keep="last")
    queries = pd.DataFrame({"origin": origins}).dropna().sort_values("origin")
    if queries.empty:
        return out
    joined = pd.merge_asof(queries, ordered[["available_at", "latest_period"]],
                           left_on="origin", right_on="available_at", direction="backward")
    rows = source[columns].reindex(pd.DatetimeIndex(joined.latest_period))
    out.loc[queries.index, columns] = rows.to_numpy()
    return out
