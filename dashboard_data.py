"""Read-only dashboard data and deterministic aggregations."""
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
ARTIFACTS = ROOT / "artifacts"
POST_TYPES = {"Photo": "תמונה", "Status": "סטטוס", "Link": "קישור", "Video": "וידאו"}
REPORTS = {
    "insights.md": "תובנות האנליסטים",
    "evaluation_report.md": "דוח הערכה",
    "model_card.md": "כרטיס המודל",
    "scientist_review.md": "ביקורת מדעית",
}
COLUMNS = ["post_type", "category", "post_month", "post_weekday", "post_hour", "paid", "total_interactions"]


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def validate_frame(df):
    if not set(COLUMNS).issubset(df.columns) or df.empty:
        raise ValueError("קובץ הנתונים ריק או שחסרות בו עמודות נדרשות.")
    if df[COLUMNS].isna().any().any():
        raise ValueError("נמצאו ערכים חסרים בנתונים.")
    if not df.post_type.isin(POST_TYPES).all():
        raise ValueError("נמצא סוג פוסט שאינו מוכר.")
    for name, low, high in [("category", 1, 3), ("post_month", 1, 12), ("post_weekday", 1, 7), ("post_hour", 0, 23), ("paid", 0, 1), ("total_interactions", 0, None)]:
        values = pd.to_numeric(df[name], errors="raise")
        if (values % 1 != 0).any() or (values < low).any() or (high is not None and (values > high).any()):
            raise ValueError(f"ערכים לא תקינים בעמודה {name}.")
        df[name] = values.astype("int64")
    return df[COLUMNS].copy()


def load_local(artifacts=ARTIFACTS):
    df = validate_frame(pd.read_csv(artifacts / "clean_data.csv"))
    training_path = artifacts / "training_summary.json"
    training = read_json(training_path) if training_path.exists() else None
    reports = {name: (artifacts / name).read_text(encoding="utf-8") for name in REPORTS if (artifacts / name).exists()}
    return df, training, reports


def filter_posts(df, post_types, months, paid):
    mask = df.post_type.isin(post_types) & df.post_month.between(*months)
    if paid != "הכל":
        mask &= df.paid.eq(1 if paid == "ממומן" else 0)
    return df.loc[mask].copy()


def summarize(df):
    return df.groupby("post_type", observed=True).agg(
        post_count=("total_interactions", "size"),
        median_interactions=("total_interactions", "median"),
        mean_interactions=("total_interactions", "mean"),
    ).reset_index().sort_values("median_interactions", ascending=False)


def flow_history(artifacts=ARTIFACTS):
    history = []
    for path in artifacts.glob("flow_*.json"):
        try:
            record = read_json(path)
            if isinstance(record, dict) and isinstance(record.get("events"), list):
                history.append(record)
        except (OSError, ValueError):
            continue
    return sorted(history, key=lambda r: (r["events"][-1].get("time", "") if r["events"] else ""), reverse=True)

