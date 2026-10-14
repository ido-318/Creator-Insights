import subprocess
import sys
import json
from pathlib import Path

import pandas as pd
import streamlit as st


ARTIFACTS = Path(__file__).resolve().parent / "artifacts"

st.set_page_config(
    page_title="Creator Insights",
    page_icon="📊",
    layout="wide",
)

st.title("📊 Creator Insights")
st.write("ניתוח ביצועי תוכן והשוואת מודלים לחיזוי אינטראקציות")

st.caption(
    "תצוגת קבצים שנשמרו בפרויקט. "
    "פתיחת המסך אינה מפעילה סוכנים או מאמנת מודלים."
)

st.subheader("הפעלת המערכת")

st.caption(
    "הפעלה מלאה מפעילה את ששת הסוכנים דרך Claude, "
    "מאמנת מחדש את המודלים ומעדכנת את התוצרים. "
    "הקריאות ל־API מחויבות לפי השימוש."
)

if st.button("הפעלת התהליך המלא", type="primary"):
    project_dir = ARTIFACTS.parent
    run_log_path = ARTIFACTS / "latest_ui_run.log"
    ARTIFACTS.mkdir(exist_ok=True)

    st.session_state.pop("flow_run_result", None)

    try:
        with st.spinner("התהליך פועל — יש להמתין לסיום…"):
            with run_log_path.open("w", encoding="utf-8") as log_file:
                process = subprocess.run(
                    [
                        sys.executable,
                        "-u",
                        str(project_dir / "project_flow.py"),
                    ],
                    cwd=project_dir,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    stdin=subprocess.DEVNULL,
                    timeout=1800,
                )

        st.session_state["flow_run_result"] = {
            "success": process.returncode == 0,
            "message": (
                "התהליך הסתיים בהצלחה והתוצרים עודכנו."
                if process.returncode == 0
                else "התהליך נכשל. ייתכן שחלק מהתוצרים נשארו מהרצה קודמת."
            ),
        }

    except subprocess.TimeoutExpired:
        st.session_state["flow_run_result"] = {
            "success": False,
            "message": (
                "ההרצה חרגה ממגבלת 30 דקות ונעצרה. "
                "ייתכן שחלק מהתוצרים עודכנו וחלקם לא."
            ),
        }

    except OSError:
        st.session_state["flow_run_result"] = {
            "success": False,
            "message": "לא ניתן להפעיל את התהליך. בדוק את טרמינל האפליקציה.",
        }

run_result = st.session_state.get("flow_run_result")

if run_result is not None:
    if run_result["success"]:
        st.success(run_result["message"])
    else:
        st.error(run_result["message"])

    run_log_path = ARTIFACTS / "latest_ui_run.log"

    if run_log_path.is_file():
        with st.expander("פרטי ההרצה האחרונה מהממשק"):
            log_text = run_log_path.read_text(
                encoding="utf-8",
                errors="replace",
            )
            st.code(log_text[-20000:], language="text")

st.divider()

required_files = [
    "clean_data.csv",
    "summary_by_type.csv",
    "training_summary.json",
]

missing = [
    name
    for name in required_files
    if not (ARTIFACTS / name).is_file()
]

if missing:
    st.error("חסרים קבצים: " + ", ".join(missing))
    st.stop()

df = pd.read_csv(ARTIFACTS / "clean_data.csv")
summary = pd.read_csv(ARTIFACTS / "summary_by_type.csv")

training = json.loads(
    (ARTIFACTS / "training_summary.json").read_text(
        encoding="utf-8"
    )
)

first, second, third = st.columns(3)

first.metric("פוסטים בנתונים הנקיים", len(df))
second.metric(
    "חציון אינטראקציות",
    f"{df['total_interactions'].median():,.1f}",
)
third.metric("סוגי פוסטים", df["post_type"].nunique())

data_tab, model_tab, report_tab = st.tabs([
    "נתונים וגרפים",
    "תוצאות המודלים",
    "תובנות",
])

with data_tab:
    st.subheader("השוואה לפי סוג פוסט")
    st.dataframe(summary.round(2), hide_index=True)

    chart_path = ARTIFACTS / "interactions_by_type.png"

    if chart_path.is_file():
        st.image(str(chart_path))
    else:
        st.warning("קובץ הגרף חסר.")

    st.caption(
        "הבדלים בין הקבוצות אינם מוכיחים סיבתיות. "
        "יש להתחשב במספר הפוסטים בכל קבוצה."
    )

    with st.expander("הצגת הנתונים הנקיים"):
        st.dataframe(df, hide_index=True)

with model_tab:
    st.subheader("השוואה פנימית על נתוני האימון")

    cv_results = pd.DataFrame(training["cross_validation"])
    st.dataframe(cv_results.round(2), hide_index=True)

    st.write("המודל הנבחר:", training["selected_model"])

    st.subheader("תוצאות בקבוצת הבדיקה")
    test = training["test_results"]

    baseline_col, model_col = st.columns(2)

    baseline_col.metric(
        "MAE — קו בסיס",
        f"{test['baseline_mae']:.2f}",
    )
    model_col.metric(
        "MAE — המודל הנבחר",
        f"{test['selected_model_mae']:.2f}",
    )

    st.caption("MAE נמדד באינטראקציות. נמוך יותר עדיף.")

    if test["selected_model_beats_baseline"]:
        st.success("המודל הנבחר ניצח את קו הבסיס בחלוקה הזו.")
    else:
        st.warning(
            "המודל הנבחר לא ניצח את קו הבסיס בקבוצת הבדיקה."
        )

with report_tab:
    insights_path = ARTIFACTS / "insights.md"

    if insights_path.is_file():
        st.markdown(insights_path.read_text(encoding="utf-8"))
    else:
        st.info("דוח התובנות עדיין לא נוצר.")

st.info(
    "פרויקט לימודי המבוסס על נתונים היסטוריים מדף Facebook יחיד. "
    "הביצועים על חשבונות אחרים או בתקופות עתידיות לא נבדקו."
)