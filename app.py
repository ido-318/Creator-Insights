"""Creator Insights — Hebrew analytics workspace, with optional Supabase storage."""
from datetime import datetime
import subprocess

import altair as alt
import pandas as pd
import streamlit as st

from dashboard_data import ARTIFACTS, POST_TYPES, REPORTS, filter_posts, flow_history, load_local, summarize
from dashboard_theme import PALETTES, build_theme, export_theme, read_config, save_theme
from supabase_store import StoreError, SupabaseStore, build_snapshot, get_config
from app_security import read_log_tail, redact_secrets, require_local_access
from workspace_runtime import WorkspaceBusy, run_ui_flow

st.set_page_config(page_title="Creator Insights | סביבת המחקר שלך", page_icon=":material/insights:", layout="wide")
st.set_option("client.showErrorDetails", "none")
try:
    secret_values = dict(st.secrets)
except (FileNotFoundError, st.errors.StreamlitSecretNotFoundError):
    secret_values = {}
require_local_access(st, secret_values)

# Direction only: visual colors, spacing, typography and widgets use native theming.
# Keep code, charts and numeric tables in their natural LTR direction.
st.html("""<style>
[data-testid="stMarkdownContainer"], [data-testid="stWidgetLabel"],
[data-testid="stAlertContent"], [data-testid="stCaptionContainer"] {direction:rtl;text-align:right}
[data-testid="stMetric"] {direction:rtl;text-align:right}
[data-testid="stMetricValue"] {direction:ltr;text-align:right}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] {text-align:right}
[data-testid="stCode"], [data-testid="stDataFrame"], [data-testid="stVegaLiteChart"] {direction:ltr}
</style>""")

config = read_config()
colors = config["theme"]["chartCategoricalColors"]
for key, value in {"primary": colors[0], "secondary": colors[1], "dark": config["theme"]["base"] == "dark", "types": list(POST_TYPES), "months": (1, 12), "paid": "הכל"}.items():
    st.session_state.setdefault(key, value)


def choose_palette():
    st.session_state.primary, st.session_state.secondary = PALETTES[st.session_state.palette]


def reset_filters():
    st.session_state.types = list(POST_TYPES)
    st.session_state.months = (1, 12)
    st.session_state.paid = "הכל"


@st.cache_data(ttl=300, max_entries=4, show_spinner=False)
def cached_local(signature):
    return load_local()


with st.sidebar:
    st.markdown("## :material/insights: Creator Insights")
    st.caption("סביבת עבודה לתוכן שמבוסס על נתונים")
    st.space("small")
    page = st.radio("סביבת עבודה", ["סקירה", "חקר נתונים", "מעבדת מודלים", "דוחות", "מערכת"],
                    format_func=lambda name: {"סקירה": ":material/dashboard:  סקירה", "חקר נתונים": ":material/query_stats:  חקר נתונים", "מעבדת מודלים": ":material/science:  מעבדת מודלים", "דוחות": ":material/article:  דוחות", "מערכת": ":material/settings:  מערכת"}[name], key="page", label_visibility="collapsed")
    st.space("small")
    st.caption("מקור הנתונים")
    source = st.selectbox("מקור נתונים", ["תוצרים מקומיים", "Supabase"], key="source", label_visibility="collapsed")
    if page in ("סקירה", "חקר נתונים"):
        st.markdown("#### מסננים")
        st.multiselect("סוגי תוכן", list(POST_TYPES), format_func=POST_TYPES.get, key="types", persist_state="session")
        st.slider("חודשי פרסום", 1, 12, key="months", persist_state="session")
        st.segmented_control("קידום", ["הכל", "אורגני", "ממומן"], required=True, key="paid", persist_state="session")
        st.button("איפוס מסננים", icon=":material/restart_alt:", on_click=reset_filters, width="stretch")
    with st.expander("עיצוב וצבעים", icon=":material/palette:"):
        st.selectbox("ערכת צבעים", list(PALETTES), key="palette", on_change=choose_palette)
        st.color_picker("צבע ראשי", key="primary")
        st.color_picker("צבע משני", key="secondary")
        st.toggle("מצב כהה", key="dark")
        st.caption("הגרפים מציגים את הצבעים מיד. שמירה מחילה את העיצוב על סביבת העבודה המקומית ושומרת אותו לפתיחה הבאה.")
        if st.button("שמירת העיצוב", icon=":material/check:", width="stretch"):
            try:
                theme_config = build_theme(config, st.session_state.primary, st.session_state.secondary, st.session_state.dark)
                save_theme(theme_config)
                st.success("העיצוב נשמר. אם הממשק עדיין לא השתנה, רעננו את הדף.")
            except (OSError, ValueError):
                st.error("לא ניתן לשמור את העיצוב. בדקו את הצבעים והרשאות הקובץ.")
        try:
            theme_config = build_theme(config, st.session_state.primary, st.session_state.secondary, st.session_state.dark)
            st.download_button("הורדת ערכת העיצוב", export_theme(theme_config), "config.toml", "text/plain", icon=":material/download:")
        except ValueError:
            st.caption("בחרו צבע ראשי כהה יותר כדי לשמור ערכה נגישה.")
    st.space("small")
    st.caption("מחקר תוכן · Facebook Metrics\n\nפרויקט לימודי / עמוד מקור יחיד")
    st.button("יציאה", icon=":material/logout:", on_click=st.session_state.clear)

