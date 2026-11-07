"""Deterministic demonstration observations for tests; never public artifacts."""

import numpy as np
import pandas as pd

from price.calendar import iso_week
from price.dataset import PriceDataset


def frames():
    rng = np.random.default_rng(418)
    dates = pd.date_range("2012-01-02", "2026-11-02", freq="W-MON")
    n = len(dates)
    j = np.arange(n)
    price = np.exp(4 + np.cumsum(rng.normal(0, .025, n)) + .1 * np.sin(j / 8))
    ssb = pd.DataFrame({"week": [iso_week(d) for d in dates], "week_start": dates,
                        "price_nok_kg": price, "volume_t": 15000 * np.exp(.15 * np.sin(j / 7)),
                        "available_at": dates + pd.Timedelta(days=9)})
    daily = pd.date_range("2011-12-01", "2026-11-06", freq="B")
    fx = pd.DataFrame({"date": daily, "eurnok": 9 + .2 * np.sin(np.arange(len(daily)) / 80),
                       "usdnok": 8 + .3 * np.cos(np.arange(len(daily)) / 90),
                       "available_at": daily + pd.Timedelta(days=1)})
    months = pd.date_range("2017-10-01", "2026-09-01", freq="MS")
    rows = []
    for k, m in enumerate(months):
        for area in range(14):
            count = 1e6 * (area + 1) * (1 + .1 * np.cos(k))
            biomass = 7e6 * (area + 1) * (1 + .05 * np.sin(k))
            rows.append({"area": area, "month": m.strftime("%Y-%m"), "harvest_count": count,
                         "harvest_kg": count * (4.5 + .2 * np.sin(k / 2)), "biomass_kg": biomass,
                         "feed_kg": biomass * (.1 + .01 * np.cos(k / 3)), "dead": 1000 + 200 * np.cos(k),
                         "fish_stock": 1e7 * (area + 1),
                         "available_at": m + pd.offsets.MonthBegin(1) + pd.Timedelta(days=19)})
    weekly = pd.DataFrame({"week": ssb.week, "mobile_idx": .3 + .15 * np.sin(j / 10),
                           "treat_rate": .05 + .04 * np.cos(j / 13), "disease_share": .1 + .02 * np.sin(j / 6),
                           "dd_below8": np.where(j % 3 == 0, np.sin(j / 3), 0.),
                           "dd_8to14": np.where(j % 3 == 1, np.cos(j / 4), 0.),
                           "dd_above14": np.where(j % 3 == 2, np.sin(j / 5), 0.),
                           "available_at": dates + pd.Timedelta(days=13)})
    return ssb, fx, pd.DataFrame(rows), weekly


def dataset():
    return PriceDataset.from_frames(*frames())
