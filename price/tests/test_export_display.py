from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import pandas as pd

from price.export_display import DATASET_ID, DATA_FILE, MANIFEST_FILE, build_payload, export, read_json


EXPERIMENT = Path(__file__).resolve().parents[1] / "experiments/sisalmoni_v2"


class DisplayHandoffTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.selection = read_json(EXPERIMENT / "selection.json")
        cls.final = read_json(EXPERIMENT / "final_metrics.json")
        cls.decision = read_json(EXPERIMENT / "decision.json")
        cls.intervals = read_json(EXPERIMENT / "paired_uncertainty.json")
        cls.predictions = pd.read_parquet(EXPERIMENT / "final_predictions.parquet")

    def payload(self, final=None, decision=None):
        return build_payload(self.selection, final or self.final, decision or self.decision,
                             self.intervals, self.predictions)

    def test_display_uses_frozen_candidate_and_keeps_live_recommendation_distinct(self):
        payload = self.payload()
        self.assertEqual(payload["display_model"]["id"], "ridge_level_a10")
        # The lower test MAE of alpha 100 must not replace the development choice.
        self.assertNotEqual(payload["display_model"]["id"], "ridge_level_a100")
        self.assertEqual(payload["recommendation"]["recommended_live_model_id"], "rw")
        self.assertEqual(payload["target"]["unit"], "EUR/kg")
        self.assertAlmostEqual(payload["headline"]["mae_eur_per_kg"], .29203129148658474)
        self.assertAlmostEqual(payload["headline"]["improvement_vs_no_change_pct"], 33.566341273194)
        self.assertEqual(payload["headline"]["direction_correct"], 19)
        self.assertEqual(payload["headline"]["direction_calls"], 24)
        self.assertFalse(payload["evaluation"]["fresh_independent_holdout"])
        self.assertFalse(payload["headline"]["direction_is_overall_price_accuracy"])
        self.assertIn("include no benefit", payload["uncertainty"]["must_display"])

    def test_mixed_period_or_incomplete_comparison_is_rejected(self):
        final = deepcopy(self.final)
        final["dates"]["final_start"] = "2025-W01"
        with self.assertRaisesRegex(ValueError, "Mixed evaluation dates"):
            self.payload(final=final)
        final = deepcopy(self.final)
        row = next(r for r in final["scores"] if r["h"] == 4 and r["model"] == "rw")
        row["n"] = 23
        with self.assertRaisesRegex(ValueError, "same complete 24-week"):
            self.payload(final=final)
        decision = deepcopy(self.decision)
        decision["selected_challenger"] = "ridge_level_a100"
        with self.assertRaisesRegex(ValueError, "frozen development selection"):
            self.payload(decision=decision)

    def test_export_is_deterministic_and_does_not_replace_the_ssb_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            public = Path(directory)
            (public / "data").mkdir()
            legacy = public / "data/price.json"
            legacy.write_text('{"legacy_target":"SSB NOK/kg"}\n')
            before = legacy.read_bytes()
            export(EXPERIMENT, public)
            files = list(public.rglob("*.json"))
            first = {p.relative_to(public): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
            export(EXPERIMENT, public)
            self.assertEqual(first, {p.relative_to(public): hashlib.sha256(p.read_bytes()).hexdigest() for p in files})
            self.assertEqual(legacy.read_bytes(), before)
            manifest = read_json(public / "data" / MANIFEST_FILE)
            self.assertEqual(manifest["use_for_price_results"], f"data/{DATA_FILE}")
            payload = read_json(public / "data" / DATA_FILE)
            self.assertEqual(payload["dataset_id"], DATASET_ID)
            self.assertEqual(len(payload["backtest_h4"]), 24)
            self.assertNotIn(str(EXPERIMENT.resolve().parents[3]), json.dumps(payload))
            for path in manifest["charts"].values():
                chart = read_json(public / path)
                self.assertEqual(chart["usermeta"]["dataset_id"], DATASET_ID)
                self.assertEqual(chart["usermeta"]["unit"], "EUR/kg")


if __name__ == "__main__":
    unittest.main()
