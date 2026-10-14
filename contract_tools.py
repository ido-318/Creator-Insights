import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
from crewai.tools import tool

from validate_data import validate_data


def publish_contract():
    """Create the defined contract and check the cleaned data against it."""
    project_dir = Path(__file__).resolve().parent
    artifacts = project_dir / "artifacts"

    # Generate the contract using the rules we already defined
    subprocess.run(
        [sys.executable, str(project_dir / "create_contract.py")],
        cwd=project_dir,
        check=True,
    )

    contract_path = artifacts / "dataset_contract.json"
    contract = json.loads(
        contract_path.read_text(encoding="utf-8")
    )

    df = pd.read_csv(artifacts / "clean_data.csv")

    errors = validate_data(df, contract)

    if errors:
        raise ValueError(
            "Contract validation failed:\n"
            + "\n".join(errors)
        )

    return {
        "validation_passed": True,
        "checked_rows": len(df),
        "contract_path": str(contract_path),
        "contract": contract,
    }


@tool("Publish Dataset Contract")
def publish_dataset_contract() -> str:
    """Create the dataset contract and fail if cleaned data violates it."""
    return json.dumps(publish_contract(), ensure_ascii=False)


if __name__ == "__main__":
    result = publish_contract()

    print("Validation passed:", result["validation_passed"])
    print("Checked rows:", result["checked_rows"])
    print("Contract saved to:", result["contract_path"])