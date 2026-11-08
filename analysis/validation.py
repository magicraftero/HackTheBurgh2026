"""Fail before exporting when source tables violate the production contract."""

import numpy as np
import pandas as pd

from analysis.panel import week_start_from_label


def require(condition, message):
    if not bool(condition):
        raise ValueError(message)


def require_columns(frame, columns, name):
    missing = set(columns) - set(frame)
    require(not missing, f"{name}: missing columns {sorted(missing)}")


def dates(frame, column, name):
    values = pd.to_datetime(frame[column], errors="raise")
    require(values.notna().all() and (values == values.dt.normalize()).all(),
            f"{name}.{column}: non-null midnight dates required")
    return values.astype("datetime64[ns]")


def nonnegative(frame, columns, name, allow_missing=False):
    values = frame[columns].astype(float)
    valid = np.isfinite(values) & (values >= 0)
    if allow_missing:
        valid |= values.isna()
    require(valid.all().all(), f"{name}: invalid, negative, or unexpectedly missing numeric values")


def validate_sources(directorate, farm_week, farms, ssb):
    """Validate original data without changing or filling source observations."""
    numeric = ["harvest_count", "harvest_kg", "biomass_kg", "fish_stock",
               "smolt_released", "feed_kg", "dead"]
    require_columns(directorate, ["area", "month", "avg_kg", "available_at", *numeric], "Directorate")
    require(not directorate.duplicated(["area", "month"]).any(), "Directorate: duplicate area-month")
    month = pd.to_datetime(directorate.month + "-01", errors="raise")
    require((month.dt.strftime("%Y-%m") == directorate.month).all(), "Directorate: invalid month labels")
    grid = pd.MultiIndex.from_product([range(14), pd.date_range(month.min(), month.max(), freq="MS").strftime("%Y-%m")])
    require(set(zip(directorate.area, directorate.month)) == set(grid),
            "Directorate: every calendar month needs areas 0-13")
    nonnegative(directorate, numeric, "Directorate")
    no_harvest = directorate.harvest_count == 0
    require(no_harvest.equals(directorate.harvest_kg == 0), "Directorate: zero count and kg disagree")
    require(directorate.avg_kg.isna().equals(no_harvest), "Directorate: avg_kg must be null exactly at zero harvest")
    require(np.allclose(directorate.loc[~no_harvest, "avg_kg"],
                        directorate.loc[~no_harvest, "harvest_kg"] / directorate.loc[~no_harvest, "harvest_count"]),
            "Directorate: avg_kg disagrees with kg/count")
    releases = dates(directorate, "available_at", "Directorate")
    require((releases >= month + pd.offsets.MonthBegin(1) + pd.Timedelta(days=19)).all(),
            "Directorate: publication earlier than following month's 20th")

    require_columns(farms, ["locality_no", "area", "capacity_t"], "farms")
    require(not farms.locality_no.duplicated().any(), "farms: duplicate locality")
    require(farms.area.isin(range(1, 14)).all(), "farms: invalid area")
    capacity = farms.capacity_t.dropna()
    require((np.isfinite(capacity) & (capacity > 0)).all(), "farms: capacity must be positive or null")
    require(farms.groupby("area").capacity_t.median().notna().all(), "farms: no capacity median for an area")

    fields = ["locality_no", "area", "week", "week_start", "reported", "mobile",
              "adult_female", "stationary", "treated", "sea_temp_c", "isa", "pd", "available_at"]
    require_columns(farm_week, fields, "farm_week")
    require(not farm_week.duplicated(["locality_no", "week"]).any(), "farm_week: duplicate site-week")
    starts = dates(farm_week, "week_start", "farm_week")
    require(starts.equals(week_start_from_label(farm_week.week).rename(starts.name)),
            "farm_week: week label disagrees with week_start")
    releases = dates(farm_week, "available_at", "farm_week")
    require((releases >= starts + pd.Timedelta(days=13)).all(), "farm_week: publication earlier than week + 13 days")
    area = farm_week.locality_no.map(farms.set_index("locality_no").area)
    require(area.notna().all() and (area == farm_week.area).all(), "farm_week: farm register area mismatch")
    for column in ("reported", "treated", "isa", "pd"):
        require(farm_week[column].dropna().isin([True, False]).all(), f"farm_week: invalid {column} flag")
    unreported = ~farm_week.reported.fillna(False)
    require(farm_week.loc[unreported, ["mobile", "adult_female", "stationary"]].isna().all().all(),
            "farm_week: unreported lice must stay missing")
    nonnegative(farm_week, ["mobile", "adult_female", "stationary"], "farm_week", allow_missing=True)
    temp = farm_week.sea_temp_c.dropna()
    require(temp.between(-2, 25).all(), "farm_week: temperature outside cleaned -2..25 C bounds")
    require(farm_week.loc[farm_week.week < "2014-W01", ["isa", "pd"]].isna().all().all(),
            "farm_week: disease before 2014 must stay unknown")

    require_columns(ssb, ["week", "week_start", "volume_t", "available_at"], "SSB")
    require(not ssb.week.duplicated().any(), "SSB: duplicate week")
    starts = dates(ssb, "week_start", "SSB")
    require((starts.to_numpy() == week_start_from_label(ssb.week).to_numpy()).all(), "SSB: invalid week labels")
    require((dates(ssb, "available_at", "SSB") >= starts + pd.Timedelta(days=9)).all(),
            "SSB: publication earlier than week + 9 days")
    nonnegative(ssb, ["volume_t"], "SSB")

