"""Regression and chronology checks for the complete SISMAPISCIS growth replay."""
from __future__ import annotations

import json
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import run


class TestReproduction(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows, cls.scores, cls.bio = run.run_analysis()
        cls.curated = json.loads((ROOT / "cohort.json").read_text())

    def test_no_missing_or_extra_evaluation_dates(self):
        self.assertEqual([r["date"] for r in self.rows],
                         ["2026-08-07","2026-09-13","2026-09-26","2026-10-16"])

    def test_training_prefixes_are_past_only(self):
        self.assertEqual([r["n_training_intervals"] for r in self.rows],[2,3,4,5])
        self.assertTrue(all(r["training_last_target"] == r["anchor"]
                            and r["training_last_target"] < r["date"] for r in self.rows))

    def test_original_ml_model_invocations_replay(self):
        self.assertAlmostEqual(self.scores["ridge"]["MAE_g"],8.514416272869841,places=4)
        self.assertAlmostEqual(self.scores["gaussian"]["MAE_g"],12.197983814209017,places=4)

    def test_mechanistic_values_and_metrics(self):
        self.assertAlmostEqual(self.scores["tgc"]["MAE_g"],42.254999,delta=.002)
        self.assertAlmostEqual(self.scores["vbgf"]["MAE_g"],17.492921,delta=.002)
        self.assertAlmostEqual(self.rows[-1]["tgc_g"],177.071305,places=3)
        self.assertAlmostEqual(self.rows[-1]["vbgf_g"],155.048257,places=3)

    def test_last_observed_and_models(self):
        self.assertAlmostEqual(self.rows[-1]["weight_observed_g"],150.53,places=2)
        self.assertAlmostEqual(self.rows[-1]["ridge_g"],143.222228,places=3)
        self.assertAlmostEqual(self.rows[-1]["gaussian_g"],149.282643,places=3)

    def test_all_reference_intervals_have_eligible_data(self):
        for row in self.curated["intervals"]:
            self.assertTrue(row["quality"]["eligible"])
            for key in ("temperature","oxygen","ph"):
                self.assertGreaterEqual(row["quality"]["coverage"][key],run.MIN_COVERAGE)

    def test_no_observed_label_leak_into_mechanistic_coefficient(self):
        original=json.loads((ROOT/"cohort.json").read_text())
        rows=original["intervals"]
        base=run.calculate_references(rows,original["biometries"])
        # Change ONLY the last, reserved label. Calibration cannot change.
        modified=json.loads(json.dumps(original))
        modified["biometries"][-1]["mean_g"] += 15
        modified["intervals"][-1]["actual_weight_g"] += 15
        modified["intervals"][-1]["observed_gain_g"] += 15
        alt=run.calculate_references(modified["intervals"], modified["biometries"])
        self.assertEqual(len(base),len(alt))
        for a,b in zip(base,alt):
            self.assertEqual(a["tgc_weight_g"],b["tgc_weight_g"])
            self.assertEqual(a["vbgf_weight_g"],b["vbgf_weight_g"])

    def test_model_comparison_cannot_mix_date_axes(self):
        altered=json.loads((ROOT/"cohort.json").read_text())
        altered["intervals"][-1]["anchor"] = "2026-10-01"
        with self.assertRaises(ValueError):
            run.calculate_references(altered["intervals"],altered["biometries"])


if __name__=="__main__":
    unittest.main(verbosity=2)
