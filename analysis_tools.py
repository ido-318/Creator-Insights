import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
from crewai.tools import tool


def run_analysis():
    """Run the existing analysis script and return its results."""
    project_dir = Path(__file__).resolve().parent
    artifacts = project_dir / "artifacts"

    # Run the fixed analysis script with our active Python environment
    subprocess.run(
        [sys.executable, str(project_dir / "analyze_data.py")],
        cwd=project_dir,
        check=True,
    )

    summary = pd.read_csv(artifacts / "summary_by_type.csv")

    required_outputs = [
        "summary_by_type.csv",
        "interactions_by_type.png",
        "eda_report.html",
    ]

    for filename in required_outputs:
        if not (artifacts / filename).is_file():
            raise FileNotFoundError(f"Missing output: {filename}")

    return {
        "summary_by_type": summary.to_dict(orient="records"),
        "outputs": [
            str(artifacts / filename)
            for filename in required_outputs
        ],
        "limitations": [
            "Descriptive comparison, not proof of causation",
            "Historical data from one Facebook page",
            "Small samples require cautious interpretation",
        ],
    }


@tool("Analyze Facebook Content")
def analyze_facebook_content() -> str:
    """Generate the EDA report and chart, then return measured statistics."""
    return json.dumps(run_analysis(), ensure_ascii=False)


if __name__ == "__main__":
    print(
        json.dumps(
            run_analysis(),
            ensure_ascii=False,
            indent=2,
        )
    )