"""Creator Insights — analytics workspace for content creators (Hebrew RTL / English LTR)."""
from datetime import datetime
import sqlite3
import subprocess
import urllib.parse

import altair as alt
import pandas as pd
import streamlit as st

from dashboard_data import ARTIFACTS, POST_TYPES, REPORTS, filter_posts, flow_history, load_local, summarize
from dashboard_theme import PALETTES, build_theme, export_theme, read_config, save_theme
from supabase_store import StoreError, SupabaseStore, build_snapshot, get_config
from app_security import public_demo, read_log_tail, redact_secrets, require_local_access
from workspace_runtime import WorkspaceBusy, run_ui_flow
from social_connect import PLATFORMS, SOCIAL_KEYS, SocialError, analyze_video, auth_url, consume_state, exchange_code, fetch_videos, interactions, is_pending, new_state
from social_connect import get_config as social_config
from user_store import KEY_NAME as STORE_KEY, PATH_NAME as STORE_PATH, StorageError, UserStore

st.set_page_config(page_title="Creator Insights", page_icon=":material/insights:", layout="wide")
st.set_option("client.showErrorDetails", "none")
try:
    secret_values = dict(st.secrets)
except (FileNotFoundError, st.errors.StreamlitSecretNotFoundError):
    secret_values = {}
# OAuth app credentials stay server-side; only these keys are read, and never rendered.
social_values = {k: secret_values[k] for k in SOCIAL_KEYS if k in secret_values}
storage_values = {k: secret_values[k] for k in (STORE_KEY, STORE_PATH) if k in secret_values}
DEMO = public_demo(secret_values)
if DEMO:
    # Public demo exposes saved artifacts only: never pass credentials to the page.
    secret_values = {}
else:
    require_local_access(st, secret_values)

st.session_state.setdefault("lang", "he")
LANG = st.session_state.lang if st.session_state.lang in ("he", "en") else "he"
RTL = LANG == "he"


def T(he, en):
    return he if RTL else en


TYPE_EN = {"Photo": "Photo", "Status": "Status", "Link": "Link", "Video": "Video"}
PAGE_LABELS = {
    "סקירה": (":material/home:", "בית", "Home"),
    "חיבור חשבון": (":material/link:", "חיבור חשבון", "Connect account"),
    "עוד": (":material/more_horiz:", "עוד", "More"),
}
REPORT_EN = {"insights.md": "Insights", "evaluation_report.md": "Evaluation report", "model_card.md": "Forecast summary", "scientist_review.md": "Expert review"}
PAID_EN = {"הכל": "All", "אורגני": "Organic", "ממומן": "Paid"}


def type_name(key):
    return POST_TYPES[key] if RTL else TYPE_EN[key]


def model_name(name, names):
    """Plain-language labels: no internal model names are shown to users."""
    if "baseline" in str(name).lower():
        return T("קו בסיס", "Baseline")
    others = sorted(n for n in names if "baseline" not in str(n).lower())
    index = others.index(name) if name in others else 0
    letter = "ABCDEFGH"[index % 8]
    return T(f"תחזית {letter}", f"Forecast {letter}")


config = read_config()
colors = config["theme"]["chartCategoricalColors"]
for key, value in {"primary": colors[0], "secondary": colors[1], "dark": config["theme"]["base"] == "dark", "types": list(POST_TYPES), "months": (1, 12), "paid": "הכל"}.items():
    st.session_state.setdefault(key, value)
primary, secondary = st.session_state.primary, st.session_state.secondary

