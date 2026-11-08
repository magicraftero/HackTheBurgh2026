from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from price.calendar import iso_week, week_start
from price.sisalmoni_v2 import (
    ALL_FEATURES, BASELINES, HORIZONS, MODEL_IDS, RULES, SPECS,
    add_adaptive_policy, ensure_final_allowed, evaluate_cases, evaluation_dates,
    file_hashes, freeze_selection, main, metrics, select_models, validate_hashes, write_json,
)


def prediction_rows(errors, count=12):
    records = []
    for i, t in enumerate(pd.date_range("2025-01-06", periods=count, freq="W-MON")):
        T = t + pd.Timedelta(weeks=4)
        for model, error in errors.items():
            records.append({"h": 4, "model": model, "origin_week": iso_week(t), "target_week": iso_week(T),
                            "issue_date": (t + pd.Timedelta(days=10)).date().isoformat(),
                            "target_available_at": (T + pd.Timedelta(days=10)).date().isoformat(),
                            "origin_price": 5.0, "actual_eur_kg": 6.0, "pred_eur_kg": 6.0 + error,
                            "n_train": 30 + i, "failed": False, "reason": "", "split": "development"})
    return pd.DataFrame(records)


class SelectionTests(unittest.TestCase):
    def test_global_embargo_precedes_every_final_forecast(self):
        index = pd.Series(1.0, index=pd.date_range(week_start("2024-W32"), periods=117, freq="W-MON"))
        dates = evaluation_dates(index)
        self.assertEqual(dates["final_start"], "2026-W21")
        self.assertEqual(dates["final_end"], "2026-W44")
        self.assertEqual(dates["dev_end"], "2026-W20")
        self.assertEqual(dates["selection_cutoff"], "2026-W13")
        self.assertEqual(dates["selection_issue_date"], "2026-04-02")
        cutoff_release = week_start(dates["selection_cutoff"]) + pd.Timedelta(days=10)
        for h in HORIZONS:
            first_final_issue = week_start(dates["final_start"]) - pd.Timedelta(weeks=h) + pd.Timedelta(days=10)
            self.assertLessEqual(cutoff_release, first_final_issue)

    def test_feature_group_requires_matched_development_contribution(self):
        errors = {name: 1.2 for name in MODEL_IDS}
        errors.update(rw=1.0, ar1=.9, ridge_log_a100=.8, ridge_fx=.79,
                      ridge_exports=.77, ridge_biology=.85, blend=.82)
        selected = select_models(prediction_rows(errors))
        self.assertFalse(selected["feature_group_eligible"]["ridge_fx"])
        self.assertTrue(selected["feature_group_eligible"]["ridge_exports"])
        self.assertEqual(selected["selected_challenger"], "ridge_exports")
        self.assertEqual(selected["strongest_baseline"], "ar1")
        self.assertEqual(selected["selected_policy"], "ridge_exports")
        rows = prediction_rows(errors)
        rows.loc[rows.model == "ridge_exports", "failed"] = True
        self.assertNotEqual(select_models(rows)["selected_challenger"], "ridge_exports")

    def test_adaptive_selection_cannot_see_unreleased_validation_outcomes(self):
        errors = {name: 1.2 for name in MODEL_IDS}
        errors.update(rw=.7, ridge_log_a100=.4, blend=.5)
        rows = prediction_rows(errors, count=18)
        chosen_origin = sorted(rows.origin_week.unique())[14]
        issue = pd.Timestamp(rows.loc[rows.origin_week == chosen_origin, "issue_date"].iloc[0])
        before = add_adaptive_policy(rows)
        changed = rows.copy()
        future = pd.to_datetime(changed.target_available_at) > issue
        changed.loc[future, "actual_eur_kg"] = 10000.0
        after = add_adaptive_policy(changed)
        selected_before = before.loc[(before.model == "adaptive_policy") & (before.origin_week == chosen_origin)].iloc[0]
        selected_after = after.loc[(after.model == "adaptive_policy") & (after.origin_week == chosen_origin)].iloc[0]
        self.assertGreaterEqual(selected_before.selection_released_count, 8)
        self.assertEqual(selected_before.selected_model, selected_after.selected_model)
        self.assertEqual(selected_before.pred_eur_kg, selected_after.pred_eur_kg)


