import json
from pathlib import Path

import pandas as pd


def validate_data(df, contract):
    errors = []
    rules = contract["columns"]

    # Check required and unexpected columns
    missing = set(rules) - set(df.columns)
    extra = set(df.columns) - set(rules)

    if missing:
        errors.append(f"Missing columns: {sorted(missing)}")

    if extra and not contract["allow_extra_columns"]:
        errors.append(f"Unexpected columns: {sorted(extra)}")

    if len(df) < contract["min_rows"]:
        errors.append(
            f"Too few rows: {len(df)}; "
            f"minimum is {contract['min_rows']}"
        )

    # Check each column that exists in the dataset
    for column, rule in rules.items():
        if column not in df.columns:
            continue

        values = df[column]

        if not rule["nullable"] and values.isna().any():
            errors.append(
                f"{column}: {values.isna().sum()} missing values"
            )

        present = values.dropna()

        if rule["dtype"] == "integer":
            numeric = pd.to_numeric(present, errors="coerce")

            if numeric.isna().any():
                errors.append(f"{column}: contains non-numeric values")
                continue

            if numeric.isin([float("inf"), float("-inf")]).any():
                errors.append(f"{column}: contains infinite values")
                continue

            if (numeric % 1 != 0).any():
                errors.append(f"{column}: values must be whole numbers")

            present = numeric

        elif rule["dtype"] == "string":
            if not present.map(lambda value: isinstance(value, str)).all():
                errors.append(f"{column}: values must be text")

        else:
            errors.append(
                f"{column}: unsupported type {rule['dtype']}"
            )
            continue

        if "allowed_values" in rule:
            if not present.isin(rule["allowed_values"]).all():
                errors.append(f"{column}: contains disallowed values")

        if "min" in rule and (present < rule["min"]).any():
            errors.append(f"{column}: values below {rule['min']}")

        if "max" in rule and (present > rule["max"]).any():
            errors.append(f"{column}: values above {rule['max']}")

    return errors


def main():
    project_dir = Path(__file__).resolve().parent
    artifacts = project_dir / "artifacts"

    contract = json.loads(
        (artifacts / "dataset_contract.json").read_text(
            encoding="utf-8"
        )
    )
    df = pd.read_csv(artifacts / "clean_data.csv")

    errors = validate_data(df, contract)

    if errors:
        print("VALIDATION FAILED:")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)

    print("VALIDATION PASSED")
    print(f"Checked {len(df)} rows and {len(df.columns)} columns.")


if __name__ == "__main__":
    main()