import json
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from handoff_integrity import seal_handoff, verify_handoff
from validate_data import validate_data


source = Path(__file__).resolve().parent / "artifacts"

with TemporaryDirectory() as temporary_directory:
    artifacts = Path(temporary_directory)

    for filename in ["clean_data.csv", "dataset_contract.json"]:
        shutil.copy2(source / filename, artifacts / filename)

    # Record the original handoff
    seal_handoff(artifacts)
    assert verify_handoff(artifacts)["integrity_verified"]
    print("PASS: Unchanged handoff accepted.")

    # Simulate a scale change after publication
    data_path = artifacts / "clean_data.csv"
    df = pd.read_csv(data_path)
    df["total_interactions"] = df["total_interactions"] * 100
    df.to_csv(data_path, index=False)

    contract = json.loads(
        (artifacts / "dataset_contract.json").read_text(
            encoding="utf-8"
        )
    )

    # These values still satisfy the schema and numeric limits
    assert not validate_data(df, contract)
    print("Confirmed: Schema checks alone accept the changed values.")

    # The fingerprint check must reject the modified file
    try:
        verify_handoff(artifacts)
    except ValueError as error:
        assert "clean_data.csv" in str(error)
        assert "changed after publication" in str(error)
        print("PASS: Changed data blocked.")
        print("Detected:", error)
    else:
        raise AssertionError("Changed data was incorrectly accepted.")