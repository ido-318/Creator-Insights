import json
import subprocess
import sys
from pathlib import Path

from crewai.tools import tool

from modeling_tools import inspect_modeling_input


def run_training():
    """Validate the handoff, run training and return measured results."""
    project_dir = Path(__file__).resolve().parent
    artifacts = project_dir / "artifacts"

    # Mandatory check: invalid data must stop training
    handoff = inspect_modeling_input()

    summary_path = artifacts / "training_summary.json"
    previous_timestamp = (
        summary_path.stat().st_mtime_ns
        if summary_path.exists()
        else None
    )

    # Run the fixed training script with the active Python environment
    subprocess.run(
        [sys.executable, str(project_dir / "train_model.py")],
        cwd=project_dir,
        check=True,
    )

    # Do not silently return an old summary
    if not summary_path.is_file():
        raise FileNotFoundError("Training summary was not created.")

    if summary_path.stat().st_mtime_ns == previous_timestamp:
        raise RuntimeError("Training summary was not updated.")

    summary = json.loads(
        summary_path.read_text(encoding="utf-8")
    )

    # Confirm that the results refer to the expected modeling inputs
    if summary["features"] != handoff["features"]:
        raise ValueError("Training features differ from the contract.")

    if summary["target"] != handoff["target"]:
        raise ValueError("Training target differs from the contract.")

    required_outputs = [
        "features.csv",
        "model.joblib",
        "evaluation_report.md",
        "model_card.md",
    ]

    for filename in required_outputs:
        if not (artifacts / filename).is_file():
            raise FileNotFoundError(f"Missing output: {filename}")

    return summary


@tool("Train Content Models")
def train_content_models() -> str:
    """Validate inputs, train model variants and return evaluation metrics."""
    return json.dumps(run_training(), ensure_ascii=False)


if __name__ == "__main__":
    result = run_training()

    print("\nTraining tool completed.")
    print(json.dumps(result["test_results"], indent=2))