primary, secondary = st.session_state.primary, st.session_state.secondary
store = None
store_error = None
try:
    settings = get_config(secret_values)
    store = SupabaseStore(settings) if settings else None
except StoreError as exc:
    store_error = str(exc)

headings = {
    "סקירה": ("מבט אחד. יותר תובנות.", "כל מה שצריך כדי להבין את ביצועי התוכן שלך, במקום אחד."),
    "חקר נתונים": ("הסיפור שמאחורי המספרים", "משווים סוגי תוכן, שעות פרסום וקידום — ומעמיקים בנתונים."),
    "מעבדת מודלים": ("בודקים. משווים. לומדים.", "תוצאות הניסוי, בחירת המודל והמרחק מקו הבסיס."),
    "דוחות": ("מהנתונים לתמונה ברורה", "דוחות המחקר, מסקנות האנליסטים וביקורת המודל."),
    "מערכת": ("סביבת העבודה שלך", "הפעלת התהליך, חיבור לענן והיסטוריית הריצות."),
}
st.caption("CREATOR INSIGHTS  /  " + page)
st.title(headings[page][0], text_alignment="right")
st.caption(headings[page][1], text_alignment="right")

frame, training, reports, updated = None, None, {}, None
load_error = None
try:
    if source == "Supabase":
        if not store:
            raise StoreError(store_error or "Supabase עדיין לא הוגדר. הגדרות החיבור נמצאות במסך מערכת.")
        # Session-local snapshot avoids sharing privileged data through a global cache.
        if "cloud_snapshot" not in st.session_state:
            st.session_state.cloud_snapshot = store.latest()
        frame, training, reports, updated = st.session_state.cloud_snapshot
    else:
        paths = [ARTIFACTS / n for n in ("clean_data.csv", "training_summary.json", *REPORTS)]
        signature = tuple((str(p), p.stat().st_mtime_ns, p.stat().st_size) for p in paths if p.exists())
        frame, training, reports = cached_local(signature)
        updated = datetime.fromtimestamp((ARTIFACTS / "clean_data.csv").stat().st_mtime).isoformat()
except (OSError, ValueError, KeyError, StoreError) as exc:
    load_error = redact_secrets(exc, secret_values)

