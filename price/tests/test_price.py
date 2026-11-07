from datetime import datetime
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal
import statsmodels.api as sm
from scipy.stats import norm
from statsmodels.stats.multitest import multipletests

from charts.price_charts import build_charts
from charts.theme import PALETTE
from price.anomalies import fallback_anomaly
from price.backtest import FREEZE, check_final_allowed, main, run_backtest
from price.calendar import iso_week, week_start
from price.dataset import PriceDataset, _asof, national_months
from price.evaluate import backtest_prices, clark_west, evaluate, paired
from price.io import write_json
from price.models import choose_lag, fit_predict, target
from price.tests.fixtures import dataset, frames


SHORT = {"dev": ["2021-W01", "2021-W08"], "holdout": ["2021-W09", "2021-W16"]}


class DatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs = frames()

    def test_iso_week_53_and_calendar_target_with_gap(self):
        self.assertEqual(iso_week(week_start("2020-W53") + pd.Timedelta(weeks=1)), "2021-W01")
        index = pd.to_datetime(["2020-12-21", "2021-01-04"])
        y = target(pd.DataFrame({"p": [1., 3.]}, index=index), 1)
        self.assertTrue(y.isna().all())

    def test_national_ratios_include_suppressed_area(self):
        source = self.inputs[2].iloc[:14].copy()
        source.loc[source.area == 0, "harvest_kg"] *= 4
        output = national_months(source).iloc[0]
        self.assertAlmostEqual(output.avg_kg, source.harvest_kg.sum() / source.harvest_count.sum())
        source.loc[source.area == 1, "harvest_kg"] = np.nan
        self.assertTrue(pd.isna(national_months(source).iloc[0].avg_kg))

    def test_missing_area_row_is_missing_national_total(self):
        source = self.inputs[2].iloc[:14].copy()
        source = source.loc[source.area != 7]
        self.assertTrue(pd.isna(national_months(source).iloc[0].avg_kg))

    def test_publication_date_filters_future_levels_and_full_sample_anomalies(self):
        inputs = [x.copy() for x in self.inputs]
        date = pd.Timestamp("2021-01-13")
        before = PriceDataset.from_frames(*inputs).snapshot(date)
        for frame in inputs:
            future = frame.available_at > date
            for column in frame.select_dtypes(include="number"):
                if column != "area":
                    frame.loc[future, column] *= 100
        inputs[3]["mobile_anom"] = 1e9
        inputs[3]["treat_anom"] = -1e9
        after = PriceDataset.from_frames(*inputs).snapshot(date)
        assert_frame_equal(before, after)

    def test_monthly_release_is_asof_each_own_origin(self):
        source = pd.DataFrame({"value": [1., 2., np.nan],
                               "available_at": pd.to_datetime(["2020-12-20", "2021-01-20", "2021-02-20"])},
                              index=pd.to_datetime(["2020-11-01", "2020-12-01", "2021-01-01"]))
        dates = pd.Series(pd.to_datetime(["2021-01-19", "2021-01-20", "2021-02-21"]))
        out = _asof(source, dates, ["value"])
        self.assertEqual(out.value.iloc[:2].tolist(), [1., 2.])
        self.assertTrue(pd.isna(out.value.iloc[2]))

    def test_weekly_missing_report_is_not_replaced_with_older_value(self):
        inputs = [x.copy() for x in self.inputs]
        # 2021-W01 origin is Jan 13; latest public BW week is 2020-W53.
        inputs[3].loc[inputs[3].week == "2020-W53", "mobile_idx"] = np.nan
        p = PriceDataset.from_frames(*inputs)
        row = p.snapshot("2021-01-13").loc[week_start("2021-W01")]
        self.assertTrue(pd.isna(row.mobile_anom))
        self.assertTrue(np.isfinite(row.mobile_anom_lag1))

    def test_lag_is_one_calendar_week_across_a_missing_week(self):
        inputs = [x.copy() for x in self.inputs]
        inputs[3] = inputs[3].loc[inputs[3].week != "2020-W52"]
        p = PriceDataset.from_frames(*inputs)
        row = p.snapshot("2021-01-13").loc[week_start("2021-W01")]
        self.assertTrue(np.isfinite(row.mobile_anom))
        self.assertTrue(pd.isna(row.mobile_anom_lag1))

    def test_all_null_disease_is_documented_and_dropped(self):
        inputs = [x.copy() for x in self.inputs]
        inputs[3]["disease_share"] = np.nan
        p = PriceDataset.from_frames(*inputs)
        self.assertNotIn("disease_share", p.drivers)
        self.assertTrue(any("disease_share dropped" in x for x in p.notes))

    def test_delayed_price_release_cannot_enter_a_past_origin(self):
        inputs = [x.copy() for x in self.inputs]
        inputs[0].loc[inputs[0].week == "2020-W53", "available_at"] = pd.Timestamp("2021-02-01")
        p = PriceDataset.from_frames(*inputs)
        s = p.snapshot("2021-03-01")
        row = s.loc[week_start("2021-W01")]
        self.assertTrue(pd.isna(row.dp_lag0))
        self.assertTrue(pd.isna(row.v_anom_lag1))

    def test_invalid_input_and_missing_files_have_clear_errors(self):
        inputs = [x.copy() for x in self.inputs]
        inputs[0].loc[0, "price_nok_kg"] = -2
        with self.assertRaisesRegex(ValueError, "positive"):
            PriceDataset.from_frames(*inputs)
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(FileNotFoundError, "Inputs have not landed"):
                PriceDataset.load(directory)

    def test_fallback_fit_does_not_use_future_values(self):
        s = pd.Series(np.exp(np.sin(np.arange(200) / 8)), index=pd.date_range("2017-01-02", periods=200, freq="W-MON"))
        before = fallback_anomaly(s, "W", fit_end=s.index[140])
        s.iloc[141:] *= 1000
        after = fallback_anomaly(s, "W", fit_end=s.index[140])
        np.testing.assert_allclose(before.iloc[:141], after.iloc[:141], equal_nan=True)


class BacktestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = dataset()
        cls.rows, cls.payload, cls.diagnostics = run_backtest(cls.data, final=True, horizons=[2, 4], windows=SHORT)

    def test_default_never_evaluates_holdout_targets(self):
        rows, payload, _ = run_backtest(self.data, horizons=[4], windows=SHORT)
        self.assertEqual(set(rows.window), {"dev"})
        self.assertIsNone(payload["f2"])
        self.assertIsNone(payload["backtest_h4"])
        for origin in rows.origin_week:
            self.assertLessEqual(week_start(origin) + pd.Timedelta(weeks=4), week_start(SHORT["dev"][1]))

    def test_training_targets_are_published_and_forecasts_share_rows(self):
        original = fit_predict
        data = self.data
        def checked(x, y, new):
            origin = new.index[0]
            targets = x.index + pd.Timedelta(weeks=4)
            self.assertTrue((targets <= origin).all())
            release = data.ssb.available_at.reindex(targets)
            self.assertTrue((release <= data.ssb.loc[origin, "available_at"]).all())
            return original(x, y, new)
        with patch("price.backtest.fit_predict", side_effect=checked):
            run_backtest(data, horizons=[4], windows=SHORT)
        counts = self.rows.groupby(["origin_week", "h"]).model.nunique()
        self.assertTrue((counts == 4).all())

    def test_missing_c1_origin_is_skipped_for_all_models(self):
        inputs = frames()
        inputs[3].loc[inputs[3].week == "2020-W52", "mobile_idx"] = np.nan
        p = PriceDataset.from_frames(*inputs)
        rows, _, diagnostics = run_backtest(p, horizons=[4], windows=SHORT)
        self.assertNotIn("2020-W53", set(rows.origin_week))
        self.assertGreater(diagnostics["skips"]["dev/h4"]["missing_features"], 0)

    def test_bic_is_fixed_before_2019(self):
        frame = self.data.snapshot("2024-01-10")
        before, detail = choose_lag(frame, 4)
        frame.loc[frame.index >= "2019-01-01", "p"] = 1e9
        after, changed = choose_lag(frame, 4)
        self.assertEqual(before, after)
        self.assertEqual(detail["bic"], changed["bic"])

    def test_clark_west_hac_and_holm_primary(self):
        pair = paired(self.rows, 4, "dev")
        stat, p = clark_west(pair, 4)
        if len(pair) < 5:
            self.assertIsNone(p)
        # Use enough synthetic matched observations for the exact HAC check.
        pair = pd.concat([pair] * 4, ignore_index=True)
        stat, p = clark_west(pair, 4)
        f = pair.error_c0 ** 2 - pair.error_c1 ** 2 + (pair.y_hat_c0 - pair.y_hat_c1) ** 2
        expected = sm.OLS(f, np.ones(len(f))).fit(cov_type="HAC", cov_kwds={"maxlags": 3})
        self.assertAlmostEqual(stat, expected.tvalues.iloc[0])
        self.assertAlmostEqual(p, norm.sf(expected.tvalues.iloc[0]))
        self.assertTrue(all(r["p_holm"] is None for r in self.payload["cw"] if r["h"] == 4))

    def test_backtest_price_bands_use_only_development_errors(self):
        rows = self.rows.copy()
        # More h4 holdout data is not needed to test conversion/quantiles.
        records = backtest_prices(rows, self.data.ssb, {"pass": False})
        self.assertTrue(records)
        changed = rows.copy()
        changed.loc[changed.window == "holdout", "error"] += 1e6
        self.assertEqual(records, backtest_prices(changed, self.data.ssb, {"pass": False}))
        r = records[0]
        self.assertEqual(r["band_model"], "c0")
        self.assertLess(r["p10"], r["p90"])
        self.assertAlmostEqual(r["actual"], self.data.ssb.loc[week_start(r["week"]), "price_nok_kg"])

    def test_final_time_and_once_guards_and_cli(self):
        with tempfile.TemporaryDirectory() as directory:
            before = datetime(2026, 11, 8, 3, 59, tzinfo=ZoneInfo("Europe/London"))
            with self.assertRaisesRegex(ValueError, "Holdout locked"):
                check_final_allowed(directory, before)
            check_final_allowed(directory, FREEZE)
            marker = Path(directory) / "price/final_run.json"
            marker.parent.mkdir()
            marker.write_text("{}")
            with self.assertRaisesRegex(ValueError, "already recorded"):
                check_final_allowed(directory, FREEZE)
            with self.assertRaisesRegex(ValueError, "Frozen final results"):
                main(["--output-root", directory])

    def test_strict_json_schema_and_altair_v5_specs(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / "price.json"
            write_json(p, self.payload)
            value = json.loads(p.read_text(), parse_constant=lambda x: self.fail(f"Invalid JSON {x}"))
            self.assertEqual(set(value), {"history", "c1_drivers", "windows", "notes", "scorecard", "cw", "by_year", "f2", "backtest_h4", "current"})
            for name, chart in build_charts(value).items():
                spec = json.loads(chart.to_json())
                self.assertIn("vega-lite/v5", spec["$schema"])
                self.assertNotIn('"url":', json.dumps(spec.get("data", {})))
            self.assertTrue({"rw", "ar", "c0", "c1", "stock", "market", "pipeline", "feed", "temperature", "losses", "lice", "count", "avg_kg", "actual"} <= PALETTE.keys())
            with patch("charts.price_charts.alt.__version__", "6.0.0"):
                with self.assertRaisesRegex(ValueError, "Altair 5"):
                    build_charts(value)

    def test_f2_requires_both_holdout_mae_and_unadjusted_p(self):
        rows = self.rows.copy()
        for window in ["dev", "holdout"]:
            mask = (rows.window == window) & (rows.h == 4)
            rows.loc[mask & (rows.model == "c0"), "error"] = 1.
            rows.loc[mask & (rows.model == "c1"), "error"] = .9
        with patch("price.evaluate.clark_west", return_value=(2., .02)):
            self.assertTrue(evaluate(rows, final=True)["f2"]["pass"])
        with patch("price.evaluate.clark_west", return_value=(1., .08)):
            self.assertFalse(evaluate(rows, final=True)["f2"]["pass"])
        rows.loc[(rows.window == "holdout") & (rows.h == 4) & (rows.model == "c1"), "error"] = .98
        with patch("price.evaluate.clark_west", return_value=(2., .02)):
            self.assertFalse(evaluate(rows, final=True)["f2"]["pass"])

    def test_rw_hit_rate_null_and_other_zero_calls_excluded(self):
        row = {"origin_week": "2021-W01", "h": 4, "window": "dev", "y": 1., "error": 1.}
        rows = pd.DataFrame([{**row, "model": "rw", "y_hat": 0.},
                             {**row, "model": "ar", "y_hat": 0.},
                             {**row, "model": "ar", "y_hat": 1., "error": 0.}])
        scores = {r["model"]: r for r in evaluate(rows)["scorecard"]}
        self.assertIsNone(scores["rw"]["hit_rate"])
        self.assertEqual(scores["ar"]["hit_rate"], 1.)

    def test_secondary_holm_family_contains_six_horizons_per_window(self):
        template = self.rows.loc[self.rows.h == 4]
        rows = pd.concat([template.assign(h=h) for h in range(2, 9)], ignore_index=True)
        pvalues = {2: .01, 3: .04, 4: .03, 5: .1, 6: .02, 7: .3, 8: .4}
        with patch("price.evaluate.clark_west", side_effect=lambda pair, h: (2., pvalues[h])):
            cw = evaluate(rows, final=True)["cw"]
        expected = multipletests([pvalues[h] for h in [2, 3, 5, 6, 7, 8]], method="holm")[1]
        for window in ["dev", "holdout"]:
            secondary = [r for r in cw if r["window"] == window and r["h"] != 4]
            np.testing.assert_allclose([r["p_holm"] for r in secondary], expected)

    def test_final_cli_publishes_once_using_only_synthetic_inputs(self):
        original_run = run_backtest
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "inputs"
            source.mkdir()
            for name, frame in zip(["ssb_weekly", "fx_daily", "directorate_area_month", "weekly_national_index"], frames(), strict=True):
                frame.to_parquet(source / (name + ".parquet"), index=False)
            output = root / "out"
            args = ["--input-dir", str(source), "--output-root", str(output), "--final"]
            with patch("price.backtest.check_final_allowed", side_effect=lambda p: check_final_allowed(p, FREEZE)), \
                 patch("price.backtest.run_backtest", side_effect=lambda ds, **kw: original_run(ds, horizons=[2, 4], windows=SHORT, **kw)):
                main(args)
                public = json.loads((output / "web/public/data/price.json").read_text())
                stored = pd.read_parquet(output / "data/processed/price_backtest.parquet")
                self.assertEqual(set(stored.window), {"dev", "holdout"})
                self.assertIsNotNone(public["f2"])
                self.assertTrue(public["backtest_h4"])
                self.assertTrue((output / "price/final_run.json").exists())
                before = (output / "web/public/data/price.json").read_bytes()
                with self.assertRaisesRegex(ValueError, "already recorded"):
                    main(args)
                self.assertEqual(before, (output / "web/public/data/price.json").read_bytes())


if __name__ == "__main__":
    unittest.main()
