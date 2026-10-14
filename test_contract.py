import json
from copy import deepcopy
from pathlib import Path

import pandas as pd

from validate_data import validate_data


artifacts = Path(__file__).resolve().parent / "artifacts"

contract = json.loads(
    (artifacts / "dataset_contract.json").read_text(
        encoding="utf-8"
    )
)
df = pd.read_csv(artifacts / "clean_data.csv")


def check_rejected(name, modified_contract, expected_error):
    errors = validate_data(df, modified_contract)

    assert any(expected_error in error for error in errors), (
        f"{name}: expected '{expected_error}', got {errors}"
    )

    print(f"PASS: {name}")
    for error in errors:
        print(f"  Detected: {error}")


# Confirm that the original contract still passes
assert not validate_data(df, contract)
print("PASS: Original contract")


# 1. Change the declared time unit
changed_unit = deepcopy(contract)
changed_unit["columns"]["post_hour"]["unit"] = "minute_of_day"

check_rejected(
    "Changed time unit",
    changed_unit,
    "post_hour: expected unit",
)


# 2. Delete a required column definition
missing_rule = deepcopy(contract)
del missing_rule["columns"]["paid"]

check_rejected(
    "Missing column definition",
    missing_rule,
    "missing or unexpected column definitions",
)


# 3. Relax the hour limit without an agreed schema change
relaxed_rule = deepcopy(contract)
relaxed_rule["columns"]["post_hour"]["max"] = 999

check_rejected(
    "Relaxed hour limit",
    relaxed_rule,
    "post_hour: rules differ",
)


# 4. Add the prediction target to the input features
leaky_features = deepcopy(contract)
leaky_features["features"].append("total_interactions")

check_rejected(
    "Target included in features",
    leaky_features,
    "Contract features differ",
)


# 5. Supply an unsupported contract version
unsupported_version = deepcopy(contract)
unsupported_version["contract_version"] = "2.0"

check_rejected(
    "Unsupported contract version",
    unsupported_version,
    "Unsupported contract version",
)

print("\nAll 6 contract checks passed.")