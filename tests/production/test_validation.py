import numpy as np
import pandas as pd
import pytest

from analysis.validation import validate_sources


def sources(directorate, ssb_weekly):
    farms = pd.DataFrame({"locality_no": [101], "area": [1], "capacity_t": [100.]})
    fw = pd.DataFrame({"locality_no": [101], "area": [1], "week": ["2024-W01"],
                       "week_start": pd.to_datetime(["2024-01-01"]), "reported": [True],
                       "mobile": [1.], "adult_female": [.5], "stationary": [.2],
                       "treated": [False], "sea_temp_c": [10.], "isa": [False], "pd": [False],
                       "available_at": pd.to_datetime(["2024-01-14"])})
    return directorate.copy(), fw, farms, ssb_weekly.copy()


def test_valid_sources_pass(directorate, ssb_weekly):
    validate_sources(*sources(directorate, ssb_weekly))


@pytest.mark.parametrize("case, message", [
    ("duplicate", "duplicate site-week"),
    ("early_release", "publication earlier"),
    ("bad_temp", "temperature outside"),
    ("unreported_lice", "unreported lice"),
    ("wrong_area", "register area mismatch"),
    ("bad_capacity", "capacity must be positive"),
    ("missing_area", "every calendar month needs areas 0-13"),
    ("fake_zero_weight", "avg_kg must be null"),
])
def test_rejects_corrupt_sources(directorate, ssb_weekly, case, message):
    d, fw, farms, ssb = sources(directorate, ssb_weekly)
    if case == "duplicate":
        fw = pd.concat([fw, fw], ignore_index=True)
    elif case == "early_release":
        fw["available_at"] = pd.Timestamp("2024-01-05")
    elif case == "bad_temp":
        fw["sea_temp_c"] = 99.
    elif case == "unreported_lice":
        fw["reported"] = False
    elif case == "wrong_area":
        fw["area"] = 2
    elif case == "bad_capacity":
        farms["capacity_t"] = 0.
    elif case == "missing_area":
        d = d.loc[~((d.area == 0) & (d.month == "2024-01"))]
    elif case == "fake_zero_weight":
        d.loc[d.harvest_count == 0, "avg_kg"] = 0.
    with pytest.raises(ValueError, match=message):
        validate_sources(d, fw, farms, ssb)