class EvaluationTests(unittest.TestCase):
    def test_failure_and_missing_forecasts_reduce_coverage_without_error_dropping(self):
        rows = prediction_rows({"ridge_level_a10": .2}, count=2)
        rows.loc[0, "pred_eur_kg"] = -1.0
        rows.loc[0, "failed"] = True
        score = metrics(rows, {4: 3})[0]
        self.assertEqual(score["n"], 2)
        self.assertEqual(score["n_failed"], 2)
        self.assertAlmostEqual(score["coverage"], 1 / 3)
        self.assertIsNone(score["mae_eur_kg"])
        self.assertAlmostEqual(score["raw_finite_mae_eur_kg"], 3.6)

    def test_all_models_keep_the_same_forecast_case_when_one_model_fails(self):
        T = week_start("2026-W10")
        cases, old = {}, []
        for h in HORIZONS:
            t = T - pd.Timedelta(weeks=h)
            issue = t + pd.Timedelta(days=10)
            row = {name: 1.0 for name in ALL_FEATURES}
            row.update(origin_price=5.0, actual_price=6.0, target_date=T,
                       target_available_at=T + pd.Timedelta(days=10), issue_date=issue,
                       target_log_change=np.log(6 / 5))
            cases[h] = pd.DataFrame([row], index=[t])
            for model in ["ar", "c0", "c1"]:
                old.append(dict(origin_week=iso_week(t), h=h, model=model,
                                actual_eur_kg=6.0, pred_eur_kg=5.5, issue_date=issue,
                                n_train=35))
        legacy = pd.DataFrame(old).set_index(["origin_week", "h", "model"])
        dates = {"index_start": iso_week(T), "selection_cutoff": iso_week(T),
                 "selection_issue_date": "2026-12-01"}
        def predict(spec, train, current):
            if spec["id"] == "ridge_fx":
                raise ValueError("synthetic numerical failure")
            return 5.5, {}
        with patch("price.sisalmoni_v2.training_rows", return_value=pd.DataFrame(index=range(30))), \
             patch("price.sisalmoni_v2.predict_spec", side_effect=predict):
            rows, counts = evaluate_cases(cases, legacy, dates, split="development")
        self.assertEqual(len(rows), 13 * 7)
        self.assertTrue(rows.groupby(["origin_week", "h"]).model.nunique().eq(13).all())
        self.assertTrue(rows.loc[rows.model == "ridge_fx", "failed"].all())
        self.assertTrue(all(c["eligible"] == 1 for c in counts.values()))
        self.assertTrue(all(s["coverage"] == 0 for s in metrics(rows) if s["model"] == "ridge_fx"))


