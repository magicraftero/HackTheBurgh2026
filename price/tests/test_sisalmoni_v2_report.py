import unittest

import numpy as np
import pandas as pd

from price.sisalmoni_v2_report import independent_scores, paired_blocks


class PairedUncertaintyTests(unittest.TestCase):
    def test_constant_paired_benefit_is_preserved_by_block_resampling(self):
        actual = np.full(24, 6.0)
        baseline = actual + np.tile([1., 2., 3., 2.], 6)
        candidate = baseline - .5
        result = paired_blocks(actual, candidate, baseline, block_length=4, repetitions=1000)
        np.testing.assert_allclose(result["difference_ci95"], [-.5, -.5])
        self.assertAlmostEqual(result["mean_error_difference_eur_kg"], -.5)
        self.assertEqual(result, paired_blocks(actual, candidate, baseline, block_length=4, repetitions=1000))

    def test_failed_forecast_does_not_produce_an_improved_subset_score(self):
        dates = pd.to_datetime(["2026-05-18", "2026-05-25"])
        index = pd.Series([6., 6.], index=dates - pd.Timedelta(weeks=4))
        rows = pd.DataFrame({"h": [4, 4], "model": ["candidate"] * 2,
                             "origin_week": ["2026-W17", "2026-W18"],
                             "target_week": ["2026-W21", "2026-W22"],
                             "actual_eur_kg": [6., 6.], "pred_eur_kg": [6., -100.],
                             "failed": [False, True]})
        score = independent_scores(rows, index, {4: 2}).iloc[0]
        self.assertTrue(pd.isna(score.mae_eur_kg))
        self.assertEqual(score.raw_finite_mae_eur_kg, 53.)
        self.assertEqual(score.coverage, .5)


if __name__ == "__main__":
    unittest.main()