# Design system: direction, spacing, cards and navigation. Colors come from the native theme.
align = "right" if RTL else "left"
st.html(f"""<style>
.block-container {{padding-top:2.2rem;max-width:1240px}}
[data-testid="stMarkdownContainer"], [data-testid="stWidgetLabel"], [data-testid="stAlertContent"],
[data-testid="stCaptionContainer"], [data-testid="stMetric"] {{direction:{'rtl' if RTL else 'ltr'};text-align:{align}}}
[data-testid="stMetricValue"] {{direction:ltr;text-align:{align}}}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] {{text-align:{align}}}
[data-testid="stCode"], [data-testid="stDataFrame"], [data-testid="stVegaLiteChart"] {{direction:ltr}}
[data-testid="stMetric"] {{padding:.35rem .25rem}}
[data-testid="stMetricLabel"] {{opacity:.8}}
h1 {{letter-spacing:-.01em}}
.stApp {{background-image:radial-gradient(900px 420px at 88% -6%, rgba(25,195,179,.16), transparent 62%), radial-gradient(700px 420px at 0% 105%, rgba(79,140,255,.09), transparent 60%)}}
[data-testid="stVerticalBlockBorderWrapper"] {{transition:border-color .2s}}
[data-testid="stVerticalBlockBorderWrapper"]:hover {{border-color:rgba(25,195,179,.55)}}
[data-testid="stMetricValue"] {{color:#5EEAD4}}
.ci-brand {{display:flex;align-items:center;gap:.65rem;direction:{'rtl' if RTL else 'ltr'};margin:.25rem 0 1rem}}
.ci-brand img {{flex:none}}
.ci-brand b {{display:block;font-size:1.05rem;line-height:1.2}}
.ci-brand span {{font-size:.8rem;opacity:.7}}
.ci-chip {{display:inline-flex;align-items:center;gap:.4rem;font-size:.82rem;padding:.2rem .7rem;border-radius:99px;border:1px solid rgba(128,128,128,.35)}}
.ci-note {{font-size:.85rem;opacity:.75}}
[data-testid="stSidebar"] [role="radiogroup"] label {{padding:.35rem .5rem;border-radius:10px}}
[data-testid="stSidebar"] [role="radiogroup"] label:hover {{background:rgba(128,128,128,.12)}}
button:focus-visible, [role="radio"]:focus-visible, input:focus-visible {{outline:3px solid {primary}!important;outline-offset:2px}}
h1 {{font-weight:800!important;letter-spacing:-.035em!important}}
.st-key-hero h1, .st-key-hero [data-testid="stCaptionContainer"] {{text-align:center!important}}
.st-key-hero h1 {{font-size:3.1rem!important;line-height:1.08}}
button[kind="primary"], button[kind="primaryFormSubmit"] {{border-radius:999px!important;border:0!important;font-weight:700!important;padding:.62rem 1.8rem!important;color:#031A18!important;background:linear-gradient(135deg,#2EE6D3,#19C3B3 55%,#12A4C4)!important;box-shadow:0 10px 28px -8px rgba(25,195,179,.6);transition:transform .15s, box-shadow .15s}}
button[kind="primary"]:hover, button[kind="primaryFormSubmit"]:hover {{transform:translateY(-2px);box-shadow:0 16px 34px -8px rgba(25,195,179,.75)}}
button[kind="primary"]:active, button[kind="primaryFormSubmit"]:active {{transform:translateY(0)}}
button[kind="secondary"], button[kind="secondaryFormSubmit"], [data-testid="stDownloadButton"] button {{border-radius:999px!important;font-weight:600!important;transition:border-color .15s, background .15s}}
button[kind="secondary"]:hover, [data-testid="stDownloadButton"] button:hover {{border-color:#19C3B3!important;background:rgba(25,195,179,.1)!important}}
[data-baseweb="select"] > div {{border-radius:999px!important}}
[data-baseweb="select"] > div:hover {{border-color:#19C3B3!important}}
.st-key-qc_panel, .st-key-connect_panel {{border-radius:28px!important;padding:1.4rem 1.6rem 0!important;overflow:hidden;background:linear-gradient(180deg,rgba(25,195,179,.10),rgba(16,24,33,.9) 55%)!important;box-shadow:0 0 0 1px rgba(25,195,179,.28),0 34px 80px -34px rgba(25,195,179,.5)}}
.st-key-qc_panel [data-testid="stHeading"], .st-key-qc_panel [data-testid="stCaptionContainer"], .st-key-connect_panel [data-testid="stCaptionContainer"] {{text-align:center!important}}
.st-key-qc_panel [data-testid="stHeading"], .st-key-qc_panel [data-testid="stHeading"] > * {{display:flex;justify-content:center;width:100%}}
.st-key-qc_panel [data-testid="stFormSubmitButton"], .st-key-qc_panel [data-testid="stFormSubmitButton"] > div {{display:flex;justify-content:center;width:100%}}
.st-key-qc_panel [data-testid="stElementContainer"]:has([data-testid="stFormSubmitButton"]) {{width:100%!important;display:flex;justify-content:center}}
.st-key-qc_panel [data-testid="stFormSubmitButton"] button {{font-size:1.05rem;padding:.7rem 2.6rem!important}}
.ci-wave {{height:64px;margin:1rem -1.6rem 0;background:repeating-linear-gradient(90deg,rgba(25,195,179,.65) 0 3px,transparent 3px 9px);-webkit-mask-image:linear-gradient(to top,#000,transparent);mask-image:linear-gradient(to top,#000,transparent);opacity:.7}}
[data-testid="stMetric"] {{padding:.6rem .4rem}}
[data-testid="stMetricValue"] {{font-weight:800}}
[data-testid="stSidebar"] [data-baseweb="radio"] > div:first-child, [data-testid="stSidebar"] label[data-testid="stRadioOption"] > div > div:first-child {{display:none!important}}
[data-testid="stSidebar"] [role="radiogroup"] {{gap:.4rem}}
[data-testid="stSidebar"] [role="radiogroup"] label {{padding:.7rem 1rem;border-radius:14px;border:1px solid rgba(128,128,128,.22);background:rgba(255,255,255,.02);transition:background .15s,border-color .15s,transform .15s,box-shadow .15s;cursor:pointer}}
[data-testid="stSidebar"] [role="radiogroup"] label:hover {{border-color:rgba(25,195,179,.6);background:rgba(25,195,179,.08);transform:translateX({'4px' if not RTL else '-4px'})}}
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) {{background:linear-gradient(135deg,#2EE6D3,#19C3B3 60%,#12A4C4);border-color:transparent;box-shadow:0 10px 24px -10px rgba(25,195,179,.8)}}
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) * {{color:#031A18!important;font-weight:700}}
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:focus-visible) {{outline:3px solid #5EEAD4;outline-offset:2px}}
@media (max-width: 640px) {{.st-key-hero h1 {{font-size:2.1rem!important}} .st-key-qc_panel {{padding:1rem 1rem 0!important}} .ci-wave {{margin:1rem -1rem 0}}}}
@media (max-width: 640px) {{.block-container {{padding:1.2rem .9rem}} h1 {{font-size:1.9rem!important}}
[data-testid="stHorizontalBlock"] {{flex-wrap:wrap!important;gap:.6rem!important}}
[data-testid="stColumn"] {{min-width:100%!important;flex:1 1 100%!important}}
[data-testid="stColumn"]:has([data-testid="stMetric"]) {{min-width:calc(50% - .4rem)!important;flex:1 1 calc(50% - .4rem)!important}}
[data-testid="stMetricValue"] {{font-size:1.7rem!important}}}}
@media (prefers-reduced-motion: reduce) {{* {{animation:none!important;transition:none!important}}}}
</style>""")


def choose_palette():
    st.session_state.primary, st.session_state.secondary = PALETTES[st.session_state.palette]


def sync_types():
    st.session_state.types = st.session_state.types_en


def reset_filters():
    st.session_state.types = list(POST_TYPES)
    st.session_state.pop("types_en", None)
    st.session_state.months = (1, 12)
    st.session_state.paid = "הכל"


@st.cache_data(ttl=300, max_entries=4, show_spinner=False)
def cached_local(signature):
    return load_local()


def open_store():
    """Encrypted per-user storage, or None when it isn't switched on."""
    try:
        return UserStore.from_config(storage_values)
    except StorageError:
        return None


# OAuth return: the platform redirects back here with ?code=...&state=...
_query = st.query_params
if "state" in _query and ("code" in _query or "error" in _query):
    _code, _state, _denied = _query.get("code"), _query.get("state"), "error" in _query
    st.query_params.clear()
    st.session_state.page = "חיבור חשבון"
    st.session_state.pop("social_error", None)
    _platform = consume_state(_state)
    if _denied:
        st.session_state.social_error = T("החיבור בוטל בפלטפורמה.", "The connection was cancelled on the platform.")
    elif not _platform or not _code:
        st.session_state.social_error = T("קישור החיבור פג תוקף או אינו תקין. התחילו שוב.", "The sign-in link expired or isn't valid. Please start again.")
    else:
        try:
            with st.spinner(T("מתחברים…", "Connecting…")):
                _config = social_config(_platform, social_values)
                _token = exchange_code(_platform, _config, _code)
                _name, _videos, _account = fetch_videos(_platform, _token)
            _user_key, _store = None, open_store()
            if _store and _account:
                try:
                    _user_key = _store.user_key(_platform, _account)
                    _store.save_snapshot(_user_key, _platform, _name, _videos)
                except (StorageError, OSError, sqlite3.Error):
                    _user_key = None
            st.session_state.social = {"platform": _platform, "token": _token, "name": _name, "videos": _videos, "user_key": _user_key}
        except (SocialError, AttributeError) as exc:
            st.session_state.social_error = redact_secrets(exc, social_values)


