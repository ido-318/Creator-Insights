EXPECTED_FEATURES = [
    "post_type",
    "category",
    "post_month",
    "post_weekday",
    "post_hour",
    "paid",
]

EXPECTED_RULES = {
    "post_type": {
        "dtype": "string",
        "nullable": False,
        "allowed_values": ["Photo", "Status", "Link", "Video"],
    },
    "category": {
        "dtype": "integer",
        "nullable": False,
        "allowed_values": [1, 2, 3],
    },
    "post_month": {
        "dtype": "integer",
        "nullable": False,
        "min": 1,
        "max": 12,
    },
    "post_weekday": {
        "dtype": "integer",
        "nullable": False,
        "allowed_values": [1, 2, 3, 4, 5, 6, 7],
    },
    "post_hour": {
        "dtype": "integer",
        "nullable": False,
        "min": 0,
        "max": 23,
        "unit": "hour_of_day",
    },
    "paid": {
        "dtype": "integer",
        "nullable": False,
        "allowed_values": [0, 1],
    },
    "total_interactions": {
        "dtype": "integer",
        "nullable": False,
        "min": 0,
        "unit": "count",
    },
}


def validate_contract(contract):
    """Check compatibility with the consumer's supported contract v1."""
    errors = []

    if not isinstance(contract, dict):
        return ["Contract must be a JSON object."]

    if contract.get("contract_version") != "1.0":
        errors.append("Unsupported contract version.")

    if contract.get("features") != EXPECTED_FEATURES:
        errors.append("Contract features differ from the supported schema.")

    if contract.get("target") != "total_interactions":
        errors.append("Unexpected prediction target.")

    if contract.get("allow_extra_columns") is not False:
        errors.append("Extra columns must not be allowed.")

    min_rows = contract.get("min_rows")
    if type(min_rows) is not int or min_rows < 100:
        errors.append("min_rows must be an integer of at least 100.")

    columns = contract.get("columns")

    if not isinstance(columns, dict):
        errors.append("Contract must contain column rules.")
        return errors

    if set(columns) != set(EXPECTED_RULES):
        errors.append("Contract has missing or unexpected column definitions.")

    for column, expected in EXPECTED_RULES.items():
        actual = columns.get(column)

        if not isinstance(actual, dict):
            errors.append(f"{column}: missing or invalid rules.")
            continue

        if "unit" in expected:
            if actual.get("unit") != expected["unit"]:
                errors.append(
                    f"{column}: expected unit {expected['unit']}, "
                    f"got {actual.get('unit')}"
                )

        if actual != expected:
            errors.append(
                f"{column}: rules differ from supported contract v1.0."
            )

    return errors