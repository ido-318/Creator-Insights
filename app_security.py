"""Owner authentication and safe diagnostics for the local research workspace."""
import hashlib
import hmac
import os
from pathlib import Path
import re
import secrets
import stat

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
TOKEN_PATH = ROOT / ".streamlit/access_token"
TOKEN_ENV = "CREATOR_INSIGHTS_ACCESS_TOKEN"
AUTH_STATE = "_authenticated_token_digest"


class SecurityError(RuntimeError):
    """A safe configuration error without secret values."""


def load_access_token(values=None, path=TOKEN_PATH):
    """Use an explicit secret or bootstrap a private, random local access token."""
    load_dotenv(ROOT / ".env")
    token = (values or {}).get(TOKEN_ENV, os.getenv(TOKEN_ENV, ""))
    if not token:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            pass
        else:
            with os.fdopen(fd, "w", encoding="utf-8") as file:
                file.write(secrets.token_urlsafe(32) + "\n")
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
        with os.fdopen(os.open(path, flags), "r", encoding="utf-8") as file:
            info = os.fstat(file.fileno())
            if not stat.S_ISREG(info.st_mode) or (
                os.name == "posix" and (info.st_mode & 0o077 or info.st_uid != os.getuid())
            ):
                raise SecurityError("קובץ קוד הגישה חייב להיות פרטי לבעל הפרויקט (הרשאות 600).")
            token = file.read(258).strip()
    if not isinstance(token, str) or not re.fullmatch(r"[A-Za-z0-9_-]{32,256}", token):
        raise SecurityError("נדרש קוד גישה אקראי באורך 32 תווים לפחות. בדקו את הגדרות האבטחה ב־README.")
    return token


def token_digest(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def authenticate(state, submitted, token):
    """Keep only a fingerprint in session state; never retain the submitted token."""
    state.pop("_access_token_input", None)
    if isinstance(submitted, str) and hmac.compare_digest(submitted.encode(), token.encode()):
        state[AUTH_STATE] = token_digest(token)
        state.pop("_login_failed", None)
    else:
        state.pop(AUTH_STATE, None)
        state.pop("cloud_snapshot", None)
        state["_login_failed"] = True


def require_local_access(st, values=None):
    """Gate the entire app before data loading, configuration exports or actions."""
    if (st.get_option("server.address") not in {"127.0.0.1", "::1", "localhost"}
            or not st.get_option("server.enableCORS")
            or not st.get_option("server.enableXsrfProtection")
            or st.get_option("server.enableStaticServing")):
        st.error("הגישה נחסמה: נדרשת הפעלה מקומית עם הגנות הדפדפן. בדקו את הוראות ההפעלה ב־README.")
        st.stop()
    try:
        token = load_access_token(values)
    except (OSError, ValueError, SecurityError):
        st.error("לא ניתן לאמת את הגדרות הגישה. בדקו את קוד הגישה והרשאות הקובץ לפי README.")
        st.stop()
    if hmac.compare_digest(str(st.session_state.get(AUTH_STATE, "")), token_digest(token)):
        return
    st.session_state.pop(AUTH_STATE, None)
    st.session_state.pop("cloud_snapshot", None)
    st.title("כניסה ל־Creator Insights")
    st.caption("הזינו את קוד הגישה המקומי של בעל הפרויקט. הקוד נשמר בקובץ ‎.streamlit/access_token במחשב זה.")

    def login():
        authenticate(st.session_state, st.session_state.get("_access_token_input", ""), token)

    with st.form("workspace_login"):
        st.text_input("קוד גישה", type="password", key="_access_token_input", max_chars=256)
        st.form_submit_button("כניסה", on_click=login)
    if st.session_state.get("_login_failed"):
        st.error("קוד הגישה אינו נכון.")
    st.stop()


def redact_secrets(value, values=None):
    """Best-effort masking of known credentials and common credential formats."""
    text = str(value)
    candidates = dict(os.environ)
    candidates.update(values or {})
    secret_values = [str(v) for k, v in candidates.items()
                     if v and re.search(r"KEY|TOKEN|SECRET|PASSWORD|COOKIE", k, re.I) and len(str(v)) >= 8]
    for secret in sorted(secret_values, key=len, reverse=True):
        text = text.replace(secret, "[REDACTED]")
    text = re.sub(r"\b(?:sk-ant-|sb_secret_)[A-Za-z0-9_-]+", "[REDACTED]", text)
    text = re.sub(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+", "Bearer [REDACTED]", text)
    return text


def read_log_tail(path, limit=16000, values=None):
    """Bound reads before rendering; mask complete credentials before truncation."""
    with Path(path).open("rb") as file:
        file.seek(0, os.SEEK_END)
        size = file.tell()
        file.seek(max(0, size - limit - 4096))
        data = file.read(limit + 4096)
    if size > limit + 4096:
        # Drop a possibly partial first line (including a split credential).
        data = data.partition(b"\n")[2]
    return redact_secrets(data.decode("utf-8", errors="replace"), values)[-limit:]