with st.container(horizontal=True, horizontal_alignment="right"):
    st.badge("תמונת מצב מהענן" if source == "Supabase" else "תוצרים מקומיים", icon=":material/cloud:" if source == "Supabase" else ":material/folder:", color="blue")
    if updated:
        st.caption("עודכן " + str(updated)[:16].replace("T", " · "))
    if st.button("רענון נתונים", icon=":material/refresh:", key="refresh"):
        cached_local.clear()
        st.session_state.pop("cloud_snapshot", None)
        st.rerun()

history = flow_history()
if source == "תוצרים מקומיים" and history and history[0].get("status") != "completed":
    st.warning("הריצה המקומית האחרונה לא הושלמה. ייתכן שמוצגים תוצרים מריצות שונות. פרטים במסך מערכת.")
if load_error and page != "מערכת":
    st.warning("לא ניתן להציג את מקור הנתונים שנבחר: " + load_error)
    st.info("אפשר לבחור תוצרים מקומיים בתפריט הצד, או להיכנס למערכת כדי להגדיר חיבור ולהפעיל את התהליך.")
    st.stop()


def chart_style(chart):
    return chart.configure_view(strokeWidth=0).configure_axis(gridOpacity=.12, labelFontSize=12, titleFontSize=12, domain=False).configure_legend(title=None)


def type_chart(data):
    data = summarize(data).assign(label=lambda d: d.post_type.map(POST_TYPES))
    chart = alt.Chart(data).mark_bar(cornerRadiusEnd=6, height=25).encode(
        x=alt.X("median_interactions:Q", title="חציון אינטראקציות"),
        y=alt.Y("label:N", sort="-x", title=None),
        color=alt.Color("post_type:N", scale=alt.Scale(domain=list(POST_TYPES), range=[primary, secondary, "#D19134", "#A181CD"]), legend=None),
        tooltip=[alt.Tooltip("label:N", title="סוג תוכן"), alt.Tooltip("post_count:Q", title="פוסטים"), alt.Tooltip("median_interactions:Q", title="חציון", format=",.1f")],
    ).properties(height=245)
    st.altair_chart(chart_style(chart), alt="חציון אינטראקציות לפי סוג תוכן ומספר הפוסטים בכל קבוצה")


