from pathlib import Path

import pandas as pd


def clean_dataset():
    """Clean the source dataset and save the modeling columns."""
    project_dir = Path(__file__).resolve().parent
    source_path = project_dir / "data" / "dataset_Facebook.csv"

    output_dir = project_dir / "artifacts"
    output_dir.mkdir(exist_ok=True)

    df = pd.read_csv(source_path, sep=";")

    column_names = {
        "Type": "post_type",
        "Category": "category",
        "Post Month": "post_month",
        "Post Weekday": "post_weekday",
        "Post Hour": "post_hour",
        "Paid": "paid",
        "Total Interactions": "total_interactions",
    }

    clean_df = df[list(column_names)].copy()
    clean_df = clean_df.dropna(subset=["Paid"])
    clean_df = clean_df.rename(columns=column_names)

    # Validate before conversion so invalid values aren't truncated
    if not clean_df["paid"].isin([0, 1]).all():
        raise ValueError("Paid must contain only 0 or 1.")

    clean_df["paid"] = clean_df["paid"].astype(int)

    output_path = output_dir / "clean_data.csv"
    clean_df.to_csv(output_path, index=False)
     
    return {
        "original_rows": len(df),
        "removed_rows": len(df) - len(clean_df),
        "removal_reason": "Missing value in the Paid column",
        "duplicates_checked": False,
        "clean_rows": len(clean_df),
        "column_count": len(clean_df.columns),
        "output_path": str(output_path),
    }


if __name__ == "__main__":
    result = clean_dataset()

    for name, value in result.items():
        print(f"{name}: {value}")