class FreezeTests(unittest.TestCase):
    def test_final_rejects_alternate_input_paths_before_loading_even_with_identical_data(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            out = root / "out"
            raw_a, raw_b = root / "raw_a", root / "raw_b"
            input_a, input_b = root / "input_a", root / "input_b"
            for path in [raw_a, raw_b, input_a, input_b]:
                path.mkdir()
            payload = {"year": 2026, "months": [{"month": 5, "weeks": [{"week": 21, "fpiEUR": 6.5}]}]}
            for path in [raw_a, raw_b]:
                (path / "2026.json").write_text(json.dumps(payload))
            for path in [input_a, input_b]:
                (path / "inputs.bin").write_bytes(b"identical synthetic inputs")
            legacy_a, legacy_b = root / "legacy_a.bin", root / "legacy_b.bin"
            for path in [legacy_a, legacy_b]:
                path.write_bytes(b"identical synthetic benchmarks")

            def manifest(raw_files, input_dir, legacy_path, output_dir):
                return {"inputs": file_hashes([*raw_files, Path(input_dir) / "inputs.bin", legacy_path]), "code": {}}

            selection = {"candidate_specs": SPECS, "rules": RULES,
                         "hashes": manifest(list(raw_a.glob("*.json")), input_a, legacy_a, out)}
            freeze_selection(out, selection)
            variants = [(raw_b, input_a, legacy_a), (raw_a, input_b, legacy_a), (raw_a, input_a, legacy_b)]
            for raw, inputs, legacy in variants:
                with self.subTest(raw=raw, inputs=inputs, legacy=legacy), \
                     patch("price.sisalmoni_v2.hash_manifest", side_effect=manifest), \
                     patch("price.sisalmoni_v2.load_experiment") as load:
                    with self.assertRaisesRegex(ValueError, "Requested final input paths or contents"):
                        main(["final", "--raw-dir", str(raw), "--input-dir", str(inputs),
                              "--legacy-predictions", str(legacy), "--output-dir", str(out)])
                    load.assert_not_called()
            self.assertFalse((out / "final_predictions.parquet").exists())

    def test_staged_cli_freezes_development_before_writing_full_final_coverage(self):
        dates_index = pd.date_range(week_start("2024-W32"), periods=117, freq="W-MON")
        index = pd.Series(6 + .01 * np.arange(117), index=dates_index)
        dates = evaluation_dates(index)
        cases, legacy_records = {}, []
        for h in HORIZONS:
            records = []
            for t, price in index.items():
                T = t + pd.Timedelta(weeks=h)
                actual = float(index.get(T, np.nan))
                issue = t + pd.Timedelta(days=10)
                row = {name: 1.0 for name in ALL_FEATURES}
                row.update(origin_price=price, actual_price=actual, issue_date=issue,
                           target_date=T, target_available_at=T + pd.Timedelta(days=10),
                           target_log_change=np.log(actual / price))
                records.append(row)
                for model in ["ar", "c0", "c1"]:
                    legacy_records.append({"origin_week": iso_week(t), "h": h, "model": model,
                                           "actual_eur_kg": actual, "pred_eur_kg": price + .05,
                                           "issue_date": issue, "n_train": 35})
            cases[h] = pd.DataFrame(records, index=dates_index)
        legacy = pd.DataFrame(legacy_records).set_index(["origin_week", "h", "model"])
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            sentinel = out / "input.txt"
            sentinel.write_text("synthetic input")
            manifest = {"inputs": file_hashes([sentinel]), "code": {}}
            args = ["--output-dir", str(out)]
            with patch("price.sisalmoni_v2.load_experiment", return_value=(index, cases, legacy, dates, [])), \
                 patch("price.sisalmoni_v2.hash_manifest", return_value=manifest), \
                 patch("price.sisalmoni_v2.predict_spec", side_effect=lambda spec, train, current: (current.origin_price, {})):
                self.assertEqual(main(["develop", *args]), 0)
                self.assertTrue((out / "selection.json").exists())
                self.assertFalse((out / "final_predictions.parquet").exists())
                frozen = (out / "selection.json").read_bytes()
                self.assertEqual(main(["final", *args]), 0)
                final = pd.read_parquet(out / "final_predictions.parquet")
                self.assertTrue(final.groupby(["model", "h"]).size().eq(24).all())
                self.assertEqual((out / "selection.json").read_bytes(), frozen)
                with self.assertRaisesRegex(ValueError, "already completed"):
                    main(["final", *args])

    def test_final_requires_written_freeze_and_refuses_changed_inputs_or_repeated_run(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            source = out / "input.txt"
            source.write_text("frozen")
            selection = {"hashes": {"inputs": file_hashes([source]), "code": {}},
                         "candidate_specs": SPECS, "rules": RULES}
            with self.assertRaisesRegex(ValueError, "written selection"):
                ensure_final_allowed(out, selection)
            freeze_selection(out, selection)
            ensure_final_allowed(out, selection)
            original_freeze = (out / "selection.json").read_bytes()
            changed = deepcopy(selection)
            changed["candidate_specs"] = []
            write_json(out / "selection.json", changed)
            with self.assertRaisesRegex(ValueError, "Frozen selection changed"):
                ensure_final_allowed(out, changed)
            (out / "selection.json").write_bytes(original_freeze)
            source.write_text("changed")
            with self.assertRaisesRegex(ValueError, "changed"):
                ensure_final_allowed(out, selection)
            source.write_text("frozen")
            (out / "final_metrics.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "already completed"):
                ensure_final_allowed(out, selection)

    def test_strict_json_keeps_numpy_metrics_without_rounding(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "metrics.json"
            write_json(path, {"primary": np.bool_(True), "n": np.int64(24), "mae": np.float64(.1234567890123)})
            loaded = json.loads(path.read_text())
            self.assertTrue(loaded["primary"])
            self.assertEqual(loaded["n"], 24)
            self.assertEqual(loaded["mae"], .1234567890123)


if __name__ == "__main__":
    unittest.main()
