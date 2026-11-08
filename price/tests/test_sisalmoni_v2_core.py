"""Synthetic checks for v2 publication, horizon and preprocessing invariants."""

import unittest
from types import SimpleNamespace

import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal

from price.calendar import week_start
from price.dataset import PriceDataset
from price.sisalmoni import retarget_dataset
from price.sisalmoni_v2_core import (ALL_FEATURES, PRICE_FEATURES, build_cases,
                                    fit_scaled_ridge, predict_ridge, predict_spec, training_rows)
from price.tests.fixtures import frames


class CaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs = frames()
        cls.index = pd.Series(
            np.exp(1.8 + .06 * np.sin(np.arange(90) / 3)),
            index=pd.date_range(week_start("2024-W32"), periods=90, freq="W-MON"))

    def test_future_releases_cannot_change_an_earlier_feature_row(self):
        origin = week_start("2025-W20")
        original = PriceDataset.from_frames(*self.inputs)
        base = retarget_dataset(original, self.index)
        # Limit which origins the test constructs without deleting history seen
        # by the real snapshot. Both the lags and exogenous features stay real.
        def one_origin(dataset):
            carrier = dataset.ssb.copy()
            carrier.loc[carrier.index != origin, "price_nok_kg"] = np.nan
            return SimpleNamespace(ssb=carrier, snapshot=dataset.snapshot)

        before = build_cases(one_origin(base), horizons=(4,))[4]
        cutoff = origin + pd.Timedelta(days=10)
        changed_inputs = [f.copy() for f in self.inputs]
        for source in changed_inputs:
            future = source.available_at > cutoff
            for column in source.select_dtypes(include="number"):
                if column != "area":
                    source.loc[future, column] *= 10
        changed_index = self.index.copy()
        changed_index.loc[changed_index.index + pd.Timedelta(days=10) > cutoff] *= 4
        changed = retarget_dataset(PriceDataset.from_frames(*changed_inputs), changed_index)
        after = build_cases(one_origin(changed), horizons=(4,))[4]
        # Actual targets are labels and may change; neither features nor origin dates may.
        columns = [*ALL_FEATURES, "origin_price", "issue_date", "target_date"]
        self.assertTrue(np.isfinite(before.loc[origin, list(PRICE_FEATURES)].to_numpy(float)).all())
        assert_frame_equal(before[columns], after[columns])

    def test_week_53_and_a_gap_do_not_shorten_the_target_horizon(self):
        class TinyDataset:
            def __init__(self):
                dates = pd.date_range("2020-11-23", "2021-02-08", freq="W-MON")
                self.ssb = pd.DataFrame({"price_nok_kg": np.arange(len(dates)) + 5.0,
                                         "available_at": dates + pd.Timedelta(days=10)}, index=dates)
                self.ssb.loc["2021-01-04", "price_nok_kg"] = np.nan

            def snapshot(self, issue):
                f = self.ssb.loc[self.ssb.available_at <= issue].copy()
                f["p"] = np.log(f.price_nok_kg)
                return f

        cases = build_cases(TinyDataset(), horizons=(2,))[2]
        self.assertEqual(cases.loc["2020-12-28", "target_date"], pd.Timestamp("2021-01-11"))
        self.assertTrue(np.isnan(cases.loc["2020-12-21", "actual_price"]))
        # Four-calendar-week features must not skip the missing week either.
        self.assertTrue(np.isnan(cases.loc["2021-01-11", "momentum_4"]))
        self.assertTrue(np.isnan(cases.loc["2021-01-11", "volatility_4"]))

    def test_training_rejects_a_label_published_after_the_current_issue(self):
        dates = pd.date_range("2025-01-06", periods=8, freq="W-MON")
        table = pd.DataFrame(1.0, index=dates, columns=ALL_FEATURES)
        table["target_date"] = dates + pd.Timedelta(weeks=2)
        table["target_available_at"] = table.target_date + pd.Timedelta(days=10)
        table["issue_date"] = dates + pd.Timedelta(days=10)
        table["actual_price"] = 6.0
        table["target_log_change"] = .02
        current = dates[-1]
        delayed = dates[2]
        table.loc[delayed, "target_available_at"] = current + pd.Timedelta(days=11)
        selected = training_rows(table, current)
        self.assertNotIn(delayed, selected.index)
        self.assertTrue((selected.target_date <= current).all())
        self.assertTrue((selected.target_available_at <= table.loc[current, "issue_date"]).all())


class RidgeTests(unittest.TestCase):
    def test_scaler_is_fitted_only_on_training_and_is_not_changed_by_prediction(self):
        x = pd.DataFrame({"a": [1., 2., 3., 4.], "b": [10., 20., 30., 40.]})
        y = np.array([5., 6., 7., 8.])
        state = fit_scaled_ridge(x, y, 10)
        before = {key: state[key].copy() for key in ("mean", "scale", "coef")}
        predict_ridge(state, pd.DataFrame({"a": [1e9], "b": [-1e9]}))
        np.testing.assert_allclose(state["mean"], x.mean())
        for key, value in before.items():
            np.testing.assert_array_equal(state[key], value)
        # A test row accidentally included in preprocessing would materially alter this.
        contaminated = fit_scaled_ridge(pd.concat([x, pd.DataFrame({"a": [1e9], "b": [-1e9]})]),
                                        np.r_[y, 9.], 10)
        self.assertGreater(abs(contaminated["mean"][0] - state["mean"][0]), 1e7)

    def test_ridge_remains_finite_with_constant_and_collinear_predictors(self):
        a = np.linspace(-1, 1, 30)
        x = np.column_stack([np.ones(30), a, a, 1e9 * a])
        state = fit_scaled_ridge(x, 6 + a, 100)
        predictions = predict_ridge(state, x)
        self.assertTrue(np.isfinite(predictions).all())
        self.assertEqual(state["scale"][0], 1.0)
        self.assertLess(state["condition"], 3)
        np.testing.assert_allclose(predictions.mean(), 6., atol=1e-12)

    def test_level_and_log_change_targets_have_explicit_eur_predictions(self):
        n = 30
        train = pd.DataFrame({c: np.zeros(n) for c in PRICE_FEATURES})
        train["price"] = 6.0
        train["actual_price"] = 7.0
        train["target_log_change"] = np.log(7.0 / 6.0)
        current = train.iloc[-1].copy()
        current["origin_price"] = 6.0
        for representation in ["level", "log_change"]:
            spec = {"kind": "ridge", "representation": representation, "alpha": 100, "groups": []}
            predicted, diagnostics = predict_spec(spec, train, current)
            self.assertAlmostEqual(predicted, 7.0)
            self.assertTrue(diagnostics["positive_price"])
        blend, _ = predict_spec({"kind": "blend"}, train, current)
        self.assertAlmostEqual(blend, 6.5)


if __name__ == "__main__":
    unittest.main()