if page in ("סקירה", "חקר נתונים"):
    filtered = filter_posts(frame, st.session_state.types, st.session_state.months, st.session_state.paid)
    st.caption(f"{len(filtered):,} מתוך {len(frame):,} פוסטים · חודשים {st.session_state.months[0]}–{st.session_state.months[1]} · {st.session_state.paid}")
    if filtered.empty:
        st.info("אין פוסטים שמתאימים לסינון. נסו להרחיב את טווח החודשים או לבחור סוגי תוכן נוספים.")
        st.button("הצגת כל הפוסטים", on_click=reset_filters, type="primary")
        st.stop()
    with st.container(horizontal=True):
        with st.container(width=440):
            first, second = st.columns(2)
            first.metric("פוסטים בניתוח", f"{len(filtered):,}", border=True)
            second.metric("סך אינטראקציות", f"{filtered.total_interactions.sum():,}", border=True)
        with st.container(width=440):
            third, fourth = st.columns(2)
            third.metric("חציון לפוסט", f"{filtered.total_interactions.median():,.1f}", border=True)
            fourth.metric("שיעור תוכן ממומן", f"{filtered.paid.mean():.0%}", border=True)

    if page == "סקירה":
        charts = st.container(horizontal=True, gap="medium")
        with charts.container(border=True, width=440):
            st.subheader("איזה תוכן מוביל באינטראקציות?", text_alignment="right")
            st.caption("השוואת חציון אינטראקציות לכל פוסט")
            type_chart(filtered)
        with charts.container(border=True, width=440):
            st.subheader("ביצועים לאורך השנה", text_alignment="right")
            st.caption("חציון חודשי · לפי חודש הפרסום במאגר")
            monthly = filtered.groupby("post_month").agg(value=("total_interactions", "median"), count=("total_interactions", "size")).reset_index()
            chart = alt.Chart(monthly).mark_area(color=primary, opacity=.16, line={"color": primary, "strokeWidth": 3}, point={"filled": True, "fill": primary, "size": 55}).encode(
                x=alt.X("post_month:O", title="חודש", sort="ascending"), y=alt.Y("value:Q", title="חציון אינטראקציות"),
                tooltip=[alt.Tooltip("post_month:O", title="חודש"), alt.Tooltip("value:Q", title="חציון", format=",.1f"), alt.Tooltip("count:Q", title="פוסטים")],
            ).properties(height=245)
            st.altair_chart(chart_style(chart), alt="חציון אינטראקציות לכל חודש פרסום, לפי המסננים")
        grouped = summarize(filtered)
        leader = grouped.iloc[0]
        with st.container(border=True):
            st.subheader("נקודה למחשבה", icon=":material/lightbulb:", text_alignment="right")
            st.markdown(f"**{POST_TYPES[leader.post_type]}** מוביל בחציון האינטראקציות בסינון הנוכחי: **{leader.median_interactions:,.1f}**, על בסיס **{int(leader.post_count)} פוסטים**.")
            st.caption("זהו קשר תיאורי, לא הוכחה שסוג התוכן גורם לביצועים. השוו גם את גודל הקבוצות לפני שמסיקים מסקנות.")
    else:
        charts = st.container(horizontal=True, gap="medium")
        with charts.container(border=True, width=440):
            st.subheader("תוכן מול ביצועים", text_alignment="right")
            type_chart(filtered)
        with charts.container(border=True, width=440):
            st.subheader("מתי פורסם התוכן?", text_alignment="right")
            hourly = filtered.groupby("post_hour").agg(median=("total_interactions", "median"), count=("total_interactions", "size")).reset_index()
            chart = alt.Chart(hourly).mark_bar(color=secondary, cornerRadiusTopLeft=4, cornerRadiusTopRight=4).encode(
                x=alt.X("post_hour:O", title="שעת פרסום", sort="ascending"), y=alt.Y("median:Q", title="חציון אינטראקציות"),
                tooltip=[alt.Tooltip("post_hour:O", title="שעה"), alt.Tooltip("median:Q", title="חציון"), alt.Tooltip("count:Q", title="פוסטים")],
            ).properties(height=245)
            st.altair_chart(chart_style(chart), alt="חציון אינטראקציות לפי שעת פרסום")
        st.subheader("הנתונים שלך, מקרוב", text_alignment="right")
        st.caption("הטבלה וההורדה משקפות את המסננים. ניתן למיין לפי כותרות העמודות.")
        display = filtered.assign(post_type=filtered.post_type.map(POST_TYPES)).rename(columns={"post_type": "סוג תוכן", "category": "קטגוריה", "post_month": "חודש", "post_weekday": "קוד יום במאגר", "post_hour": "שעה", "paid": "ממומן (1/0)", "total_interactions": "אינטראקציות"})
        st.dataframe(display, hide_index=True, height=380, alt="הפוסטים המתאימים למסננים")
        st.download_button("הורדת הנתונים המסוננים", filtered.to_csv(index=False).encode("utf-8-sig"), "creator-insights-filtered.csv", "text/csv", icon=":material/download:")

