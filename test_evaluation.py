"""Validate reported results against isolated copies of the saved evidence."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest

import pandas as pd

from evaluation_tools import review_model_results


class EvaluationIntegrityTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.artifacts = Path(directory.name)
        source = Path(__file__).resolve().parent / "artifacts"
        for name in ("clean_data.csv", "training_summary.json",
                     "test_predictions.csv", "data_split.csv"):
            shutil.copy2(source / name, self.artifacts / name)

    def review(self):
        return review_model_results(self.artifacts, write_report=False)

    def change_csv(self, name, change):
        path = self.artifacts / name
        data = pd.read_csv(path)
        change(data).to_csv(path, index=False)

    def change_summary(self, change):
        path = self.artifacts / "training_summary.json"
        summary = json.loads(path.read_text())
        change(summary)
        path.write_text(json.dumps(summary))

    def test_valid_evidence_recalculates_metrics_without_writing(self):
        result = self.review()
        self.assertTrue(result["metrics_verified"])
        self.assertEqual(result["test_rows_checked"], 100)
        self.assertAlmostEqual(result["recalculated_baseline_mae"], 120.45)
        self.assertFalse(result["beats_baseline"])
        self.assertFalse((self.artifacts / "evaluation_check.json").exists())

    def test_changed_actual_outcomes_are_rejected(self):
        self.change_csv("test_predictions.csv", lambda df: df.assign(actual=df.actual + 1))
        with self.assertRaisesRegex(ValueError, "actual outcomes differ"):
            self.review()

    def test_changed_predictions_are_rejected(self):
        self.change_csv("test_predictions.csv", lambda df: df.assign(predicted=0))
        with self.assertRaisesRegex(ValueError, "Metric mismatch: selected_model_mae"):
            self.review()

    def test_missing_test_prediction_is_rejected(self):
        self.change_csv("test_predictions.csv", lambda df: df.iloc[1:])
        with self.assertRaisesRegex(ValueError, "Predictions do not match"):
            self.review()

    def test_duplicate_prediction_id_is_rejected(self):
        self.change_csv("test_predictions.csv", lambda df: pd.concat([df, df.iloc[:1]]))
        with self.assertRaisesRegex(ValueError, "Duplicate row identifiers"):
            self.review()

    def test_incomplete_split_is_rejected(self):
        self.change_csv("data_split.csv", lambda df: df.iloc[1:])
        with self.assertRaisesRegex(ValueError, "Split does not cover"):
            self.review()

    def test_unknown_split_label_is_rejected(self):
        self.change_csv("data_split.csv", lambda df: df.assign(split="validation"))
        with self.assertRaisesRegex(ValueError, "Unexpected split labels"):
            self.review()

    def test_incorrect_baseline_score_is_rejected(self):
        self.change_summary(lambda d: d["test_results"].update(baseline_mae=0))
        with self.assertRaisesRegex(ValueError, "Metric mismatch: baseline_mae"):
            self.review()

    def test_false_claim_of_beating_baseline_is_rejected(self):
        self.change_summary(lambda d: d["test_results"].update(selected_model_beats_baseline=True))
        with self.assertRaisesRegex(ValueError, "Incorrect baseline comparison"):
            self.review()


if __name__ == "__main__":
    unittest.main()
