import json
from pathlib import Path

import pandas as pd
from crewai.tools import tool

from validate_data import validate_data


def inspect_modeling_input(artifacts=None):
    """Check the analyst team's handoff without changing it."""
    if artifacts is None:
        artifacts = Path(__file__).resolve().parent / "artifacts"
    else:
        artifacts = Path(artifacts)

    contract = json.loads(
        (artifacts / "dataset_contract.json").read_text(
            encoding="utf-8"
        )
    )
    df = pd.read_csv(artifacts / "clean_data.csv")

    # Validate the modeling definitions before using them
    features = contract.get("features")
    target = contract.get("target")
    columns = contract.get("columns")

    if not isinstance(columns, dict):
        raise ValueError("Contract must define column rules.")

    if (
        not isinstance(features, list)
        or not features
        or not all(isinstance(name, str) for name in features)
    ):
        raise ValueError("Contract must define a non-empty feature list.")

    if len(features) != len(set(features)):
        raise ValueError("Contract contains duplicate features.")

    if not isinstance(target, str) or target not in columns:
        raise ValueError("Target is missing from contract column rules.")

    if target in features:
        raise ValueError("Target cannot also be an input feature.")

    undefined = set(features) - set(columns)
    if undefined:
        raise ValueError(
            f"Features missing from contract rules: {sorted(undefined)}"
        )

    errors = validate_data(df, contract)

    if errors:
        raise ValueError(
            "Modeling blocked:\n" + "\n".join(errors)
        )

    return {
        "validation_passed": True,
        "rows": len(df),
        "features": features,
        "target": target,
        "contract_version": contract["contract_version"],
    }


@tool("Inspect Modeling Input")
def inspect_modeling_input_tool() -> str:
    """Validate the cleaned dataset and contract before modeling."""
    return json.dumps(inspect_modeling_input(), ensure_ascii=False)


if __name__ == "__main__":
    print(
        json.dumps(
            inspect_modeling_input(),
            ensure_ascii=False,
            indent=2,
        )
    )