elif page == "מעבדת מודלים":
    if not training:
        st.info("תוצאות האימון עדיין לא זמינות. הפעילו את תהליך המידול ממסך מערכת.")
        st.stop()
    st.caption("תוצאות האימון המלא · מסנני התוכן אינם משנים את ניסוי המודל")
    try:
        result = training["test_results"]
        baseline, selected = float(result["baseline_mae"]), float(result["selected_model_mae"])
        with st.container(horizontal=True):
            st.metric("MAE · קו הבסיס", f"{baseline:.2f}", border=True)
            st.metric("MAE · המודל הנבחר", f"{selected:.2f}", delta=f"{selected-baseline:+.2f}", delta_color="inverse", delta_description="אינטראקציות לעומת קו הבסיס", border=True)
            st.metric("פוסטים באימון", training["training_rows"], border=True)
            st.metric("פוסטים בבדיקה", training["test_rows"], border=True)
        if selected < baseline:
            st.success("המודל עבר את קו הבסיס בחלוקה שנבדקה. עדיין נדרש אימות על נתונים חדשים.")
        else:
            st.warning("המודל עדיין לא עבר את קו הבסיס. בניסוי הזה, חיזוי חציון קבוע מדויק יותר.")
        with st.container(border=True):
            st.subheader("השוואת המועמדים", text_alignment="right")
            st.caption(f"נבחר: {training['selected_model']} · אימות צולב בחמש חלוקות של נתוני האימון")
            cv = pd.DataFrame(training["cross_validation"])
            chart = alt.Chart(cv).mark_bar(color=primary, cornerRadiusEnd=5, height=28).encode(
                x=alt.X("cv_mae_mean:Q", title="MAE ממוצע · נמוך יותר עדיף"), y=alt.Y("model:N", sort="x", title=None),
                tooltip=[alt.Tooltip("model:N", title="מודל"), alt.Tooltip("cv_mae_mean:Q", title="MAE", format=".2f"), alt.Tooltip("cv_mae_std:Q", title="סטיית תקן", format=".2f")],
            ).properties(height=210)
            st.altair_chart(chart_style(chart), alt="שגיאת האימות הצולב של שלושת המועמדים")
            st.dataframe(cv.rename(columns={"model": "מודל", "cv_mae_mean": "MAE ממוצע", "cv_mae_std": "סטיית תקן"}).round(2), hide_index=True, alt="מדדי אימות צולב וסטיית התקן")
        st.caption("MAE הוא ממוצע גודל שגיאת התחזית, באינטראקציות. האימות הצולב משמש לבחירה; קבוצת הבדיקה משמשת להערכה נפרדת. אין להשוות את המספרים כאילו נמדדו על אותם פוסטים.")
    except (KeyError, TypeError, ValueError):
        st.error("סיכום האימון אינו במבנה הצפוי. יש לייצר מחדש את תוצרי המידול.")

elif page == "דוחות":
    chosen = st.selectbox("בחירת דוח", list(REPORTS), format_func=REPORTS.get)
    if chosen in reports:
        st.download_button("הורדת הדוח", reports[chosen], chosen, "text/markdown", icon=":material/download:")
        with st.container(border=True):
            st.markdown(reports[chosen])
    else:
        st.info("הדוח הזה עדיין לא נוצר במקור הנתונים שנבחר.")

