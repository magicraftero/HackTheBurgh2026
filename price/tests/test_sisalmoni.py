from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal

from price.calendar import iso_week, week_start
from price.dataset import PriceDataset
from price.sisalmoni import _write_json, parse_public_years, retarget_dataset, run_sisalmoni, summarize
from price.tests.fixtures import frames


class IndexInputTests(unittest.TestCase):
    def test_eur_benchmark_is_used_instead_of_legacy_nok_fpi_field(self):
        result = parse_public_years([{"year": 2024, "months": [{"month": 8, "weeks": [
            {"week": 33, "fpiEUR": 6.20, "fpiNOK": 73.04}]}]}])
        self.assertEqual(result.loc[week_start("2024-W33")], 6.20)

    def test_settlement_december_week_one_belongs_to_next_iso_year(self):
        december = {"year": 2025, "months": [{"month": 12, "weeks": [
            {"week": 52, "fpiEUR": 100.88}, {"week": 1, "fpiEUR": 96.27}]}]}
        january = {"year": 2026, "months": [{"month": 1, "weeks": [
            {"week": 1, "fpiEUR": 96.27}, {"week": 2, "fpiEUR": 90.62}]}]}
        result = parse_public_years([december, january])
        self.assertEqual([iso_week(d) for d in result.index], ["2025-W52", "2026-W01", "2026-W02"])
        self.assertEqual(result.loc[week_start("2026-W01")], 96.27)
        conflict = deepcopy(january)
        conflict["months"][0]["weeks"][0]["fpiEUR"] = 1.0
        with self.assertRaisesRegex(ValueError, "conflicting duplicate"):
            parse_public_years([december, conflict])

    def test_rejects_legacy_splice_invalid_iso_week_and_invalid_prices(self):
        def entry(year, week, price):
            return [{"year": year, "months": [{"month": 8, "weeks": [{"week": week, "fpiEUR": price}]}]}]
        with self.assertRaisesRegex(ValueError, "pre-SISALMONI"):
            parse_public_years(entry(2024, 31, 50))
        with self.assertRaises(ValueError):
            parse_public_years(entry(2025, 53, 50))
        for price in [0, -1, np.nan, np.inf, True]:
            with self.subTest(price=price), self.assertRaisesRegex(ValueError, "finite and positive"):
                parse_public_years(entry(2025, 32, price))


class IndexBacktestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs = frames()
        dates = pd.date_range(week_start("2024-W32"), week_start("2026-W44"), freq="W-MON")
        rng = np.random.default_rng(901)
        cls.index = pd.Series(np.exp(4.2 + np.cumsum(rng.normal(0, .035, len(dates)))), index=dates)

    def test_missing_index_is_not_replaced_by_ssb_and_volume_history_survives(self):
        original = PriceDataset.from_frames(*self.inputs)
        index = self.index.drop(week_start("2025-W29"))
        dataset = retarget_dataset(original, index)
        self.assertTrue(pd.isna(dataset.ssb.loc[week_start("2024-W31"), "price_nok_kg"]))
        self.assertTrue(pd.isna(dataset.ssb.loc[week_start("2025-W29"), "price_nok_kg"]))
        np.testing.assert_array_equal(dataset.ssb.volume_t, original.ssb.volume_t)
        self.assertEqual(dataset.ssb.loc[week_start("2025-W30"), "available_at"],
                         week_start("2025-W30") + pd.Timedelta(days=10))
        self.assertTrue(original.ssb.price_nok_kg.notna().all())

    def test_future_mutation_cannot_change_past_forecasts_and_models_share_rows(self):
        original = PriceDataset.from_frames(*self.inputs)
        base = retarget_dataset(original, self.index)
        rows, _ = run_sisalmoni(base, {2: 2, 4: 2}, start="2025-W30", end="2025-W32", horizons=(2, 4))
        self.assertFalse(rows.empty)
        latest_issue = pd.Timestamp(rows.issue_date.max())
        altered = [frame.copy() for frame in self.inputs]
        for source in altered:
            future = source.available_at > latest_issue
            for column in source.select_dtypes(include="number"):
                if column != "area":
                    source.loc[future, column] *= 3
        modified_index = self.index.copy()
        modified_index.loc[modified_index.index + pd.Timedelta(days=10) > latest_issue] *= 2
        changed = retarget_dataset(PriceDataset.from_frames(*altered), modified_index)
        rerun, _ = run_sisalmoni(changed, {2: 2, 4: 2}, start="2025-W30", end="2025-W32", horizons=(2, 4))
        columns = ["origin_week", "h", "model", "y_hat", "n_train", "issue_date"]
        assert_frame_equal(rows[columns], rerun[columns])
        self.assertTrue(rows.groupby(["origin_week", "h"]).model.nunique().eq(4).all())
        for r in rows.itertuples():
            self.assertEqual(week_start(r.target_week), week_start(r.origin_week) + pd.Timedelta(weeks=r.h))
        metrics = summarize(rows)
        for item in metrics["scorecard"]:
            self.assertEqual(item["n"], 3)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "metrics.json"
            _write_json(path, metrics)
            exported = json.loads(path.read_text())
            self.assertEqual(len(exported["scorecard"]), 8)
            self.assertTrue(next(r for r in exported["comparisons"] if r["h"] == 4)["primary"])

    def test_target_gap_is_skipped_for_all_models_without_shortening_horizon(self):
        original = PriceDataset.from_frames(*self.inputs)
        index = self.index.drop(week_start("2025-W32"))
        rows, diagnostics = run_sisalmoni(retarget_dataset(original, index), {4: 2},
                                        start="2025-W30", end="2025-W33", horizons=(4,))
        self.assertNotIn("2025-W32", set(rows.target_week))
        self.assertEqual(diagnostics["skips"]["4"]["missing_actual"], 1)
        self.assertEqual(set(rows.target_week), {"2025-W30", "2025-W31", "2025-W33"})


if __name__ == "__main__":
    unittest.main()
