import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
from crewai.tools import tool

from validate_data import validate_data
from handoff_integrity import seal_handoff


def publish_contract():
    """Create the contract, validate the data and seal the handoff."""
    project_dir = Path(__file__).resolve().parent
    artifacts = project_dir / "artifacts"

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

    # Record fingerprints only after validation succeeds
    seal_handoff(artifacts)

    return {
        "validation_passed": True,
        "checked_rows": len(df),
        "contract_path": str(contract_path),
        "manifest_path": str(artifacts / "handoff_manifest.json"),
        "contract": contract,
    }


@tool("Publish Dataset Contract")
def publish_dataset_contract() -> str:
    """Create and validate the contract, then seal the handoff files."""
    return json.dumps(
        publish_contract(),
        ensure_ascii=False,
    )


if __name__ == "__main__":
    result = publish_contract()

    print("Validation passed:", result["validation_passed"])
    print("Checked rows:", result["checked_rows"])
    print("Contract saved to:", result["contract_path"])
    print("Manifest saved to:", result["manifest_path"])