elif page == "מערכת":
    left, right = st.columns(2, gap="medium")
    with right.container(border=True):
        st.subheader("התהליך המלא", icon=":material/account_tree:", text_alignment="right")
        st.markdown("**01 · ניתוח** — ניקוי, מחקר וחוזה נתונים\n\n**02 · אימות** — בדיקת החוזה וטביעות הקבצים\n\n**03 · מידול** — אימון, השוואה וביקורת")
        st.caption("ההפעלה משתמשת בשישה סוכני Claude ומעדכנת את התוצרים המקומיים. קריאות API מחויבות לפי השימוש. פתיחת הדשבורד אינה מפעילה אותם.")
        if st.button("הפעלת התהליך המלא", icon=":material/play_arrow:", type="primary", width="stretch"):
            ARTIFACTS.mkdir(exist_ok=True)
            try:
                with st.status("התהליך פועל — ניתוח, אימות ומידול…", expanded=True) as status:
                    st.write("ניתן לעיין ביומן ההרצה בסיום. מגבלת זמן: 30 דקות.")
                    success = run_ui_flow(secret_values=secret_values) == 0
                    status.update(label="התהליך הושלם" if success else "התהליך לא הושלם", state="complete" if success else "error")
                st.session_state.flow_result = "התהליך הושלם והתוצרים עודכנו." if success else "התהליך נכשל. ייתכן שחלק מהתוצרים ישנים. בדקו את יומן ההרצה."
            except subprocess.TimeoutExpired:
                st.session_state.flow_result = "ההרצה נעצרה לאחר 30 דקות. ייתכן שחלק מהתוצרים עודכנו."
            except WorkspaceBusy as exc:
                st.session_state.flow_result = str(exc)
            except OSError:
                st.session_state.flow_result = "לא ניתן להפעיל את התהליך. בדקו הרשאות וסביבת Python."
            cached_local.clear()
            st.rerun()
        if "flow_result" in st.session_state:
            st.info(st.session_state.flow_result)
        log_path = ARTIFACTS / "latest_ui_run.log"
        if log_path.exists():
            with st.expander("יומן ההרצה המקומית האחרונה"):
                st.code(read_log_tail(log_path, values=secret_values), language="text")
    with left.container(border=True):
        st.subheader("Supabase", icon=":material/cloud:", text_alignment="right")
        st.badge("מוגדר · טרם נבדק" if store else "מצב מקומי", color="blue" if store else "gray")
        st.caption("שמירת תמונות מצב של הנתונים, תוצאות המודלים והדוחות. כל תמונת מצב נשמרת בעסקה אחת; סנכרון חוזר של אותו תוכן אינו יוצר כפילות.")
        if store_error:
            st.error(store_error)
        if store:
            if st.button("בדיקת חיבור", icon=":material/wifi:", width="stretch"):
                try:
                    store.check()
                    st.success("החיבור למסד נבדק בהצלחה.")
                except StoreError as exc:
                    st.error(str(exc))
            if st.button("סנכרון התוצרים המקומיים לענן", icon=":material/cloud_upload:", width="stretch"):
                try:
                    with st.spinner("מאמת ושומר תמונת מצב…"):
                        snapshot = build_snapshot()
                        store.sync(snapshot)
                    st.session_state.pop("cloud_snapshot", None)
                    st.success(f"נשמרו {snapshot['row_count']} פוסטים, תוצאות המודל והדוחות.")
                except (StoreError, OSError, ValueError, WorkspaceBusy) as exc:
                    st.error(redact_secrets(exc, secret_values))
        else:
            st.info("להפעלת הענן: צרו פרויקט Supabase, הפעילו את המיגרציה והגדירו את פרטי החיבור בקובץ ‎.env.")
            st.code("SUPABASE_URL=https://PROJECT.supabase.co\nSUPABASE_SECRET_KEY=your_server_secret_key", language="bash")
            st.caption("המפתח נשאר בשרת. הוראות מלאות ב־README וב־docs/supabase.md.")
    st.subheader("היסטוריית ריצות מקומיות", text_alignment="right")
    if history:
        labels = {"completed": "הושלם", "failed": "נכשל", "analysts_running": "ניתוח", "scientists_running": "מידול", "validating": "אימות"}
        for run in history[:10]:
            events = run.get("events", [])
            when = events[-1].get("time", "")[:16].replace("T", " · ") if events else ""
            with st.expander(f"{labels.get(run.get('status'), run.get('status', 'לא ידוע'))}  ·  {when}  ·  {run.get('id', '')[:8]}"):
                safe_events = [{k: redact_secrets(v, secret_values) for k, v in event.items()} for event in events]
                st.dataframe(pd.DataFrame(safe_events), hide_index=True, alt="אירועים מתועדים של הרצת התהליך")
                if run.get("error"):
                    st.error(redact_secrets(run["error"], secret_values))
    else:
        st.caption("עדיין אין ריצות מתועדות.")

st.space("small")
st.caption("Creator Insights · מחקר שקוף, החלטות שקולות. נתונים היסטוריים מעמוד Facebook יחיד; הביצועים בחשבונות אחרים ובתקופות עתידיות לא נבדקו.")
