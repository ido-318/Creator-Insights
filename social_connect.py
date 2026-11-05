"""Instagram and TikTok account connection.

OAuth runs on the server: app secrets and access tokens are never sent to the browser,
never written to disk and never logged. Tokens live only in the user's session.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
import os
import secrets
import threading
import time
from urllib.parse import urlencode, urlsplit

import httpx
import pandas as pd

PLATFORMS = ("instagram", "tiktok")
SOCIAL_KEYS = ("INSTAGRAM_APP_ID", "INSTAGRAM_APP_SECRET", "TIKTOK_CLIENT_KEY", "TIKTOK_CLIENT_SECRET", "OAUTH_REDIRECT_URI")
VIDEO_COLUMNS = ["id", "title", "created", "views", "likes", "comments", "shares", "url"]
STATE_TTL = 600
MAX_PENDING = 500
TIMEOUT = httpx.Timeout(15.0)
INSTAGRAM_API = "https://graph.instagram.com/v23.0"
TIKTOK_API = "https://open.tiktokapis.com/v2"

_pending = {}
_lock = threading.Lock()


class SocialError(RuntimeError):
    """A safe, user-presentable error. Never contains tokens or secrets."""


@dataclass(frozen=True)
class OAuthConfig:
    client_id: str
    client_secret: str
    redirect_uri: str


def get_config(platform, values=None):
    """Read credentials from secrets or the environment. None means not configured."""
    values = values or {}

    def pick(name):
        return str(values.get(name, os.environ.get(name, ""))).strip()

    names = {"instagram": ("INSTAGRAM_APP_ID", "INSTAGRAM_APP_SECRET"), "tiktok": ("TIKTOK_CLIENT_KEY", "TIKTOK_CLIENT_SECRET")}[platform]
    client_id, client_secret, redirect = pick(names[0]), pick(names[1]), pick("OAUTH_REDIRECT_URI")
    if not (client_id and client_secret and redirect):
        return None
    parts = urlsplit(redirect)
    local = parts.hostname in {"localhost", "127.0.0.1"}
    if parts.scheme != "https" and not (local and parts.scheme == "http") or not parts.hostname or parts.fragment:
        raise SocialError("OAUTH_REDIRECT_URI must be an https address of this app.")
    return OAuthConfig(client_id, client_secret, redirect)


def _purge(now):
    for key in [k for k, (_, ts) in _pending.items() if now - ts > STATE_TTL]:
        _pending.pop(key, None)
    while len(_pending) > MAX_PENDING:
        _pending.pop(next(iter(_pending)))


def new_state(platform):
    """A single-use anti-CSRF value. Held server-side because the redirect starts a new session."""
    state = secrets.token_urlsafe(24)
    now = time.time()
    with _lock:
        _purge(now)
        _pending[state] = (platform, now)
    return state


def is_pending(state):
    with _lock:
        item = _pending.get(state)
        return bool(item and time.time() - item[1] <= STATE_TTL)


def consume_state(state):
    """Return the platform the state was issued for, once. None if unknown, used or expired."""
    with _lock:
        item = _pending.pop(state, None)
    if not item or time.time() - item[1] > STATE_TTL:
        return None
    return item[0]


def auth_url(platform, config, state):
    if platform == "instagram":
        query = {"client_id": config.client_id, "redirect_uri": config.redirect_uri, "response_type": "code", "scope": "instagram_business_basic", "state": state}
        return "https://www.instagram.com/oauth/authorize?" + urlencode(query)
    query = {"client_key": config.client_id, "scope": "user.info.basic,video.list", "response_type": "code", "redirect_uri": config.redirect_uri, "state": state}
    return "https://www.tiktok.com/v2/auth/authorize/?" + urlencode(query)


def _json(response, what):
    if response.status_code >= 400:
        raise SocialError(f"{what} failed (HTTP {response.status_code}).")
    try:
        return response.json()
    except ValueError:
        raise SocialError(f"{what} returned an unreadable answer.") from None


def exchange_code(platform, config, code, client=None):
    """Swap the one-time code for an access token. Returns the token string."""
    own = client is None
    client = client or httpx.Client(timeout=TIMEOUT)
    try:
        if platform == "instagram":
            response = client.post("https://api.instagram.com/oauth/access_token", data={
                "client_id": config.client_id, "client_secret": config.client_secret, "grant_type": "authorization_code",
                "redirect_uri": config.redirect_uri, "code": code})
            data = _json(response, "Instagram sign-in")
            data = (data.get("data") or [data])[0]
        else:
            response = client.post(f"{TIKTOK_API}/oauth/token/", data={
                "client_key": config.client_id, "client_secret": config.client_secret, "code": code,
                "grant_type": "authorization_code", "redirect_uri": config.redirect_uri})
            data = _json(response, "TikTok sign-in")
        token = data.get("access_token")
        if not token:
            raise SocialError("The platform did not return an access token.")
        return token
    except httpx.HTTPError:
        raise SocialError("Could not reach the platform. Try again in a moment.") from None
    finally:
        if own:
            client.close()


def _frame(rows):
    df = pd.DataFrame(rows, columns=VIDEO_COLUMNS)
    df["created"] = pd.to_datetime(df["created"], utc=True, errors="coerce")
    for column in ("views", "likes", "comments", "shares"):
        df[column] = pd.to_numeric(df[column], errors="coerce")
    return df.dropna(subset=["created"]).sort_values("created", ascending=False).reset_index(drop=True)


def fetch_videos(platform, token, client=None):
    """Return (account name, DataFrame of recent videos, platform account id)."""
    own = client is None
    client = client or httpx.Client(timeout=TIMEOUT)
    try:
        if platform == "instagram":
            me = _json(client.get(f"{INSTAGRAM_API}/me", params={"fields": "user_id,username", "access_token": token}), "Instagram profile")
            media = _json(client.get(f"{INSTAGRAM_API}/me/media", params={
                "fields": "id,caption,media_type,permalink,timestamp,like_count,comments_count", "limit": 50, "access_token": token}), "Instagram videos")
            rows = [{"id": m.get("id"), "title": (m.get("caption") or "").strip().splitlines()[0] if (m.get("caption") or "").strip() else "",
                     "created": m.get("timestamp"), "views": None, "likes": m.get("like_count"), "comments": m.get("comments_count"),
                     "shares": None, "url": m.get("permalink")}
                    for m in media.get("data", []) if m.get("media_type") == "VIDEO"]
            return "@" + str(me.get("username", "")), _frame(rows), str(me.get("user_id") or me.get("id") or "")
        headers = {"Authorization": f"Bearer {token}"}
        info = _json(client.get(f"{TIKTOK_API}/user/info/", params={"fields": "open_id,display_name"}, headers=headers), "TikTok profile")
        listing = _json(client.post(f"{TIKTOK_API}/video/list/", params={"fields": "id,title,create_time,share_url,view_count,like_count,comment_count,share_count"},
                                    headers=headers, json={"max_count": 20}), "TikTok videos")
        rows = [{"id": v.get("id"), "title": (v.get("title") or "").strip(),
                 "created": datetime.fromtimestamp(v["create_time"], tz=timezone.utc) if v.get("create_time") else None,
                 "views": v.get("view_count"), "likes": v.get("like_count"), "comments": v.get("comment_count"),
                 "shares": v.get("share_count"), "url": v.get("share_url")}
                for v in (listing.get("data") or {}).get("videos", [])]
        user = (info.get("data") or {}).get("user") or {}
        return str(user.get("display_name", "")), _frame(rows), str(user.get("open_id", ""))
    except httpx.HTTPError:
        raise SocialError("Could not reach the platform. Try again in a moment.") from None
    finally:
        if own:
            client.close()


def interactions(row):
    return float(row["likes"] if pd.notna(row["likes"]) else 0) + float(row["comments"] if pd.notna(row["comments"]) else 0) + float(row["shares"] if pd.notna(row["shares"]) else 0)


def analyze_video(video, videos, reference):
    """Descriptive comparison only: the account's other videos and the study dataset."""
    own = videos.apply(interactions, axis=1)
    mine = interactions(video)
    result = {
        "interactions": mine,
        "rank": int((own > mine).sum()) + 1,
        "count": int(len(own)),
        "vs_account_median": (mine / own.median() - 1) if own.median() else None,
        "vs_reference_median": (mine / reference.total_interactions.median() - 1) if reference.total_interactions.median() else None,
        "hour": int(video["created"].hour),
        "weekday": int(video["created"].weekday()),
    }
    if len(videos) >= 5:
        by_hour = videos.assign(score=own, hour=videos["created"].dt.hour).groupby("hour").score.median()
        result["best_hour"] = int(by_hour.idxmax())
    return result
