from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

project_dir = Path(__file__).resolve().parent
artifacts = project_dir / "artifacts"

df = pd.read_csv(artifacts / "clean_data.csv")

# Summarize interactions for each post type
summary = (
    df.groupby("post_type")["total_interactions"]
    .agg(
        post_count="count",
        median_interactions="median",
        mean_interactions="mean",
    )
    .sort_values("median_interactions", ascending=False)
)

print(summary.round(1).to_string())

# Include sample sizes in the labels
labels = [
    f"{post_type}\n(n={int(row['post_count'])})"
    for post_type, row in summary.iterrows()
]

fig, ax = plt.subplots(figsize=(8, 5))

ax.bar(
    labels,
    summary["median_interactions"],
    color="#6366f1",
)

ax.set_title("Median interactions by post type")
ax.set_xlabel("Post type and sample size")
ax.set_ylabel("Median total interactions")

fig.tight_layout()

output_path = artifacts / "interactions_by_type.png"
fig.savefig(output_path, dpi=150)
plt.close(fig)

summary.to_csv(artifacts / "summary_by_type.csv")

print("\nChart saved to:", output_path)



# Turn the summary tables into HTML
summary_html = summary.round(1).to_html(
    classes="data-table",
    border=0,
)

statistics_html = (
    df["total_interactions"]
    .describe()
    .round(1)
    .to_frame(name="total_interactions")
    .to_html(classes="data-table", border=0)
)

# Build a report using the current data
report_html = f"""
<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>Creator Insights — דוח ניתוח</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            background: #f4f6fb;
            color: #202434;
            max-width: 1000px;
            margin: 40px auto;
            padding: 0 24px;
            line-height: 1.7;
        }}
        section {{
            background: white;
            padding: 24px;
            margin: 20px 0;
            border-radius: 12px;
        }}
        h1, h2 {{ color: #4338ca; }}
        .data-table {{
            border-collapse: collapse;
            width: 100%;
            direction: ltr;
        }}
        .data-table th, .data-table td {{
            padding: 10px;
            border-bottom: 1px solid #ddd;
            text-align: center;
        }}
        .data-table th {{ background: #eef2ff; }}
        img {{ max-width: 100%; height: auto; }}
    </style>
</head>
<body>
    <h1>Creator Insights</h1>
    <p>דוח ראשוני לניתוח ביצועי פוסטים</p>

    <section>
        <h2>הנתונים שנבדקו</h2>
        <p>
            מספר פוסטים: <strong>{len(df)}</strong><br>
            מספר עמודות: <strong>{len(df.columns)}</strong><br>
            מקור: UCI Facebook Metrics
        </p>
        <p>
            מדד הביצועים הוא מספר האינטראקציות הכולל,
            ולא שיעור מעורבות ביחס לחשיפה.
        </p>
    </section>

    <section>
        <h2>השוואת סוגי פוסטים</h2>
        {summary_html}
        <img
            src="interactions_by_type.png"
            alt="גרף חציון אינטראקציות לפי סוג פוסט וגודל מדגם"
        >
        <p>
            חשוב להשוות גם את מספר הפוסטים בכל קבוצה.
            תוצאה המבוססת על מעט פוסטים מחייבת זהירות.
        </p>
    </section>

    <section>
        <h2>סטטיסטיקה תיאורית של האינטראקציות</h2>
        {statistics_html}
        <p>
            count — מספר הפוסטים; mean — ממוצע;
            std — סטיית תקן; min ו־max — מינימום ומקסימום;
            50% — חציון; 25% ו־75% — הרבעון הראשון והשלישי.
        </p>
    </section>

    <section>
        <h2>מגבלות הניתוח</h2>
        <p>
            זהו מדגם היסטורי מעמוד Facebook יחיד.
            ההשוואה אינה מנטרלת הבדלים במימון ובתזמון,
            ואינה מוכיחה שסוג הפוסט גורם להבדל בביצועים.
        </p>
    </section>
</body>
</html>
"""

report_path = artifacts / "eda_report.html"
report_path.write_text(report_html, encoding="utf-8")

print("HTML report saved to:", report_path)