with st.sidebar:
    logo = urllib.parse.quote(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 40"><polygon points="20,3 4,35 20,25" fill="{primary}"/><polygon points="20,3 36,35 20,25" fill="{secondary}" opacity=".6"/><polygon points="4,35 36,35 20,25" fill="#5EEAD4"/></svg>')
    st.html(f"""<div class="ci-brand"><img src="data:image/svg+xml,{logo}" alt="" width="34" height="34"><div><b>Creator Insights</b><span>{T('אנליטיקה ליוצרי תוכן', 'Analytics for content creators')}</span></div></div>""")
    page = st.radio(T("ניווט", "Navigation"), list(PAGE_LABELS), format_func=lambda p: PAGE_LABELS[p][0] + "  " + PAGE_LABELS[p][1 if RTL else 2], key="page", label_visibility="collapsed")
    st.segmented_control(T("שפה", "Language"), ["he", "en"], format_func=lambda v: "עברית" if v == "he" else "English", key="lang", required=True)
    if not DEMO:
        st.button(T("יציאה", "Sign out"), icon=":material/logout:", on_click=st.session_state.clear)

source = st.session_state.get("source_choice", "תוצרים מקומיים")
primary, secondary = st.session_state.primary, st.session_state.secondary
store = None
store_error = None
try:
    settings = None if DEMO else get_config(secret_values)
    store = SupabaseStore(settings) if settings else None
except StoreError as exc:
    store_error = str(exc)

headings = {
    "סקירה": (T("מה כדאי לפרסם?", "What should you post?"), T("בחרו, לחצו ״בדיקה״ וראו איך פוסטים דומים הצליחו.", "Choose, press Check and see how similar posts did.")),
    "חיבור חשבון": (T("חיבור חשבון", "Connect your account"), T("בחרו סרטון מ-Instagram או TikTok, והאפליקציה תנתח אותו.", "Pick a video from Instagram or TikTok and the app analyses it.")),
    "עוד": (T("עוד", "More"), T("גרפים מפורטים, תחזיות, דוחות והגדרות.", "Detailed charts, forecasts, reports and settings.")),
}
if DEMO:
    st.info(T("הדגמה ציבורית לקריאה בלבד. הרצה מלאה זמינה מקומית (ראו README).", "Read-only public demo. Full runs are available locally (see the README)."), icon=":material/visibility:")
with st.container(key="hero" if page == "סקירה" else "title_block"):
    st.title(headings[page][0], text_alignment="center" if page == "סקירה" else ("right" if RTL else "left"))
    st.caption(headings[page][1], text_alignment="center" if page == "סקירה" else ("right" if RTL else "left"))

frame, training, reports, updated = None, None, {}, None
load_error = None
try:
    with st.spinner(T("טוענים את הנתונים…", "Loading your data…")):
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

if page == "עוד":
    with st.container(horizontal=True, horizontal_alignment="right" if RTL else "left", vertical_alignment="center"):
        st.badge(T("תמונת מצב מהענן", "Cloud snapshot") if source == "Supabase" else T("תוצאות שמורות", "Saved results"), icon=":material/cloud:" if source == "Supabase" else ":material/folder:", color="blue")
        if updated:
            st.caption(T("עודכן ", "Updated ") + str(updated)[:16].replace("T", " · "))
        if st.button(T("רענון נתונים", "Refresh data"), icon=":material/refresh:", key="refresh"):
            cached_local.clear()
            st.session_state.pop("cloud_snapshot", None)
            st.rerun()

history = flow_history()
if source == "תוצרים מקומיים" and history and history[0].get("status") != "completed":
    st.warning(T("הריצה המקומית האחרונה לא הושלמה. ייתכן שמוצגים תוצרים מריצות שונות. פרטים במסך הניהול.", "The last local run did not finish, so results from different runs may be mixed. See Admin for details."))
if load_error and page != "עוד":
    st.warning(T("לא ניתן להציג את מקור הנתונים שנבחר: ", "The selected data source can't be displayed: ") + load_error)
    st.info(T("אפשר לבחור תוצאות שמורות בתפריט הצד, או להיכנס לניהול כדי להגדיר חיבור ולהפעיל את התהליך.", "Choose saved results in the sidebar, or open Admin to set up a connection and run the process."))
    st.stop()


def chart_style(chart):
    return chart.configure_view(strokeWidth=0).configure_axis(gridOpacity=.12, labelFontSize=12, titleFontSize=12, domain=False).configure_legend(title=None)


def type_chart(data):
    data = summarize(data).assign(label=lambda d: d.post_type.map(type_name))
    chart = alt.Chart(data).mark_bar(cornerRadiusEnd=6, height=25).encode(
        x=alt.X("median_interactions:Q", title=T("חציון אינטראקציות", "Median interactions")),
        y=alt.Y("label:N", sort="-x", title=None),
        color=alt.Color("post_type:N", scale=alt.Scale(domain=list(POST_TYPES), range=[primary, secondary, "#D19134", "#A181CD"]), legend=None),
        tooltip=[alt.Tooltip("label:N", title=T("סוג תוכן", "Content type")), alt.Tooltip("post_count:Q", title=T("פוסטים", "Posts")), alt.Tooltip("median_interactions:Q", title=T("חציון", "Median"), format=",.1f")],
    ).properties(height=245)
    st.altair_chart(chart_style(chart), alt=T("חציון אינטראקציות לפי סוג תוכן ומספר הפוסטים בכל קבוצה", "Median interactions by content type, with the number of posts in each group"))


def remember_source():
    st.session_state.source_choice = st.session_state.source


def render_filters():
    with st.expander(T("סינון", "Filter"), icon=":material/filter_list:"):
        if RTL:
            st.multiselect("סוגי תוכן", list(POST_TYPES), format_func=type_name, key="types", persist_state="session")
        else:
            # The browser caches option labels per widget id, so English uses its own widget kept in sync.
            st.session_state["types_en"] = st.session_state.types
            st.multiselect("Content types", list(POST_TYPES), format_func=type_name, key="types_en", on_change=sync_types)
        st.slider(T("חודשי פרסום", "Publishing months"), 1, 12, key="months", persist_state="session")
        st.segmented_control(T("קידום", "Promotion"), ["הכל", "אורגני", "ממומן"], format_func=lambda v: v if RTL else PAID_EN[v], required=True, key="paid", persist_state="session")
        st.button(T("איפוס מסננים", "Reset filters"), icon=":material/restart_alt:", on_click=reset_filters, width="stretch")


def render_home():
    with st.container(border=True, key="qc_panel"):
        with st.form("quick_check", border=False):
            f1, f2, f3 = st.columns(3)
            qt = f1.selectbox(T("סוג תוכן", "Content type"), list(POST_TYPES), format_func=type_name, key=f"qc_type_{LANG}")
            qh = f2.selectbox(T("שעת פרסום", "Posting hour"), list(range(24)), index=10, format_func=lambda h: f"{h:02d}:00", key=f"qc_hour_{LANG}")
            qp = f3.selectbox(T("קידום", "Promotion"), ["אורגני", "ממומן"], format_func=lambda v: v if RTL else PAID_EN[v], key=f"qc_paid_{LANG}")
            go = st.form_submit_button(T("בדיקה", "Check"), icon=":material/play_arrow:", type="primary")
        if go:
            similar = frame[(frame.post_type == qt) & (frame.paid == (1 if qp == "ממומן" else 0))]
            near = similar[similar.post_hour.between(qh - 3, qh + 3)]
            used = near if len(near) >= 8 else similar
            if used.empty:
                st.info(T("אין בנתונים פוסטים דומים לבחירה הזאת. נסו סוג תוכן או קידום אחר.", "There are no similar posts for this choice. Try another content type or promotion."))
            else:
                typical = used.total_interactions.median()
                overall = frame.total_interactions.median()
                r1, r2, r3 = st.columns(3)
                r1.metric(T("תוצאה אופיינית", "Typical result"), f"{typical:,.0f}")
                r2.metric(T("רוב הפוסטים", "Most posts"), f"\u2066{used.total_interactions.quantile(.25):,.0f}–{used.total_interactions.quantile(.75):,.0f}\u2069")
                r3.metric(T("פוסטים דומים", "Similar posts"), f"{len(used):,}")
                st.caption(T("לעומת כל הפוסטים: ", "Compared with all posts: ") + f"\u2066{typical / overall - 1:+.0%}\u2069. " + T("מבוסס על פוסטים דומים בעבר. זו לא תחזית ואין בה הבטחה.", "Based on similar past posts. This is not a forecast or a promise.") + ("" if used is near else T(" השעה לא נלקחה בחשבון כי יש מעט פוסטים בה.", " The hour was ignored because there are few posts near it.")) + (T(" מעט פוסטים, אז התוצאה פחות אמינה.", " Few posts, so treat this with care.") if len(used) < 15 else ""))
        st.html('<div class="ci-wave" aria-hidden="true"></div>')
    c = st.columns(2, gap="small")
    c[0].metric(T("פוסטים שנבדקו", "Posts checked"), f"{len(frame):,}", border=True)
    c[1].metric(T("סך אינטראקציות", "Total interactions"), f"{frame.total_interactions.sum():,}", border=True)
    top = summarize(frame).iloc[0]
    st.caption(T(f"{type_name(top.post_type)} הוא סוג התוכן שהצליח הכי הרבה בנתונים.", f"{type_name(top.post_type)} did best across all the posts in the data."))


def render_charts():
    if frame is None:
        return
    render_filters()
    filtered = filter_posts(frame, st.session_state.types, st.session_state.months, st.session_state.paid)
    paid_label = st.session_state.paid if RTL else PAID_EN[st.session_state.paid]
    st.caption(T(f"{len(filtered):,} מתוך {len(frame):,} פוסטים · חודשים {st.session_state.months[0]}–{st.session_state.months[1]} · {paid_label}", f"{len(filtered):,} of {len(frame):,} posts · months {st.session_state.months[0]}–{st.session_state.months[1]} · {paid_label}"))
    if filtered.empty:
        st.info(T("אין פוסטים שמתאימים לסינון. נסו להרחיב את טווח החודשים או לבחור סוגי תוכן נוספים.", "No posts match these filters. Try a wider month range or more content types."))
        st.button(T("הצגת כל הפוסטים", "Show all posts"), on_click=reset_filters, type="primary")
        return
    grouped = summarize(filtered)
    leader = grouped.iloc[0]
    kpis = st.columns(4, gap="small")
    kpis[0].metric(T("פוסטים בניתוח", "Posts analysed"), f"{len(filtered):,}", border=True)
    kpis[1].metric(T("סך אינטראקציות", "Total interactions"), f"{filtered.total_interactions.sum():,}", border=True)
    kpis[2].metric(T("חציון לפוסט", "Median per post"), f"{filtered.total_interactions.median():,.1f}", help=T("מחצית מהפוסטים קיבלו יותר מהערך הזה, ומחצית פחות.", "Half the posts got more than this, half got less."), border=True)
    kpis[3].metric(T("סוג התוכן המוביל", "Top content type"), type_name(leader.post_type), border=True)

    left, right = st.columns(2, gap="medium")
    with left.container(border=True):
        st.subheader(T("איזה תוכן מוביל באינטראקציות?", "Which content leads on interactions?"), text_alignment="right" if RTL else "left")
        st.caption(T("השוואת חציון אינטראקציות לכל פוסט", "Median interactions per post, by content type"))
        type_chart(filtered)
    with right.container(border=True):
        st.subheader(T("ביצועים לאורך השנה", "Performance through the year"), text_alignment="right" if RTL else "left")
        st.caption(T("חציון חודשי · לפי חודש הפרסום במאגר", "Monthly median · by publishing month"))
        monthly = filtered.groupby("post_month").agg(value=("total_interactions", "median"), count=("total_interactions", "size")).reset_index()
        chart = alt.Chart(monthly).mark_area(color=primary, opacity=.16, line={"color": primary, "strokeWidth": 3}, point={"filled": True, "fill": primary, "size": 55}).encode(
            x=alt.X("post_month:O", title=T("חודש", "Month"), sort="ascending"), y=alt.Y("value:Q", title=T("חציון אינטראקציות", "Median interactions")),
            tooltip=[alt.Tooltip("post_month:O", title=T("חודש", "Month")), alt.Tooltip("value:Q", title=T("חציון", "Median"), format=",.1f"), alt.Tooltip("count:Q", title=T("פוסטים", "Posts"))],
        ).properties(height=245)
        st.altair_chart(chart_style(chart), alt=T("חציון אינטראקציות לכל חודש פרסום, לפי המסננים", "Median interactions per publishing month, for the current filters"))
    with st.container(border=True):
        st.subheader(T("מתי פורסם התוכן?", "When was it posted?"), text_alignment="right" if RTL else "left")
        hourly = filtered.groupby("post_hour").agg(median=("total_interactions", "median"), count=("total_interactions", "size")).reset_index()
        chart = alt.Chart(hourly).mark_bar(color=secondary, cornerRadiusTopLeft=4, cornerRadiusTopRight=4).encode(
            x=alt.X("post_hour:O", title=T("שעת פרסום", "Hour posted"), sort="ascending"), y=alt.Y("median:Q", title=T("חציון אינטראקציות", "Median interactions")),
            tooltip=[alt.Tooltip("post_hour:O", title=T("שעה", "Hour")), alt.Tooltip("median:Q", title=T("חציון", "Median")), alt.Tooltip("count:Q", title=T("פוסטים", "Posts"))],
        ).properties(height=245)
        st.altair_chart(chart_style(chart), alt=T("חציון אינטראקציות לפי שעת פרסום", "Median interactions by posting hour"))
    st.caption(T(f"{type_name(leader.post_type)} מוביל בסינון הנוכחי: חציון {leader.median_interactions:,.1f} על בסיס {int(leader.post_count)} פוסטים. זה קשר תיאורי, לא הוכחה.", f"{type_name(leader.post_type)} leads for the current filters: median {leader.median_interactions:,.1f} across {int(leader.post_count)} posts. This describes a pattern; it doesn't prove cause."))
    st.subheader(T("הנתונים שלך, מקרוב", "Your data, up close"), text_alignment="right" if RTL else "left")
    st.caption(T("הטבלה וההורדה משקפות את המסננים. ניתן למיין לפי כותרות העמודות.", "The table and the download follow your filters. Click a header to sort."))
    display = filtered.assign(post_type=filtered.post_type.map(type_name), paid=filtered.paid.map({1: T("ממומן", "Paid"), 0: T("אורגני", "Organic")})).rename(columns={
        "post_type": T("סוג תוכן", "Content type"), "category": T("קטגוריה", "Category"), "post_month": T("חודש", "Month"),
        "post_weekday": T("יום בשבוע (1–7)", "Weekday (1–7)"), "post_hour": T("שעה", "Hour"), "paid": T("קידום", "Promotion"), "total_interactions": T("אינטראקציות", "Interactions")})
    st.dataframe(display, hide_index=True, height=380, alt=T("הפוסטים המתאימים למסננים", "Posts matching the filters"))
    st.download_button(T("הורדת הנתונים המסוננים", "Download filtered data"), filtered.to_csv(index=False).encode("utf-8-sig"), "creator-insights-filtered.csv", "text/csv", icon=":material/download:")


def render_lab():
    if not training:
        st.info(T("תוצאות התחזיות עדיין לא זמינות. הפעילו את התהליך המלא ממסך הניהול.", "Forecast results aren't available yet. Run the full process from Admin."))
        return
    st.caption(T("תוצאות הניסוי המלא · המסננים אינם משנים את הניסוי", "Full experiment results · filters don't change the experiment"))
    st.info(T("זהו ניסוי לימודי בנתונים היסטוריים מדף Facebook אחד. החלוקה האקראית אינה בודקת חיזוי עתידי, וסט הבדיקה נצפה במהלך הפיתוח. התוצאות אינן הבטחה לדיוק בחשבונות אחרים.", "This is a study experiment on historical data from a single Facebook page. The random split does not test future prediction, and the test set was seen during development. The results do not promise accuracy for other accounts."))
    try:
        result = training["test_results"]
        baseline, selected = float(result["baseline_mae"]), float(result["selected_model_mae"])
        kp = st.columns(4, gap="small")
        kp[0].metric(T("שגיאה ממוצעת · קו בסיס", "Average error · baseline"), f"{baseline:.2f}", border=True)
        kp[1].metric(T("שגיאה ממוצעת · התחזית שנבחרה", "Average error · chosen forecast"), f"{selected:.2f}", delta=f"{selected-baseline:+.2f}", delta_color="inverse", delta_description=T("אינטראקציות לעומת קו הבסיס", "interactions vs. baseline"), border=True)
        kp[2].metric(T("פוסטים באימון", "Training posts"), training["training_rows"], border=True)
        kp[3].metric(T("פוסטים בבדיקה", "Test posts"), training["test_rows"], border=True)
        if selected < baseline:
            st.success(T("התחזית עברה את קו הבסיס בחלוקה שנבדקה. עדיין נדרש אימות על נתונים חדשים.", "The forecast beat the baseline on the tested split. It still needs checking on new data."))
        else:
            st.warning(T("המודל עדיין לא עבר את קו הבסיס. בניסוי הזה, חיזוי חציון קבוע מדויק יותר.", "The forecast did not beat the baseline. In this experiment, predicting a constant median is more accurate."))
        with st.container(border=True):
            st.subheader(T("השוואת התחזיות", "Forecast comparison"), text_alignment="right" if RTL else "left")
            cv = pd.DataFrame(training["cross_validation"])
            names = list(cv["model"])
            st.caption(T(f"נבחרה: {model_name(training['selected_model'], names)} · בדיקה חוזרת בחמש חלוקות של נתוני האימון", f"Chosen: {model_name(training['selected_model'], names)} · checked on five splits of the training data"))
            cv = cv.assign(model=cv["model"].map(lambda n: model_name(n, names)))
            chart = alt.Chart(cv).mark_bar(color=primary, cornerRadiusEnd=5, height=28).encode(
                x=alt.X("cv_mae_mean:Q", title=T("שגיאה ממוצעת · נמוך יותר עדיף", "Average error · lower is better")), y=alt.Y("model:N", sort="x", title=None),
                tooltip=[alt.Tooltip("model:N", title=T("תחזית", "Forecast")), alt.Tooltip("cv_mae_mean:Q", title=T("שגיאה", "Error"), format=".2f"), alt.Tooltip("cv_mae_std:Q", title=T("סטיית תקן", "Std. dev."), format=".2f")],
            ).properties(height=210)
            st.altair_chart(chart_style(chart), alt=T("שגיאת הבדיקה החוזרת של שלוש התחזיות", "Repeated-check error of the three forecasts"))
            st.dataframe(cv.rename(columns={"model": T("תחזית", "Forecast"), "cv_mae_mean": T("שגיאה ממוצעת", "Average error"), "cv_mae_std": T("סטיית תקן", "Std. dev.")}).round(2), hide_index=True, alt=T("שגיאה וסטיית תקן לכל תחזית", "Error and standard deviation for each forecast"))
        st.caption(T("שגיאה ממוצעת היא גודל הטעות הממוצע של התחזית, באינטראקציות. הבדיקה החוזרת משמשת לבחירה, וקבוצת הבדיקה להערכה נפרדת. אין להשוות את המספרים כאילו נמדדו על אותם פוסטים.", "Average error is the typical size of the forecast's mistake, in interactions. The repeated check is used to choose; the test set is a separate evaluation. Don't compare the numbers as if they were measured on the same posts."))
    except (KeyError, TypeError, ValueError):
        st.error(T("סיכום התחזיות אינו במבנה הצפוי. יש לייצר מחדש את תוצרי התהליך.", "The forecast summary isn't in the expected format. Re-run the process to regenerate it."))


def render_reports():
    chosen = st.selectbox(T("בחירת דוח", "Choose a report"), list(REPORTS), format_func=lambda k: REPORTS[k] if RTL else REPORT_EN.get(k, k))
    if chosen in reports:
        st.download_button(T("הורדת הדוח", "Download report"), reports[chosen], chosen, "text/markdown", icon=":material/download:")
        with st.container(border=True):
            st.markdown(reports[chosen])
    else:
        st.info(T("הדוח הזה עדיין לא נוצר במקור הנתונים שנבחר.", "This report hasn't been created for the selected source yet."))


def render_connect():
    social = st.session_state.get("social")
    names = {"instagram": "Instagram", "tiktok": "TikTok"}
    platform = st.segmented_control(T("פלטפורמה", "Platform"), list(PLATFORMS), format_func=names.get, default=(social or {}).get("platform", "instagram"), required=True, key="connect_platform")
    if st.session_state.get("social_error"):
        st.error(st.session_state.social_error)
    if social and social["platform"] == platform:
        videos = social["videos"]
        with st.container(horizontal=True, vertical_alignment="center"):
            st.badge(T("מחובר: ", "Connected: ") + social["name"], icon=":material/check_circle:", color="green")
            if st.button(T("ניתוק", "Disconnect"), icon=":material/link_off:", key="disconnect"):
                st.session_state.pop("social", None)
                st.session_state.pop("social_error", None)
                st.rerun()
        user_store = open_store() if social.get("user_key") else None
        if user_store:
            with st.container(border=True):
                st.caption(T("הנתונים שלך נשמרים מוצפנים ומופרדים לחלוטין משאר המשתמשים. אף אחד אחר לא יכול לראות אותם.", "Your data is stored encrypted and kept completely separate from other users. Nobody else can see it."))
                try:
                    history = user_store.snapshots(social["user_key"], limit=5)
                except (StorageError, OSError, sqlite3.Error):
                    history = []
                if history:
                    rows = [{T("תאריך", "Saved"): h["taken_at"][:16].replace("T", " "), T("סרטונים", "Videos"): len(h["videos"]),
                             T("אינטראקציות", "Interactions"): int(sum((v.get("likes") or 0) + (v.get("comments") or 0) + (v.get("shares") or 0) for v in h["videos"]))} for h in history]
                    st.dataframe(pd.DataFrame(rows), hide_index=True, alt=T("שמירות קודמות של החשבון שלך", "Earlier saves of your account"))
                if st.button(T("מחיקת הנתונים שלי", "Delete my data"), icon=":material/delete:", key="delete_my_data"):
                    user_store.delete_user(social["user_key"])
                    social["user_key"] = None
                    st.success(T("הנתונים שלך נמחקו.", "Your data was deleted."))
        if videos.empty:
            st.info(T("לא נמצאו סרטונים בחשבון. פרסמו סרטון ונסו שוב.", "No videos were found on this account. Post a video and try again."))
            return
        labels = {i: f"{row.created:%Y-%m-%d} · {(row.title or T('ללא כיתוב', 'No caption'))[:48]}" for i, row in videos.iterrows()}
        pick = st.selectbox(T("בחרו סרטון", "Choose a video"), list(labels), format_func=labels.get, key=f"video_pick_{LANG}")
        video = videos.loc[pick]
        result = analyze_video(video, videos, frame)
        m = st.columns(4, gap="small")
        m[0].metric(T("אינטראקציות", "Interactions"), f"{result['interactions']:,.0f}", border=True)
        m[1].metric(T("לייקים", "Likes"), f"{video.likes:,.0f}" if pd.notna(video.likes) else "–", border=True)
        m[2].metric(T("תגובות", "Comments"), f"{video.comments:,.0f}" if pd.notna(video.comments) else "–", border=True)
        m[3].metric(T("צפיות", "Views"), f"{video.views:,.0f}" if pd.notna(video.views) else T("לא זמין", "n/a"), border=True)
        lines = [T(f"מקום {result['rank']} מתוך {result['count']} הסרטונים האחרונים בחשבון.", f"Ranked {result['rank']} of your {result['count']} latest videos.")]
        if result["vs_account_median"] is not None:
            lines.append(T("לעומת החציון בחשבון שלך: ", "Versus your account median: ") + f"\u2066{result['vs_account_median']:+.0%}\u2069.")
        if result["vs_reference_median"] is not None:
            lines.append(T("לעומת החציון בנתוני המחקר (עמוד Facebook אחד): ", "Versus the study data median (one Facebook page): ") + f"\u2066{result['vs_reference_median']:+.0%}\u2069.")
        if "best_hour" in result:
            lines.append(T(f"בסרטונים שלך, השעה החזקה ביותר היא {result['best_hour']:02d}:00 (לפי שעון UTC).", f"Across your videos, your strongest posting hour is {result['best_hour']:02d}:00 (UTC)."))
        with st.container(border=True):
            st.subheader(T("מה האפליקציה מצאה", "What the app found"), icon=":material/analytics:", text_alignment="right" if RTL else "left")
            for line in lines:
                st.markdown("- " + line)
            st.caption(T("זה תיאור של מה שקרה, לא תחזית. הנתונים מושווים לנתוני מחקר ישנים מפלטפורמה אחרת, ולכן ההשוואה מוגבלת.", "This describes what happened; it isn't a forecast. The comparison uses older study data from another platform, so it is limited."))
        chart_data = videos.assign(interactions=videos.apply(interactions, axis=1), label=videos.created.dt.strftime("%m-%d"))
        chart = alt.Chart(chart_data).mark_bar(color=primary, cornerRadiusEnd=5).encode(
            x=alt.X("label:N", sort=None, title=T("תאריך פרסום", "Posted")), y=alt.Y("interactions:Q", title=T("אינטראקציות", "Interactions")),
            tooltip=[alt.Tooltip("title:N", title=T("כיתוב", "Caption")), alt.Tooltip("interactions:Q", title=T("אינטראקציות", "Interactions"), format=",.0f")]).properties(height=240)
        with st.container(border=True):
            st.subheader(T("הסרטונים האחרונים שלך", "Your latest videos"), text_alignment="right" if RTL else "left")
            st.altair_chart(chart_style(chart), alt=T("אינטראקציות לכל אחד מהסרטונים האחרונים", "Interactions for each of your latest videos"))
        if pd.notna(video.url) and video.url:
            st.link_button(T("פתיחת הסרטון בפלטפורמה", "Open the video on the platform"), video.url, icon=":material/open_in_new:")
    else:
        try:
            config = social_config(platform, social_values)
            config_error = None
        except SocialError as exc:
            config, config_error = None, str(exc)
        if config_error:
            st.error(config_error)
        if config:
            state_key = f"oauth_state_{platform}"
            if not is_pending(st.session_state.get(state_key, "")):
                st.session_state[state_key] = new_state(platform)
            with st.container(border=True, key="connect_panel"):
                st.subheader(T(f"התחברות ל-{names[platform]}", f"Connect {names[platform]}"), icon=":material/link:", text_alignment="center")
                st.caption(T("תועברו לאישור בפלטפורמה. האפליקציה קוראת את הסרטונים והמדדים שלהם בלבד ולא מפרסמת דבר. הגישה נשמרת רק בזמן הביקור.", "You'll approve access on the platform. The app only reads your videos and their stats and never posts. Access lasts only for this visit."))
                st.link_button(T(f"התחברות עם {names[platform]}", f"Continue with {names[platform]}"), auth_url(platform, config, st.session_state[state_key]), type="primary", icon=":material/login:", width="stretch")
        elif not config_error:
            with st.container(border=True, key="connect_panel"):
                st.subheader(T(f"חיבור {names[platform]} יהיה זמין בקרוב", f"{names[platform]} sign-in is coming soon"), icon=":material/schedule:", text_alignment="center")
                st.caption(T("החיבור עדיין לא הופעל באפליקציה הזאת. בינתיים אפשר לנסות את הבדיקה המהירה בדף הבית.", "Sign-in isn't switched on in this app yet. Meanwhile, try the quick check on the Home page."))
                st.button(T(f"התחברות עם {names[platform]}", f"Continue with {names[platform]}"), disabled=True, width="stretch", key="connect_disabled")
            if not DEMO:
                # Owner-only: visitors never see developer setup; they just click the sign-in button once it's on.
                steps = {
                    "instagram": T("1. ב-developers.facebook.com צרו אפליקציה והוסיפו Instagram API with Instagram Login.\n2. הוסיפו את כתובת האפליקציה כ-Redirect URI.\n3. שמרו ב-Secrets את `INSTAGRAM_APP_ID` ו-`INSTAGRAM_APP_SECRET`.\n4. שמרו גם `OAUTH_REDIRECT_URI` עם כתובת האפליקציה. החשבון צריך להיות עסקי או יוצר.", "1. At developers.facebook.com create an app and add Instagram API with Instagram Login.\n2. Add this app's address as a Redirect URI.\n3. Save `INSTAGRAM_APP_ID` and `INSTAGRAM_APP_SECRET` in Secrets.\n4. Also save `OAUTH_REDIRECT_URI` with this app's address. The account must be a Business or Creator account."),
                    "tiktok": T("1. ב-developers.tiktok.com צרו אפליקציה והפעילו Login Kit ואת ההרשאות user.info.basic ו-video.list.\n2. הוסיפו את כתובת האפליקציה כ-Redirect URI.\n3. שמרו ב-Secrets את `TIKTOK_CLIENT_KEY` ו-`TIKTOK_CLIENT_SECRET`.\n4. שמרו גם `OAUTH_REDIRECT_URI` עם כתובת האפליקציה. TikTok צריכה לאשר את האפליקציה לפני שחשבונות אחרים יוכלו להתחבר.", "1. At developers.tiktok.com create an app and enable Login Kit with the user.info.basic and video.list scopes.\n2. Add this app's address as a Redirect URI.\n3. Save `TIKTOK_CLIENT_KEY` and `TIKTOK_CLIENT_SECRET` in Secrets.\n4. Also save `OAUTH_REDIRECT_URI` with this app's address. TikTok must approve the app before other accounts can sign in."),
                }
                with st.expander(T("למנהל המערכת: הפעלת החיבור", "For the owner: switch sign-in on"), expanded=False, icon=":material/checklist:"):
                    st.markdown(steps[platform])
                    st.caption(T("הסודות נשארים בשרת ואינם מוצגים בדפדפן.", "The secrets stay on the server and are never shown in the browser."))



def render_settings():
    with st.expander(T("מקור ועיצוב", "Source & appearance"), icon=":material/tune:"):
        source = st.selectbox(T("מקור נתונים", "Data source"), ["תוצרים מקומיים"] if DEMO else ["תוצרים מקומיים", "Supabase"], format_func=lambda v: v if RTL else {"תוצרים מקומיים": "Saved results", "Supabase": "Cloud snapshot"}[v], key="source", index=0 if DEMO else ["תוצרים מקומיים", "Supabase"].index(st.session_state.get("source_choice", "תוצרים מקומיים")), on_change=remember_source, label_visibility="collapsed")
        st.selectbox(T("ערכת צבעים", "Palette"), list(PALETTES), key="palette", on_change=choose_palette, persist_state="session")
        st.color_picker(T("צבע ראשי", "Primary color"), key="primary", persist_state="session")
        st.color_picker(T("צבע משני", "Secondary color"), key="secondary", persist_state="session")
        st.toggle(T("מצב כהה", "Dark mode"), key="dark", persist_state="session")
        st.caption(T("הגרפים מציגים את הצבעים מיד. שמירה מחילה את העיצוב על סביבת העבודה המקומית ושומרת אותו לפתיחה הבאה.", "Charts update instantly. Saving applies the look to this local workspace."))
        if not DEMO and st.button(T("שמירת העיצוב", "Save appearance"), icon=":material/check:", width="stretch"):
            try:
                theme_config = build_theme(config, st.session_state.primary, st.session_state.secondary, st.session_state.dark)
                save_theme(theme_config)
                st.success(T("העיצוב נשמר. אם הממשק עדיין לא השתנה, רעננו את הדף.", "Appearance saved. Reload the page if nothing changed."))
            except (OSError, ValueError):
                st.error(T("לא ניתן לשמור את העיצוב. בדקו את הצבעים והרשאות הקובץ.", "Could not save the appearance. Check the colors and file permissions."))
        try:
            theme_config = build_theme(config, st.session_state.primary, st.session_state.secondary, st.session_state.dark)
            st.download_button(T("הורדת ערכת העיצוב", "Download theme"), export_theme(theme_config), "config.toml", "text/plain", icon=":material/download:")
        except ValueError:
            st.caption(T("בחרו צבע ראשי כהה יותר כדי לשמור ערכה נגישה.", "Pick a darker primary color for an accessible theme."))
    left, right = st.columns(2, gap="medium")
    with right.container(border=True):
        st.subheader(T("התהליך המלא", "The full process"), icon=":material/account_tree:", text_alignment="right" if RTL else "left")
        st.markdown(T("**01 · ניתוח** — ניקוי, מחקר וחוזה נתונים\n\n**02 · אימות** — בדיקת החוזה וטביעות הקבצים\n\n**03 · מידול** — אימון, השוואה וביקורת", "**01 · Analysis** — cleaning, research and data contract\n\n**02 · Validation** — contract and file fingerprints\n\n**03 · Forecasting** — training, comparison and review"))
        st.caption(T("ההפעלה משתמשת בשישה סוכני Claude ומעדכנת את התוצרים המקומיים. קריאות API מחויבות לפי השימוש. פתיחת הדשבורד אינה מפעילה אותם.", "Running uses six Claude agents and updates the local results. API calls are billed by usage. Opening the dashboard doesn't trigger them."))
        if DEMO:
            st.info(T("הפעלת התהליך מושבתת בהדגמה הציבורית, כי היא מפעילה קריאות API בתשלום.", "Running the process is disabled in the public demo because it makes paid API calls."))
        elif st.button(T("הפעלת התהליך המלא", "Run the full process"), icon=":material/play_arrow:", type="primary", width="stretch"):
            ARTIFACTS.mkdir(exist_ok=True)
            try:
                with st.status(T("התהליך פועל — ניתוח, אימות ומידול…", "Running — analysis, validation and forecasting…"), expanded=True) as status:
                    st.write(T("ניתן לעיין ביומן ההרצה בסיום. מגבלת זמן: 30 דקות.", "You can review the run log when it ends. Time limit: 30 minutes."))
                    success = run_ui_flow(secret_values=secret_values) == 0
                    status.update(label=T("התהליך הושלם", "Process finished") if success else T("התהליך לא הושלם", "Process did not finish"), state="complete" if success else "error")
                st.session_state.flow_result = T("התהליך הושלם והתוצרים עודכנו.", "The process finished and the results were updated.") if success else T("התהליך נכשל. ייתכן שחלק מהתוצרים ישנים. בדקו את יומן ההרצה.", "The process failed. Some results may be old. Check the run log.")
            except subprocess.TimeoutExpired:
                st.session_state.flow_result = T("ההרצה נעצרה לאחר 30 דקות. ייתכן שחלק מהתוצרים עודכנו.", "The run stopped after 30 minutes. Some results may have been updated.")
            except WorkspaceBusy as exc:
                st.session_state.flow_result = str(exc)
            except OSError:
                st.session_state.flow_result = T("לא ניתן להפעיל את התהליך. בדקו הרשאות וסביבת Python.", "Couldn't start the process. Check permissions and the Python environment.")
            cached_local.clear()
            st.rerun()
        if "flow_result" in st.session_state:
            st.info(st.session_state.flow_result)
        log_path = ARTIFACTS / "latest_ui_run.log"
        if log_path.exists():
            with st.expander(T("יומן ההרצה המקומית האחרונה", "Latest local run log")):
                st.code(read_log_tail(log_path, values=secret_values), language="text")
    with left.container(border=True):
        st.subheader(T("Supabase · הרחבה אופציונלית", "Supabase · optional extension"), icon=":material/cloud:", text_alignment="right" if RTL else "left")
        st.caption(T("אינו נדרש להגשת הפרויקט. שני הצוותים והדשבורד פועלים גם במצב מקומי.", "Not required. Everything also works locally."))
        st.badge(T("מוגדר · טרם נבדק", "Configured · not yet checked") if store else T("מצב מקומי", "Local mode"), color="blue" if store else "gray")
        st.caption(T("שמירת תמונות מצב של הנתונים, תוצאות התחזיות והדוחות. כל תמונת מצב נשמרת בעסקה אחת; סנכרון חוזר של אותו תוכן אינו יוצר כפילות.", "Stores snapshots of the data, forecast results and reports. Each snapshot is saved in one transaction; syncing the same content again creates no duplicates."))
        if store_error:
            st.error(store_error)
        if store:
            if st.button(T("בדיקת חיבור", "Test connection"), icon=":material/wifi:", width="stretch"):
                try:
                    store.check()
                    st.success(T("החיבור למסד נבדק בהצלחה.", "Connection check passed."))
                except StoreError as exc:
                    st.error(str(exc))
            if st.button(T("סנכרון התוצרים המקומיים לענן", "Sync local results to the cloud"), icon=":material/cloud_upload:", width="stretch"):
                try:
                    with st.spinner(T("מאמת ושומר תמונת מצב…", "Validating and saving a snapshot…")):
                        snapshot = build_snapshot()
                        store.sync(snapshot)
                    st.session_state.pop("cloud_snapshot", None)
                    st.success(T(f"נשמרו {snapshot['row_count']} פוסטים, תוצאות התחזיות והדוחות.", f"Saved {snapshot['row_count']} posts, forecast results and reports."))
                except (StoreError, OSError, ValueError, WorkspaceBusy) as exc:
                    st.error(redact_secrets(exc, secret_values))
        else:
            st.info(T("להפעלת הענן: צרו פרויקט Supabase, הפעילו את המיגרציה והגדירו את פרטי החיבור בקובץ ‎.env.", "To enable the cloud: create a Supabase project, apply the migration and set the connection details in the .env file."))
            st.code("SUPABASE_URL=https://PROJECT.supabase.co\nSUPABASE_SECRET_KEY=your_server_secret_key", language="bash")
            st.caption(T("המפתח נשאר בשרת. הוראות מלאות ב־README וב־docs/supabase.md.", "The key stays on the server. Full instructions in the README and docs/supabase.md."))
    st.subheader(T("היסטוריית ריצות מקומיות", "Local run history"), text_alignment="right" if RTL else "left")
    if history:
        labels = {"completed": T("הושלם", "Finished"), "failed": T("נכשל", "Failed"), "analysts_running": T("ניתוח", "Analysis"), "scientists_running": T("מידול", "Forecasting"), "validating": T("אימות", "Validation")}
        for run in history[:10]:
            events = run.get("events", [])
            when = events[-1].get("time", "")[:16].replace("T", " · ") if events else ""
            with st.expander(f"{labels.get(run.get('status'), run.get('status', T('לא ידוע', 'Unknown')))}  ·  {when}  ·  {run.get('id', '')[:8]}"):
                safe_events = [{k: redact_secrets(v, secret_values) for k, v in event.items()} for event in events]
                st.dataframe(pd.DataFrame(safe_events), hide_index=True, alt=T("אירועים מתועדים של הרצת התהליך", "Recorded events of the process run"))
                if run.get("error"):
                    st.error(redact_secrets(run["error"], secret_values))
    else:
        st.caption(T("עדיין אין ריצות מתועדות.", "No recorded runs yet."))

if page == "סקירה":
    render_home()
elif page == "חיבור חשבון":
    render_connect()
else:
    tab_charts, tab_forecasts, tab_reports, tab_settings = st.tabs([T("גרפים", "Charts"), T("תחזיות", "Forecasts"), T("דוחות", "Reports"), T("הגדרות", "Settings")])
    with tab_charts:
        render_charts()
    with tab_forecasts:
        render_lab()
    with tab_reports:
        render_reports()
    with tab_settings:
        render_settings()

st.space("small")
st.caption(T("Creator Insights · מחקר שקוף, החלטות שקולות. נתונים היסטוריים מעמוד Facebook יחיד; הביצועים בחשבונות אחרים ובתקופות עתידיות לא נבדקו.", "Creator Insights · transparent research, considered decisions. Historical data from a single Facebook page; performance on other accounts and future periods hasn't been tested."))
