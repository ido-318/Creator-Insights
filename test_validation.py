import json
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


def check(name, data, expected_error=None):
    errors = validate_data(data, contract)

    if expected_error is None:
        assert not errors, f"{name}: unexpected errors: {errors}"
    else:
        assert any(expected_error in error for error in errors), (
            f"{name}: expected '{expected_error}', got {errors}"
        )

    print(f"PASS: {name}")
    for error in errors:
        print(f"  Detected: {error}")


# Valid data should pass
check("Valid data", df)

# Required column is missing
check(
    "Missing column",
    df.drop(columns=["paid"]),
    "Missing columns",
)

# An hour cannot be 99
bad_hour = df.copy()
bad_hour.loc[0, "post_hour"] = 99
check("Invalid hour", bad_hour, "post_hour: values above 23")

# A required value is missing
missing_paid = df.copy()
missing_paid["paid"] = missing_paid["paid"].astype("Int64")
missing_paid.loc[0, "paid"] = pd.NA
check("Missing paid value", missing_paid, "paid: 1 missing values")

# A post-publication metric must not enter the training data
extra_column = df.copy()
extra_column["like"] = 100
check("Unexpected column", extra_column, "Unexpected columns")

print("\nAll 5 checks passed.")