import json
import math
from pathlib import Path

import pandas as pd
from crewai.tools import tool
from sklearn.metrics import mean_absolute_error


def review_model_results(artifacts=None, *, write_report=True):
    """Recalculate test metrics and compare them with the saved summary."""
    artifacts = Path(artifacts) if artifacts is not None else Path(__file__).resolve().parent / "artifacts"

    summary = json.loads(
        (artifacts / "training_summary.json").read_text(
            encoding="utf-8"
        )
    )

    predictions = pd.read_csv(
        artifacts / "test_predictions.csv",
        index_col="row_id",
    )

    split = pd.read_csv(
        artifacts / "data_split.csv",
        index_col="row_id",
    )

    clean_data = pd.read_csv(artifacts / "clean_data.csv")

    # Check row identifiers and split labels
    if not split.index.is_unique or not predictions.index.is_unique:
        raise ValueError("Duplicate row identifiers found.")

    if set(split.index) != set(clean_data.index):
        raise ValueError("Split does not cover the cleaned dataset.")

    if not split["split"].isin(["train", "test"]).all():
        raise ValueError("Unexpected split labels.")

    train_ids = split.index[split["split"] == "train"]
    test_ids = split.index[split["split"] == "test"]

    if (
        len(train_ids) != summary["training_rows"]
        or len(test_ids) != summary["test_rows"]
    ):
        raise ValueError("Split sizes differ from the training summary.")

    if set(predictions.index) != set(test_ids):
        raise ValueError("Predictions do not match the test rows.")

    # Verify the actual outcomes against the cleaned dataset
    target = summary["target"]
    expected_actual = clean_data.loc[predictions.index, target]

    if not (
        expected_actual.to_numpy()
        == predictions["actual"].to_numpy()
    ).all():
        raise ValueError("Saved actual outcomes differ from the data.")

    # Recalculate the selected model's error
    model_mae = mean_absolute_error(
        predictions["actual"],
        predictions["predicted"],
    )

    # Rebuild the baseline using only the training outcomes
    training_median = clean_data.loc[train_ids, target].median()

    baseline_mae = mean_absolute_error(
        predictions["actual"],
        [training_median] * len(predictions),
    )

    recorded = summary["test_results"]

    for name, calculated in [
        ("selected_model_mae", model_mae),
        ("baseline_mae", baseline_mae),
    ]:
        if not math.isclose(
            calculated,
            recorded[name],
            rel_tol=1e-9,
            abs_tol=1e-6,
        ):
            raise ValueError(f"Metric mismatch: {name}")

    beats_baseline = bool(model_mae < baseline_mae)

    if recorded["selected_model_beats_baseline"] != beats_baseline:
        raise ValueError("Incorrect baseline comparison in summary.")

    review = {
        "metrics_verified": True,
        "test_rows_checked": len(predictions),
        "selected_model": summary["selected_model"],
        "recalculated_model_mae": float(model_mae),
        "recalculated_baseline_mae": float(baseline_mae),
        "beats_baseline": beats_baseline,
        "limitations": summary["limitations"],
    }

    if write_report:
        (artifacts / "evaluation_check.json").write_text(
            json.dumps(review, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    return review


@tool("Review Model Results")
def review_model_results_tool() -> str:
    """Verify saved test predictions, metrics and baseline comparison."""
    return json.dumps(review_model_results(), ensure_ascii=False)


if __name__ == "__main__":
    print(
        json.dumps(
            review_model_results(),
            ensure_ascii=False,
            indent=2,
        )
    )
